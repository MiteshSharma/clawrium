"""Behavioral regression tests for openclaw pair_device.mjs protocol negotiation.

Issue #608: pair_device.mjs pinned both minProtocol and maxProtocol to 3, which
the v2026.5.28 daemon (expectedProtocol=4) rejected. These tests stand up a
local Node WebSocket server mimicking the daemon's connect.challenge -> connect
-> hello-ok handshake and assert the pair script:
  - Succeeds against expectedProtocol=4 (current pinned daemon version).
  - Succeeds against expectedProtocol=3 (backward compat for older deployments).
  - Fails loudly with a protocol-mismatch message naming the supported range
    when the daemon advertises a protocol outside [3, 4].

The mock daemon and the pair script both rely on the `ws` npm package. A
session-scoped fixture installs `ws` into a cache dir under the repo (skipped
if `node` or `npm` are missing).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PAIR_SCRIPT = (
    REPO_ROOT
    / "src"
    / "clawrium"
    / "platform"
    / "registry"
    / "openclaw"
    / "scripts"
    / "pair_device.mjs"
)
MOCK_DAEMON = Path(__file__).parent / "fixtures" / "mock_openclaw_daemon.mjs"
WS_CACHE = REPO_ROOT / "tests" / "platform" / "fixtures" / ".ws_cache"


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def node_env() -> dict[str, Path]:
    """Set up a working directory with `ws` installed and copies of both
    scripts. Node's ESM loader resolves bare imports from the script's
    location upward, so the scripts must live next to a node_modules with
    `ws` in it — NODE_PATH does not work for ESM bare specifiers.
    """
    if not _have("node"):
        pytest.skip("node required for behavioral pair test")
    if not _have("npm"):
        pytest.skip("npm required to install ws for behavioral pair test")
    if not (WS_CACHE / "node_modules" / "ws" / "package.json").exists():
        WS_CACHE.mkdir(parents=True, exist_ok=True)
        # Minimal package.json so npm doesn't walk up looking for one.
        (WS_CACHE / "package.json").write_text(
            json.dumps({"name": "pair-device-test-cache", "private": True}) + "\n"
        )
        result = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--silent", "ws@^8"],
            cwd=WS_CACHE,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            pytest.skip(
                f"failed to install ws for pair test: {result.stderr.strip() or result.stdout.strip()}"
            )
    # Stage the scripts next to node_modules so ESM resolution finds `ws`.
    pair_copy = WS_CACHE / "pair_device.mjs"
    mock_copy = WS_CACHE / "mock_openclaw_daemon.mjs"
    pair_copy.write_text(PAIR_SCRIPT.read_text())
    mock_copy.write_text(MOCK_DAEMON.read_text())
    return {"pair": pair_copy, "mock": mock_copy, "env": os.environ.copy()}


def _spawn_mock_daemon(
    port: int, expected_protocol: int, ctx: dict
) -> subprocess.Popen:
    proc = subprocess.Popen(
        [
            "node",
            str(ctx["mock"]),
            "--port",
            str(port),
            "--expected-protocol",
            str(expected_protocol),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=ctx["env"],
        text=True,
    )
    # Block until the daemon prints its "ready" line or dies.
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else "") or ""
            raise RuntimeError(f"mock daemon exited early: {err}")
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            time.sleep(0.05)
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "ready":
            return proc
    proc.kill()
    raise TimeoutError("mock daemon never became ready")


def _run_pair_script(port: int, ctx: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "node",
            str(ctx["pair"]),
            f"ws://127.0.0.1:{port}",
            "test-bootstrap-token",
        ],
        capture_output=True,
        text=True,
        env=ctx["env"],
        timeout=15,
    )


def _pair_against(expected_protocol: int, ctx: dict):
    port = _free_port()
    daemon = _spawn_mock_daemon(port, expected_protocol, ctx)
    try:
        return _run_pair_script(port, ctx)
    finally:
        daemon.terminate()
        try:
            daemon.wait(timeout=2)
        except subprocess.TimeoutExpired:
            daemon.kill()


@pytest.mark.parametrize("expected_protocol", [3, 4])
def test_pair_succeeds_against_supported_protocol(
    expected_protocol: int, node_env: dict
) -> None:
    """Pair script must succeed against daemons in the supported range."""
    result = _pair_against(expected_protocol, node_env)
    assert result.returncode == 0, (
        f"pair script failed against expectedProtocol={expected_protocol}:\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    # Last stdout line is the JSON output with deviceId/deviceToken.
    output_lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    assert output_lines, f"no stdout from pair script: {result.stdout!r}"
    payload = json.loads(output_lines[-1])
    assert payload["deviceId"]
    assert payload["deviceToken"].startswith("mock-device-token-")
    assert "PRIVATE KEY" in payload["privateKeyPem"]


@pytest.mark.parametrize("expected_protocol", [2, 5])
def test_pair_fails_loudly_on_unsupported_protocol(
    expected_protocol: int, node_env: dict
) -> None:
    """Pair script must exit non-zero with a clear protocol-mismatch message
    when the daemon's expected protocol falls outside [3, 4]."""
    result = _pair_against(expected_protocol, node_env)
    assert result.returncode != 0, (
        f"pair script unexpectedly succeeded against expectedProtocol={expected_protocol}"
    )
    combined = result.stdout + "\n" + result.stderr
    # The error message must name the supported range AND the daemon's expected
    # protocol so the operator knows what to bump.
    assert "v3-v4" in combined, (
        f"missing supported-range marker in error output: {combined!r}"
    )
    assert f"v{expected_protocol}" in combined, (
        f"missing daemon-expected protocol marker in error output: {combined!r}"
    )
