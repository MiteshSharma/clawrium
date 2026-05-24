"""Unified error formatter.

Plan §6.1 / §6.12:

- Every error writes `Error: <msg>` to stderr.
- An optional one-line `Hint: <text>` follows, vertically aligned with
  the `Error:` prefix (`Hint:  <text>` — two trailing spaces after the
  colon so the body aligns with `Error:`'s body).
- Process exits non-zero.
"""

import sys
from typing import IO, NoReturn, Optional

import typer


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
    target.write(f"Error: {message}\n")
    if hint is not None:
        # Two spaces after "Hint:" so the body aligns under the body
        # of "Error:" — both have a 7-char prefix to their content.
        target.write(f"Hint:  {hint}\n")
    target.flush()
    raise typer.Exit(code=exit_code)
