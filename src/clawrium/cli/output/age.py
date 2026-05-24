"""kubectl-style AGE column formatter.

Plan §6.14:

- `<60s`  → `Xs`
- `<60m`  → `Xm`
- `<24h`  → `Xh`
- everything else → `Xd`

No weeks, no months — matches `kubectl`'s AGE column verbatim. Caller
passes the elapsed seconds as an int (already-computed against
`age_seconds` for JSON/YAML output).
"""

_MIN_S = 60
_HOUR_S = 60 * 60
_DAY_S = 24 * 60 * 60


def format_age(seconds: int) -> str:
    """Format `seconds` as kubectl's AGE token.

    Negative inputs are clamped to `0s` — easier to spot in output than
    raising, and matches the practical case where wall-clock skew makes
    a freshly-created resource look like it's from the future.
    """
    if seconds < 0:
        return "0s"
    if seconds < _MIN_S:
        return f"{seconds}s"
    if seconds < _HOUR_S:
        return f"{seconds // _MIN_S}m"
    if seconds < _DAY_S:
        return f"{seconds // _HOUR_S}h"
    return f"{seconds // _DAY_S}d"
