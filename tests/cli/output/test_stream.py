"""Tests for the NDJSON action streamer."""

import io
import json

import pytest

from clawrium.cli.output.stream import NDJSONStreamer, emit_event, stream_action


class TestNDJSONStreamer:
    def test_emit_writes_one_object_per_line(self) -> None:
        buf = io.StringIO()
        s = NDJSONStreamer(stream=buf)
        s.emit(
            resource="agent/wise-hypatia",
            phase="install",
            state="started",
            ts="2026-05-23T10:14:00Z",
        )
        s.emit(
            resource="agent/wise-hypatia",
            phase="install",
            state="complete",
            ts="2026-05-23T10:14:42Z",
            version="0.4.2",
        )

        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        # Required keys present
        for ev in (first, second):
            for k in ("resource", "phase", "state", "ts"):
                assert k in ev
        # Extras pass through
        assert second["version"] == "0.4.2"

    def test_ts_auto_populated_when_missing(self) -> None:
        buf = io.StringIO()
        s = NDJSONStreamer(stream=buf)
        s.emit(resource="agent/x", phase="install", state="started")
        ev = json.loads(buf.getvalue().strip())
        # RFC3339 ends with Z
        assert ev["ts"].endswith("Z")


class TestEmitEvent:
    def test_pre_built_event(self) -> None:
        buf = io.StringIO()
        emit_event(
            {
                "resource": "agent/x",
                "phase": "start",
                "state": "complete",
                "ts": "2026-05-23T10:15:00Z",
            },
            stream=buf,
        )
        ev = json.loads(buf.getvalue().strip())
        assert ev["resource"] == "agent/x"

    def test_missing_key_raises(self) -> None:
        with pytest.raises(KeyError):
            emit_event({"resource": "x", "phase": "p"}, stream=io.StringIO())


class TestStreamAction:
    def test_human_line_format(self) -> None:
        buf = io.StringIO()
        stream_action(
            resource="agent/wise-hypatia",
            message="installed",
            stream=buf,
        )
        assert buf.getvalue() == "agent/wise-hypatia: installed\n"
