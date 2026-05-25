"""`clawctl host get` — list hosts with `-o` format selection.

Plan §6.1 contract:

- Default `-o table`: NAME ADDRESS USER STATUS AGE
- `-o wide`: adds PORT and LABELS columns
- `-o json` / `-o yaml`: serializable array of host rows
- `-o name`: `host/<name>` one per line
- `-l KEY=VALUE`: label-selector filter (repeatable)
- `--no-headers`: skip the header row in table modes
"""

from __future__ import annotations

from typing import Optional

import typer

from clawrium.cli.clawctl._common import OutputFormat, parse_kv_labels
from clawrium.cli.clawctl.host._shared import (
    host_to_row,
    matches_label_selector,
    safe_load_hosts,
)
from clawrium.cli.output import (
    dump_json,
    dump_name,
    dump_yaml,
    format_age,
    format_status,
    render_table,
)


def get(
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
    selectors: Optional[list[str]] = typer.Option(
        None, "-l", "--selector", help="Label selector (KEY=VALUE). Repeatable."
    ),
    no_headers: bool = typer.Option(
        False, "--no-headers", help="Skip the header row (table modes only)."
    ),
) -> None:
    """List registered hosts."""
    selector = parse_kv_labels(selectors)
    hosts = safe_load_hosts()
    rows = [host_to_row(h) for h in hosts if matches_label_selector(h, selector)]

    if output is OutputFormat.json:
        typer.echo(dump_json(rows), nl=False)
        return
    if output is OutputFormat.yaml:
        typer.echo(dump_yaml(rows), nl=False)
        return
    if output is OutputFormat.name:
        typer.echo(dump_name(rows), nl=False)
        return

    if output is OutputFormat.wide:
        headers = ["NAME", "ADDRESS", "USER", "PORT", "STATUS", "AGE", "LABELS"]
        body = [
            [
                str(r["name"]),
                str(r["address"]),
                str(r["user"] or "-"),
                str(r["port"] or "-"),
                format_status(str(r["status"])),
                format_age(int(r["age_seconds"])),
                _labels_inline(r["labels"]) or "-",
            ]
            for r in rows
        ]
    else:
        headers = ["NAME", "ADDRESS", "USER", "STATUS", "AGE"]
        body = [
            [
                str(r["name"]),
                str(r["address"]),
                str(r["user"] or "-"),
                format_status(str(r["status"])),
                format_age(int(r["age_seconds"])),
            ]
            for r in rows
        ]

    typer.echo(render_table(headers, body, no_headers=no_headers), nl=False)


def _labels_inline(labels: dict) -> str:
    if not labels:
        return ""
    return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
