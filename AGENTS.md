# Clawrium

**An aquarium for your claws.**

Clawrium is a CLI tool (`clm`) for managing AI Claw fleets (ZeroClaw, NemoClaw, OpenClaw, or any other claw) on local networks. It allows users to deploy and manage multiple claw instances across hosts without dealing with each host separately. Using Clawrium, you can
1. manage any number of assistants on your local network
2. manage the agent lifecycle (upgrades, secrets management, backups etc)
3. track token usage across different agents and build guardrails
4. experiment with different models across your agent fleet

## Resources

- Repository: https://github.com/ric03uec/clawrium
- Project Board: https://github.com/users/ric03uec/projects/1

## Version

26.3.0

## Tech Stack

- **CLI**: Python + Typer
- **Execution**: ansible-runner
- **Packaging**: uv/uvx

## Key Concepts

- **Host**: A machine in your network that runs one or more claws
- **Claw**: An AI assistant instance (zeroclaw, nemoclaw, or openclaw)
- **Registry**: Platform-defined claw types with versions, dependencies, and templates

## User Data

All user configuration stored in `~/.config/clawrium/`

## Development

Always use `make` commands to run tests and validate changes:

```bash
make test       # Run tests (required before commits)
make lint       # Check code style
make format     # Format code
make test-cov   # Run tests with coverage
```

## Review

When @atx-ci provides a review, the caller MUST fix all issues and iterate until:
1. Rating is >3/5
2. No blocking issues remain

All @atx-ci generated reviews and feedback MUST be updated in the commit. Use the format
```
ATX Review Summary
Review <number>: Rating <1/5>
Blocking issues:
<table with blocking issues, reasoning, and recommendations>

Warnings:
<table with warnings and recommendations>

Suggestions:
<good to have improvements>

Co-Authored-By: ATX CI <atx-ci@noreply.github.com> (@atx-ci)
```
