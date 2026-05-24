"""Unified error formatter.

Plan §6.1 / §6.12:

- Every error writes `Error: <msg>` to stderr.
- An optional one-line `Hint: <text>` follows, vertically aligned with
  the `Error:` prefix (`Hint:  <text>` — two trailing spaces after the
  colon so the body aligns with `Error:`'s body).
- Process exits non-zero.

Both `message` and `hint` are bidi/control-char sanitized (#507 ATX
iter-1 B1): callers frequently forward server-supplied strings (HTTP
error bodies, ansible event text) and the bug class this guards
against — `U+202E` reversing terminal output — was already hardened in
`cli/chat.py:_sanitize_exception_text`. Sanitizing at the primitive
keeps callers from having to remember.
"""

import sys
from typing import IO, NoReturn, Optional

import typer

from clawrium.cli.output._sanitize import sanitize


def emit_error(
    message: str,
    *,
    hint: Optional[str] = None,
    exit_code: int = 1,
    stream: Optional[IO[str]] = None,
) -> NoReturn:
    """Write a structured error to stderr and raise `typer.Exit`.

    Raises `typer.Exit(exit_code)` so Typer's runtime catches it and
    sets the process exit code. Tests can intercept via
    `pytest.raises(typer.Exit)` or `CliRunner.invoke().exit_code`.
    """
    target = stream if stream is not None else sys.stderr
    target.write(f"Error: {sanitize(message)}\n")
    if hint is not None:
        # Two spaces after "Hint:" so the body aligns under the body
        # of "Error:" — both have a 7-char prefix to their content.
        target.write(f"Hint:  {sanitize(hint)}\n")
    target.flush()
    raise typer.Exit(code=exit_code)
