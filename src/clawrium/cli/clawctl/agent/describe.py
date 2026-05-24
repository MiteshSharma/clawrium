"""`clawctl agent describe <name>` — single-agent detail.

Plan §6.7 layout: Name / Kind / Type / Version / Host / Provider /
Status / Age / Installed + Config + Skills + Integrations + Channels
+ Onboarding sections.
"""

from __future__ import annotations

import typer

from clawrium.cli.clawctl._common import OutputFormat
from clawrium.cli.clawctl.agent._shared import agent_to_row, safe_resolve_agent
from clawrium.cli.output import dump_json, dump_yaml, format_age, format_status


def describe(
    name: str = typer.Argument(..., help="Agent name."),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format (yaml/json or text)."
    ),
) -> None:
    """Describe a single agent."""
    host, agent_key, claw_record = safe_resolve_agent(name)
    row = agent_to_row(host, agent_key, claw_record)

    if output is OutputFormat.json:
        typer.echo(dump_json([row]), nl=False)
        return
    if output is OutputFormat.yaml:
        typer.echo(dump_yaml([row]), nl=False)
        return

    lines: list[str] = []
    lines.append(f"Name:       {row['name']}")
    lines.append("Kind:       agent")
    lines.append(f"Type:       {row['type']}")
    lines.append(f"Version:    {row['version'] or '-'}")
    lines.append(f"Host:       {row['host']} ({row['address']})")
    lines.append(f"Provider:   {row['provider'] or '-'}")
    lines.append(f"Status:     {format_status(str(row['status']))}")
    lines.append(f"Age:        {format_age(int(row['age_seconds']))}")
    lines.append(f"Installed:  {row['installed_at'] or '-'}")

    config = claw_record.get("config", {}) or {}
    lines.append("")
    lines.append("Config:")
    lines.append(f"  Port:    {row['port'] or '-'}")
    identity = config.get("identity") or config.get("identity_file") or "-"
    lines.append(f"  Identity: {identity}")

    skills = (config.get("skills") or claw_record.get("skills") or []) or []
    lines.append("")
    lines.append(f"Skills ({len(skills)}):")
    for skill in skills:
        if isinstance(skill, dict):
            lines.append(f"  {skill.get('name') or skill.get('ref', '?')}")
        else:
            lines.append(f"  {skill}")

    integrations = config.get("integrations") or claw_record.get("integrations") or {}
    if isinstance(integrations, dict):
        integration_names = sorted(integrations.keys())
    else:
        integration_names = list(integrations)
    lines.append("")
    lines.append(f"Integrations ({len(integration_names)}):")
    for integration in integration_names:
        lines.append(f"  {integration}  (configured)")

    channels = (config.get("channels") or claw_record.get("channels") or []) or []
    lines.append("")
    if channels:
        lines.append(f"Channels ({len(channels)}):")
        for channel in channels:
            if isinstance(channel, dict):
                lines.append(f"  {channel.get('name') or channel.get('type', '?')}")
            else:
                lines.append(f"  {channel}")
    else:
        lines.append("Channels: none")

    onboarding = claw_record.get("onboarding", {}) or {}
    stages = onboarding.get("stages", {}) or {}
    lines.append("")
    lines.append("Onboarding:")
    for stage in ("providers", "identity", "channels", "validate"):
        info = stages.get(stage, {})
        if isinstance(info, dict):
            stage_state = info.get("state", "pending")
            completed = info.get("completed_at", "")
        else:
            stage_state = str(info)
            completed = ""
        completed_part = f"   ({completed})" if completed else ""
        lines.append(f"  {stage:<10} {stage_state}{completed_part}")

    typer.echo("\n".join(lines))
