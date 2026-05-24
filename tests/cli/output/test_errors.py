"""Tests for the unified error formatter."""

import io

import pytest
import typer

from clawrium.cli.output.errors import emit_error


class TestEmitError:
    def test_writes_error_to_stderr_then_exits(self) -> None:
        buf = io.StringIO()
        with pytest.raises(typer.Exit) as exc:
            emit_error("foo", hint="bar", stream=buf)
        assert exc.value.exit_code == 1
        assert buf.getvalue() == "Error: foo\nHint:  bar\n"

    def test_no_hint(self) -> None:
        buf = io.StringIO()
        with pytest.raises(typer.Exit):
            emit_error("no hint provided", stream=buf)
        assert buf.getvalue() == "Error: no hint provided\n"

    def test_custom_exit_code(self) -> None:
        buf = io.StringIO()
        with pytest.raises(typer.Exit) as exc:
            emit_error("oh no", exit_code=2, stream=buf)
        assert exc.value.exit_code == 2

    def test_hint_indent_aligns_with_error_body(self) -> None:
        """`Hint:` has two trailing spaces so the body aligns with `Error:`'s body."""
        buf = io.StringIO()
        with pytest.raises(typer.Exit):
            emit_error("foo", hint="bar", stream=buf)
        lines = buf.getvalue().splitlines()
        # Both bodies start at column 7 (0-indexed): "Error: foo" and "Hint:  bar"
        error_body_col = lines[0].index("foo")
        hint_body_col = lines[1].index("bar")
        assert error_body_col == hint_body_col == 7
