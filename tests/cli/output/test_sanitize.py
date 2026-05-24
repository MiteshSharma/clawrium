"""Bidi / control-char sanitization corpus tests.

Codifies the dangerous codepoint set in `cli/output/_sanitize.py` so
any future drift between it and `cli/chat.py:_CONTROL_AND_BIDI_RE`
shows up here. ATX #341 v3 / #455 W2 hardened chat.py against this
class of terminal-deception attack (U+202E RIGHT-TO-LEFT OVERRIDE
silently reverse-prints subsequent output); #507 ATX iter-1 B1/B2/W1/W2
extended the contract to every output primitive that writes raw
strings.
"""

import io
import json

import pytest
import typer

from clawrium.cli.output._sanitize import _CONTROL_AND_BIDI_RE, sanitize
from clawrium.cli.output.errors import emit_error
from clawrium.cli.output.json_yaml import dump_name
from clawrium.cli.output.stream import NDJSONStreamer, stream_action
from clawrium.cli.output.table import render


# Canonical adversarial codepoints — every entry here MUST be stripped.
BIDI_AND_CONTROL = [
    "‮",  # RIGHT-TO-LEFT OVERRIDE  (the classic v3 demo)
    "⁦",  # LEFT-TO-RIGHT ISOLATE
    "⁧",  # RIGHT-TO-LEFT ISOLATE
    "⁨",  # FIRST STRONG ISOLATE
    "⁩",  # POP DIRECTIONAL ISOLATE
    "‎",  # LRM
    "‏",  # RLM
    "​",  # ZERO-WIDTH SPACE
    " ",  # LINE SEPARATOR
    " ",  # PARAGRAPH SEPARATOR
    "⁠",  # WORD JOINER
    "﻿",  # ZWNBSP / BOM
    "؜",  # ARABIC LETTER MARK
    "\x00",  # NUL
    "\x07",  # BEL — terminals will beep
    "\x1b",  # ESC — starts ANSI sequences
    "\x7f",  # DEL
    "\x9b",  # CSI (C1)
]


@pytest.mark.parametrize("dangerous", BIDI_AND_CONTROL)
def test_sanitize_strips_each_codepoint(dangerous: str) -> None:
    assert _CONTROL_AND_BIDI_RE.search(dangerous) is not None
    cleaned = sanitize(f"alpha{dangerous}omega")
    assert dangerous not in cleaned, f"codepoint U+{ord(dangerous):04X} survived"
    assert "alpha" in cleaned and "omega" in cleaned


def test_sanitize_passes_through_safe_strings() -> None:
    safe = "agent/wise-hypatia: installed at 2026-05-20T14:23:11Z"
    assert sanitize(safe) is safe  # cheap identity short-circuit


class TestEmitErrorSanitization:
    def test_strips_bidi_from_message(self) -> None:
        buf = io.StringIO()
        with pytest.raises(typer.Exit):
            emit_error("agent‮xists", hint="check‮state", stream=buf)
        for dangerous in ("‮",):
            assert dangerous not in buf.getvalue(), (
                f"emit_error leaked U+{ord(dangerous):04X}"
            )


class TestStreamActionSanitization:
    def test_strips_bidi_from_resource_and_message(self) -> None:
        buf = io.StringIO()
        stream_action(
            resource="agent/wise⁦hypatia",
            message="install‮complete",
            stream=buf,
        )
        for dangerous in ("‮", "⁦"):
            assert dangerous not in buf.getvalue()


class TestNDJSONStreamerSerialization:
    """`json.dumps(..., ensure_ascii=True)` is the safety boundary —
    every non-ASCII codepoint becomes `\\uXXXX` in the output, never the
    raw control char. Verify the property at the API boundary so a
    future switch to `ensure_ascii=False` immediately fails CI.
    """

    def test_dangerous_codepoint_emerges_escaped_not_raw(self) -> None:
        buf = io.StringIO()
        s = NDJSONStreamer(stream=buf)
        s.emit(
            resource="agent/x‮y",
            phase="install",
            state="started",
            ts="2026-05-23T10:14:00Z",
        )
        raw = buf.getvalue()
        # Raw control char NEVER appears verbatim.
        assert "‮" not in raw
        # Escaped form does (json's representation).
        assert "\\u202e" in raw
        # And the parsed JSON still contains the codepoint as a value —
        # that's fine; consumers of NDJSON parse the JSON and know what
        # they're getting.
        parsed = json.loads(raw)
        assert "‮" in parsed["resource"]


class TestDumpNameSanitization:
    def test_strips_bidi_from_kind_and_name(self) -> None:
        out = dump_name(
            [
                {"kind": "agent‮", "name": "wise⁦hypatia"},
            ]
        )
        for dangerous in ("‮", "⁦"):
            assert dangerous not in out


class TestRenderSanitization:
    def test_strips_bidi_from_cells_and_headers(self) -> None:
        out = render(
            headers=["NAME‮", "STATUS"],
            rows=[["wise⁦hypatia", "run‮ning"]],
        )
        for dangerous in ("‮", "⁦"):
            assert dangerous not in out
