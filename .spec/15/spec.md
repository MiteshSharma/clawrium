# Spec: Host Reset Command

> **Status**: draft
> **Issue**: #15
> **Created**: 2026-03-23
> **Author**: devashish

## Summary

`clm host reset <host>` nukes everything on a managed host except the `xclm` management user. Users, home directories, claw services, configs - gone. It's destructive by design. Don't run it unless you mean it.

## Motivation

Here's the problem: you've got hosts in your fleet that need recycling. Maybe a failed install left garbage behind. Maybe you're repurposing hardware. Maybe someone installed something they shouldn't have.

Right now, you SSH in and run commands manually. This is stupid for several reasons:

1. **You'll forget something.** There's always that one service file or stale user you miss.
2. **It's slow.** Multiply by N hosts and you've wasted your afternoon.
3. **It's inconsistent.** Everyone has their own "cleanup" routine.
4. **You'll screw up.** Run the wrong command on the wrong host. Fun times.

The `xclm` user already has sudo. We already run ansible playbooks for installation. A reset command is the obvious missing piece.

## Design

### The Approach

Run an Ansible playbook via `xclm`. Same pattern as `clm install`. This isn't complicated:

1. SSH to host as `xclm`
2. Enumerate what exists (users, services, paths)
3. Show the user what's about to die
4. Kill it
5. Update local records

### CLI

```python
@host_app.command()
def reset(
    hostname: str = typer.Argument(..., help="Host to reset"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be removed"),
    untrack: bool = typer.Option(False, "--untrack", help="Remove host from registry after reset"),
) -> None:
    """Nuke a host back to clean state. DESTRUCTIVE."""
```

That's it. No `--force`, no `--really-force`, no `--i-promise-i-read-the-docs`. Just `--yes` to skip the prompt.

### What Gets Nuked

**Users**: Everything with uid >= 1000 except `xclm`. Period.

**Services**: Anything matching `*claw*.service`. If you installed other services manually, that's your problem.

**Paths**:
- `/etc/clawrium/`
- `/var/log/clawrium/`

**What survives**: `xclm`, system users, SSH host keys, network config.

### Output

Dry run:
```
$ clm host reset myhost --dry-run

Reset targets on myhost (192.168.1.100):

  Users (2):     opc-myhost, zc-myhost
  Services (2):  openclaw-opc-myhost.service, zeroclaw-zc-myhost.service
  Paths (2):     /etc/clawrium/, /var/log/clawrium/

  Preserved:     xclm, system users (uid < 1000)

[DRY RUN] Nothing changed.
```

Execution:
```
$ clm host reset myhost --yes

Resetting myhost (192.168.1.100)...

  Stopping services... 2 stopped
  Removing users... 2 removed
  Cleaning paths... 2 cleaned
  Updating records... done

Reset complete. Host is clean.
```

No progress bars. No emoji. No "are you super duper sure?" dialogs.

### Core Module

```python
# src/clawrium/core/reset.py

@dataclass
class ResetTargets:
    users: list[str]
    services: list[str]
    paths: list[str]

@dataclass  
class ResetResult:
    success: bool
    removed: dict[str, int]  # {"users": 2, "services": 2, "paths": 2}
    errors: list[str]

def enumerate_targets(hostname: str) -> ResetTargets:
    """Find everything that needs to die."""
    pass

def execute_reset(hostname: str, targets: ResetTargets) -> ResetResult:
    """Kill it all."""
    pass
```

### Playbook

`src/clawrium/platform/playbooks/reset.yaml`:

```yaml
---
- hosts: all
  become: yes
  tasks:
    - name: Stop and disable claw services
      ansible.builtin.systemd:
        name: "{{ item }}"
        state: stopped
        enabled: no
      loop: "{{ services_to_remove }}"
      ignore_errors: yes

    - name: Remove service files
      ansible.builtin.file:
        path: "/etc/systemd/system/{{ item }}"
        state: absent
      loop: "{{ services_to_remove }}"

    - name: Reload systemd
      ansible.builtin.systemd:
        daemon_reload: yes

    - name: Remove users and home directories
      ansible.builtin.user:
        name: "{{ item }}"
        state: absent
        remove: yes
        force: yes
      loop: "{{ users_to_remove }}"
      when: item != 'xclm'

    - name: Clean paths
      ansible.builtin.file:
        path: "{{ item }}"
        state: absent
      loop: "{{ paths_to_clean }}"
```

Simple. Idempotent. Does one thing.

### Files to Change

| File | What |
|------|------|
| `src/clawrium/cli/host.py` | Add reset command |
| `src/clawrium/core/reset.py` | New - reset logic |
| `src/clawrium/platform/playbooks/reset.yaml` | New - playbook |
| `tests/test_cli_host.py` | Reset command tests |
| `tests/test_reset.py` | New - core logic tests |

## Acceptance Criteria

Testable with commands:

- [ ] `clm host --help` shows `reset` command
- [ ] `clm host reset myhost` prompts for confirmation, exits 0 on abort
- [ ] `clm host reset myhost --dry-run` shows targets, changes nothing
- [ ] `clm host reset myhost --yes` executes without prompt
- [ ] After reset: no users with uid >= 1000 except xclm
- [ ] After reset: no `*claw*.service` in systemd
- [ ] After reset: `/etc/clawrium/` and `/var/log/clawrium/` don't exist
- [ ] After reset: host record has `claws: {}` and `last_reset` timestamp
- [ ] `--untrack` removes host from local registry
- [ ] Logs at `~/.config/clawrium/logs/reset-<host>-<timestamp>/`
- [ ] `make test` passes

## Alternatives Considered

| Alternative | Problem |
|-------------|---------|
| Shell script on host | Version drift, inconsistent with our ansible pattern |
| Raw SSH commands via paramiko | No idempotency, error handling nightmare |
| Selective cleanup (`--claw openclaw`) | Over-engineering for v1, add later if needed |

## Unresolved

- Timeout: 300s seems reasonable, same as base playbook
- Backup before reset: Out of scope. Document "backup first" in help text.

## Dependencies

None. This is standalone.

---

<details>
<summary>Prompt Log</summary>

```yaml
- model: anthropic.claude-opus-4-5-20251101-v1:0
  date: 2026-03-23
  type: spec-update
  prompt: |
    Rewrite spec in Linus Torvalds style - direct, blunt, technically precise.
    No corporate fluff. No unnecessary words. Say what it does, why, and how.
    Based on linus-code-auditor and linus-coder agent personas.
```

</details>
