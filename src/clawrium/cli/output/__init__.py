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
