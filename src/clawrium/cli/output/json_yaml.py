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

from clawrium.cli.output._sanitize import sanitize


def dump_json(rows: Sequence[Mapping[str, Any]]) -> str:
    """Serialize `rows` as a JSON array.

    Keys, values, and types pass through unchanged. Callers are
    responsible for emitting snake_case keys and pre-formatted RFC3339
    UTC timestamps (the rule lives in the plan; this module just
    serializes).

    `ensure_ascii=True` is explicit (Python default, but stated here
    so the safety boundary is visible -- raw bidi/control chars in
    string values become `\\uXXXX` escapes in the output, never
    reaching the terminal in raw form).
    """
    return json.dumps(list(rows), indent=2, sort_keys=False, ensure_ascii=True) + "\n"


def _sanitize_value(value: Any) -> Any:
    """Recursively `sanitize()` every string scalar in a nested structure.

    Used by `dump_yaml()` because `yaml.safe_dump()` does NOT escape
    LF (U+000A) inside block scalars — a crafted string with `\\n`
    survives verbatim in the YAML output. `dump_json()` is safe via
    `ensure_ascii=True`. Recursion handles nested lists/dicts so any
    future row schema with sub-objects keeps the invariant.
    """
    if isinstance(value, str):
        return sanitize(value)
    if isinstance(value, Mapping):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(v) for v in value]
    return value


def dump_yaml(rows: Sequence[Mapping[str, Any]]) -> str:
    """Serialize `rows` as a YAML list.

    Equivalence guarantee (asserted in tests):
    `yaml.safe_load(dump_yaml(rows)) == json.loads(dump_json(rows))`
    (modulo sanitization side-effects — both serializers neutralize
    bidi/control chars but via different mechanisms).

    Every string scalar is sanitized recursively (#507 ATX iter-3 W2):
    `yaml.safe_dump` escapes most C0/C1 control chars in single-quoted
    style but NOT LF (it emits a block scalar). Sanitizing at the
    primitive keeps parity with `dump_json` / `dump_name` and prevents
    a crafted agent name containing `\\n` from producing multi-line
    YAML from a field expected to be atomic.

    `allow_unicode=False` is explicit so any non-ASCII codepoint in
    a string scalar emerges as `\\uXXXX` instead of raw bytes. This
    makes the safety boundary auditable (#507 iter-3 S1).
    """
    safe_rows = [_sanitize_value(row) for row in rows]
    return yaml.safe_dump(
        safe_rows,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=False,
    )


def dump_name(rows: Sequence[Mapping[str, Any]]) -> str:
    """Serialize `rows` as `<kind>/<name>` lines.

    Each row MUST have `kind` and `name` keys. Missing keys raise
    `KeyError` — surfacing the problem to the caller is preferable to
    silently dropping records.

    Both `kind` and `name` are bidi/control-char sanitized at write
    time (#507 ATX iter-1 W2): names come from agent-registry-derived
    strings and a crafted manifest could embed bidi overrides.
    `dump_json()` is safe by serialization (`ensure_ascii=True`).
    `dump_yaml()` sanitizes recursively (see `_sanitize_value`).
    """
    lines = [
        f"{sanitize(str(row['kind']))}/{sanitize(str(row['name']))}" for row in rows
    ]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"
