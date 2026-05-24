"""`-o json`, `-o yaml`, and `-o name` serializers.

Contract (plan §6.5–6.6):

- `dump_json(rows)`  — array of objects, snake_case keys, RFC3339 UTC
  timestamps (caller pre-serializes datetimes), `age_seconds` ints.
- `dump_yaml(rows)`  — same shape, YAML-encoded.
- `dump_name(rows)`  — `<kind>/<name>` one per line; requires each row
  to carry `kind` and `name` keys.

All three return a single string ending in a newline; callers print
verbatim. JSON output is pretty-printed (2-space indent) so output is
human-readable AND machine-parseable.
"""

import json
from typing import Any, Mapping, Sequence

import yaml


def dump_json(rows: Sequence[Mapping[str, Any]]) -> str:
    """Serialize `rows` as a JSON array.

    Keys, values, and types pass through unchanged. Callers are
    responsible for emitting snake_case keys and pre-formatted RFC3339
    UTC timestamps (the rule lives in the plan; this module just
    serializes).
    """
    return json.dumps(list(rows), indent=2, sort_keys=False) + "\n"


def dump_yaml(rows: Sequence[Mapping[str, Any]]) -> str:
    """Serialize `rows` as a YAML list.

    Equivalence guarantee (asserted in tests):
    `yaml.safe_load(dump_yaml(rows)) == json.loads(dump_json(rows))`.
    """
    return yaml.safe_dump(
        list(rows),
        sort_keys=False,
        default_flow_style=False,
    )


def dump_name(rows: Sequence[Mapping[str, Any]]) -> str:
    """Serialize `rows` as `<kind>/<name>` lines.

    Each row MUST have `kind` and `name` keys. Missing keys raise
    `KeyError` — surfacing the problem to the caller is preferable to
    silently dropping records.
    """
    lines = [f"{row['kind']}/{row['name']}" for row in rows]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"
