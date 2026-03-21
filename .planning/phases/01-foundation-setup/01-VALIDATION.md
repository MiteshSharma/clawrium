---
phase: 1
slug: foundation-setup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` (Wave 0 installs) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --cov=clawrium` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --cov=clawrium`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | N/A | setup | `uv run pytest --version` | Wave 0 | pending |
| 01-01-02 | 01 | 1 | INIT-01 | unit | `uv run pytest tests/test_cli_init.py::test_init_creates_config_dir -x` | Wave 0 | pending |
| 01-01-03 | 01 | 1 | INIT-01 | unit | `uv run pytest tests/test_cli_init.py::test_init_respects_xdg -x` | Wave 0 | pending |
| 01-01-04 | 01 | 1 | INIT-02 | unit | `uv run pytest tests/test_cli_init.py::test_init_shows_dependency_status -x` | Wave 0 | pending |
| 01-01-05 | 01 | 1 | INIT-02 | unit | `uv run pytest tests/test_deps.py::test_ansible_missing -x` | Wave 0 | pending |
| 01-01-06 | 01 | 1 | INIT-02 | unit | `uv run pytest tests/test_deps.py::test_install_hints -x` | Wave 0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — needs `[tool.pytest.ini_options]` section
- [ ] `tests/conftest.py` — shared fixtures for tmp config dirs
- [ ] `tests/test_cli_init.py` — covers INIT-01 (config directory creation)
- [ ] `tests/test_deps.py` — covers INIT-02 (dependency detection)
- [ ] Framework install: `uv add --dev pytest pytest-cov`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | - | - | All phase behaviors have automated verification |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
