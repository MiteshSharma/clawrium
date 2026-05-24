"""Plain-text aligned table rendering (kubectl tabwriter style).

Padding rule (plan §6.1 / Option B):

- Each column is padded to the max width of any cell in that column.
- A fixed 3-space gap separates adjacent columns (no Rich borders).
- No trailing whitespace on any line.
- `--no-headers` omits the header row but width is still computed from
  data rows.
- Empty rows render as a single newline (no padding).

This renderer is intentionally simple — no truncation, no wrapping. The
goal is byte-stable, grep-friendly output that mirrors `kubectl get`.
"""

from typing import Sequence

GAP = "   "  # 3 spaces between columns


def render(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    no_headers: bool = False,
) -> str:
    """Render `rows` as an aligned table.

    `headers` and each row in `rows` must be sequences of strings. None
    or non-string values must be stringified by the caller — this keeps
    rendering rules in one place (callers know how to format their own
    domain values).

    Returns the rendered table as a single string ending in a newline
    when at least one row is present. An empty result (no headers and
    no rows) returns the empty string.
    """
    headers = [str(h) for h in headers]
    norm_rows: list[list[str]] = [[str(cell) for cell in row] for row in rows]

    if not headers and not norm_rows:
        return ""

    # Width per column is the max width across header (if shown) + rows.
    n_cols = max(
        (len(headers) if not no_headers else 0),
        max((len(r) for r in norm_rows), default=0),
    )
    widths = [0] * n_cols
    candidate_rows: list[list[str]] = []
    if not no_headers and headers:
        candidate_rows.append(list(headers))
    candidate_rows.extend(norm_rows)
    for r in candidate_rows:
        for i, cell in enumerate(r):
            if i < n_cols and len(cell) > widths[i]:
                widths[i] = len(cell)

    def fmt(row: Sequence[str]) -> str:
        parts: list[str] = []
        last = len(row) - 1
        for i, cell in enumerate(row):
            if i < last:
                parts.append(cell.ljust(widths[i]))
            else:
                # No padding on the last cell — keeps no trailing whitespace.
                parts.append(cell)
        return GAP.join(parts).rstrip()

    lines: list[str] = []
    if not no_headers and headers:
        lines.append(fmt(headers))
    for r in norm_rows:
        lines.append(fmt(r))

    return "\n".join(lines) + "\n"
