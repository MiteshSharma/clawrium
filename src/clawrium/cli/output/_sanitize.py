"""Terminal-output sanitization for the `clawctl` output primitives.

The output module writes server-supplied strings (agent names from
hosts.json, ansible-runner event text, hermes HTTP response bodies,
etc.) directly to stdout/stderr. A malicious upstream emitting bidi
override codepoints (U+202E etc.) can silently reverse-print the
user's terminal output — the exact class of bug ATX #341 v3 / #455 W2
hardened against in `cli/chat.py`.

`_CONTROL_AND_BIDI_RE` mirrors the pattern in `cli/chat.py` so the
coverage stays identical to the legacy parity contract. We re-state
the pattern here (rather than importing from chat.py) for two reasons:

1. The output module must stay self-contained — bundles 3-5 will
   refactor `cli/chat.py` and the import could break or shift coverage.
2. Drift detection: `tests/cli/output/test_sanitize.py` codifies the
   character set; any future edit to either copy must update both,
   surfacing the drift in CI.

Sanitization is applied at every primitive that writes a raw string
to a terminal stream: `emit_error()`, `stream_action()`, `dump_name()`,
`render_table()` cells. `NDJSONStreamer.emit()` and `dump_yaml()` are
safe by serialization (json.dumps with ensure_ascii=True and
yaml.safe_dump escape control characters in their output).
"""

import re

_CONTROL_AND_BIDI_RE = re.compile(
    # Mirrors `cli/chat.py:_CONTROL_AND_BIDI_RE`. Use explicit \uXXXX
    # escapes so literal bidi/zero-width codepoints never appear in
    # source — they are invisible to most editors and trivially
    # corrupted by auto-formatters / BOM insertion / careless paste.
    "["
    "\x00-\x1f\x7f-\x9f"
    "؜"  # ARABIC LETTER MARK
    "​-‏"  # ZWSP, ZWNJ, ZWJ, LRM, RLM
    " - "  # LINE / PARAGRAPH SEPARATOR
    "‪-‮"  # LRE, RLE, PDF, LRO, RLO
    "⁠"  # WORD JOINER
    "⁦-⁩"  # LRI, RLI, FSI, PDI
    "﻿"  # ZWNBSP / BOM
    "]"
)


def sanitize(value: str) -> str:
    """Strip control / bidi / zero-width chars; replace with a single space.

    Idempotent and pass-through for well-formed strings — only the
    dangerous codepoints are touched. Returns the input unchanged when
    nothing matches (no allocation in the common case).
    """
    if not _CONTROL_AND_BIDI_RE.search(value):
        return value
    return _CONTROL_AND_BIDI_RE.sub(" ", value)
