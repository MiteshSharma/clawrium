"""Guard tests for the per-agent-type template naming convention.

Issue #510 (Bundle 5 of #435) removes the historical `clm-` prefix from
Jinja2 templates under `src/clawrium/platform/registry/*/templates/`.
The convention going forward is that templates carry their agent-type
prefix (`zeroclaw-*`, `hermes-*`, etc.) so the source-vs-destination
file naming stays unambiguous at a glance.

This module enforces the regression-safe half of that convention: no
template anywhere under any registry's `templates/` tree may start with
`clm-`. The full `<type>-` / `<type>.` prefix convention is documented
in `.itx/435/00_PLAN.md` §10 but is not asserted here — pre-existing
unprefixed templates (`openclaw/templates/AGENTS.md.j2` etc.) remain
out of scope for this bundle per the explicit rename list in the
issue.
"""

from pathlib import Path

import pytest

REGISTRY_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "clawrium" / "platform" / "registry"
)


def _registry_templates() -> list[Path]:
    """Return every `*.j2` file under `registry/*/templates/`."""

    matches: list[Path] = []
    for registry_dir in REGISTRY_ROOT.iterdir():
        if not registry_dir.is_dir():
            continue
        templates_dir = registry_dir / "templates"
        if not templates_dir.exists():
            continue
        matches.extend(p for p in templates_dir.rglob("*.j2") if p.is_file())
    return matches


def test_template_root_resolves():
    """Smoke-test: the registry root the loader expects must exist."""

    assert REGISTRY_ROOT.is_dir(), f"Registry root not found: {REGISTRY_ROOT}"
    assert _registry_templates(), "No templates discovered — selector regressed?"


@pytest.mark.parametrize("template", _registry_templates(), ids=lambda p: str(p))
def test_no_clm_prefixed_templates(template: Path) -> None:
    """No template anywhere may carry the historical `clm-` prefix."""

    assert not template.name.startswith("clm-"), (
        f"Template {template} starts with the deprecated `clm-` prefix. "
        f"Rename per `.itx/435/00_PLAN.md` §10 (use `<type>-` or `<type>.`)."
    )
