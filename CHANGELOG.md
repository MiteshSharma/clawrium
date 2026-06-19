# Changelog

All notable changes to this project are documented here. Per-release frozen
archives live under [`docs/releases/`](docs/releases/) — that directory is
the single place to read the full history of what shipped in each version.

The project follows a `YY.M.PATCH` calendar versioning convention; the
`## [Unreleased]` section below is the working log for the next release
cut. The `itx:release` skill archives this section into a new
`docs/releases/<version>/CHANGELOG.md` and resets this file to an empty
`[Unreleased]` template on every release.

## [Unreleased]

### BREAKING

### Added

### Changed

### Fixed

### Documentation

- Landing page audit: restructured the GitHub README first-success path —
  added a Support Matrix near the top (control/host OS, agent runtimes,
  providers, channels), dropped the deliberate `xclm SSH verification
  failed` step from the 5-Minute Setup, added **Tested on Ubuntu** and
  **Tested on macOS** badges, and updated FAQ #1 to reflect macOS
  end-to-end support.
- Renamed the generic noun "Claw" / "Claws" → "Agent" / "Agents" across
  the README, AGENTS.md, the Docusaurus landing (tagline, hero,
  HomepageFeatures), website docs (intro, architecture, configuration,
  CLI reference, skills, fleet management, hermes/memory pages), and the
  repo-rooted docs index. Brand names (Clawrium, OpenClaw, ZeroClaw,
  IronClaw, NemoClaw, Hermes) are preserved, as are real on-disk
  identifiers (`*claw` systemd glob, `claw_supports_memory` Python
  symbol).
- Replaced remaining `clm` references with `clawctl` on the website
  landing's `HomepageFeatures` ASCII diagram and sample output, and in
  the `troubleshooting.md` setup-snippet placeholder. Dated migration
  blog posts and `docs/releases/*/CHANGELOG.md` archives are intentionally
  left untouched.
