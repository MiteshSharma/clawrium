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

Sanitization contract (#507 ATX iter-1):

| Primitive                              | Sanitizes? |
|----------------------------------------|------------|
| `errors.emit_error(message, hint)`     | Yes        |
| `stream.stream_action(resource, msg)`  | Yes        |
| `json_yaml.dump_name(kind, name)`      | Yes        |
| `table.render()` cells + headers       | Yes        |
| `stream.NDJSONStreamer.emit()`         | Safe via `json.dumps` (`ensure_ascii=True`) |
| `stream.emit_event()`                  | Safe via `json.dumps` |
| `json_yaml.dump_json()`                | Safe via `json.dumps` |
| `json_yaml.dump_yaml()`                | Safe via `yaml.safe_dump` |
| `age.format_age()`                     | N/A — int input |
| `status.format_status()`               | N/A — input constrained to status vocab |

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
