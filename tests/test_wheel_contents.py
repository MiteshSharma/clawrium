"""Regression test: built wheel must ship the staged GUI frontend.

Without this, `clm gui` after `uv tool install clawrium` returns 404 on every
non-API route because `mount_frontend()` short-circuits when
`clawrium/gui/frontend/index.html` is missing inside the installed package
(see issue #401).

The test is a no-op locally when the GUI hasn't been built (running `make
test-py` without `make build-ui` shouldn't fail for contributors who don't
have Node installed). It runs whenever the staged frontend exists, and CI
must build the GUI before invoking this test to catch wheel-config regressions.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGED_FRONTEND_INDEX = REPO_ROOT / "src" / "clawrium" / "gui" / "frontend" / "index.html"


pytestmark = [
    pytest.mark.skipif(
        not STAGED_FRONTEND_INDEX.exists(),
        reason="Staged GUI frontend missing — run `make build-ui` to enable this test",
    ),
    pytest.mark.skipif(
        shutil.which("uv") is None,
        reason="`uv` not on PATH — required to build the wheel",
    ),
]


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out_dir = tmp_path_factory.mktemp("wheel-out")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(out_dir.glob("clawrium-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found: {wheels}"
    return wheels[0]


def test_wheel_includes_frontend_index(built_wheel: Path) -> None:
    with zipfile.ZipFile(built_wheel) as zf:
        names = set(zf.namelist())
    assert "clawrium/gui/frontend/index.html" in names, (
        "Wheel is missing the staged Next.js frontend. "
        "Check `[tool.hatch.build.targets.wheel.force-include]` in pyproject.toml — "
        "without this, `clm gui` 404s on every non-API route after install (#401)."
    )


def test_wheel_includes_skills_catalog(built_wheel: Path) -> None:
    with zipfile.ZipFile(built_wheel) as zf:
        names = zf.namelist()
    assert any(name.startswith("clawrium/_skills/") for name in names), (
        "Wheel is missing the skills catalog. "
        "Check `[tool.hatch.build.targets.wheel.force-include]` in pyproject.toml."
    )


def test_wheel_frontend_has_route_pages(built_wheel: Path) -> None:
    """Spot-check a couple of route exports so a partial UI build is also caught."""
    with zipfile.ZipFile(built_wheel) as zf:
        names = set(zf.namelist())
    for route in ("agents.html", "topology.html"):
        assert f"clawrium/gui/frontend/{route}" in names, (
            f"Wheel is missing route export `{route}` — UI build may be incomplete."
        )
