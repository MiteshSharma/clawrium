"""Shared output-rendering primitives for the `clawctl` CLI.

Every `get`/`describe` subcommand built in later bundles renders through
this module. The contract is documented in `.itx/435/00_PLAN.md` §6
(output format contract). Highlights:

- `table.render()`  — kubectl tabwriter-style padding, min 3-space gap.
- `json_yaml.dump()` — `-o json` / `-o yaml` serializers (snake_case keys,
  RFC3339 UTC timestamps, `age_seconds` ints).
- `stream.NDJSONStreamer` — one JSON object per line for action output.
- `errors.emit_error()` — `Error: ...\nHint: ...\n` to stderr + nonzero
  exit.
- `age.format_age()` — kubectl-style AGE column (s/m/h/d only).
- `status.format_status()` — TTY-only color for the STATUS column.

This module imports nothing from `clawrium.core.*`; it deals only with
rendering primitives.

Sanitization contract (#507 ATX iter-1/2/3):

| Primitive                              | Sanitizes? |
|----------------------------------------|------------|
| `errors.emit_error(message, hint)`     | Yes |
| `stream.stream_action(resource, msg)`  | Yes |
| `json_yaml.dump_name(kind, name)`      | Yes |
| `json_yaml.dump_yaml()` string scalars | Yes (recursive, via `_sanitize_value`) |
| `table.render()` cells + headers       | Yes |
| `stream.NDJSONStreamer.emit()`         | Safe via `json.dumps(..., ensure_ascii=True)` |
| `stream.emit_event()`                  | Safe via `json.dumps(..., ensure_ascii=True)` |
| `json_yaml.dump_json()`                | Safe via `json.dumps(..., ensure_ascii=True)` |
| `status.format_status()`               | Yes (unknown-token path; known vocab tokens are identity-returned) |
| `age.format_age()`                     | N/A — int input |

`sanitize()` IS NOT a secret redactor — see `_sanitize.py` module
docstring. Callers must never pass secret-valued strings to any
output primitive; the safety boundary lives at the call site that
decides what to log.

The shared pattern lives in `_sanitize.py` and mirrors
`cli/chat.py:_CONTROL_AND_BIDI_RE` so the coverage stays identical
to the legacy parity contract from ATX #341 v3 / #455 W2.
"""

from clawrium.cli.output.age import format_age
from clawrium.cli.output.errors import emit_error
from clawrium.cli.output.json_yaml import dump_json, dump_yaml, dump_name
from clawrium.cli.output.status import format_status
from clawrium.cli.output.stream import NDJSONStreamer, stream_action
from clawrium.cli.output.table import render as render_table

__all__ = [
    "NDJSONStreamer",
    "dump_json",
    "dump_name",
    "dump_yaml",
    "emit_error",
    "format_age",
    "format_status",
    "render_table",
    "stream_action",
]
