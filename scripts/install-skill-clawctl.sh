#!/usr/bin/env bash
# Install the /clawctl skill globally for any installed AI assistant
# (Claude Code, opencode), plus the clawctl-audit companion tool.
# Idempotent — re-running updates an existing install.
#
# Supports: Ubuntu / Debian-family Linux and macOS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ric03uec/clawrium/main/scripts/install-skill-clawctl.sh | bash
#
# Override the version (defaults to the locally-installed clawctl, else "main"):
#   curl -fsSL ... | CLAWCTL_VERSION=v26.6.3 bash
#
# Exit codes:
#   0  success — installed for at least one detected assistant
#   1  no supported assistant detected on this machine
#   2  unsupported OS
#   3  required command (curl or python3) missing
#   4  network/download failure for every detected assistant
#   5  failed to install clawctl-audit companion tool

set -euo pipefail

REPO="ric03uec/clawrium"
SKILL_NAME="clawctl"
AUDIT_BIN_NAME="clawctl-audit"
AUDIT_INSTALL_DIR="${CLAWCTL_AUDIT_BIN_DIR:-$HOME/.local/bin}"

# ---------------------------------------------------------------------------
# 0. Preflight
# ---------------------------------------------------------------------------

OS="$(uname -s)"
case "$OS" in
  Linux|Darwin) ;;
  *)
    printf 'error: unsupported OS: %s (this script supports Linux and macOS)\n' "$OS" >&2
    exit 2
    ;;
esac

if ! command -v curl >/dev/null 2>&1; then
  printf 'error: curl is required but not installed.\n' >&2
  case "$OS" in
    Linux)  printf '       install with: sudo apt-get install -y curl\n' >&2 ;;
    Darwin) printf '       install with: brew install curl  (or use the system curl on macOS 10.15+)\n' >&2 ;;
  esac
  exit 3
fi

if ! command -v python3 >/dev/null 2>&1; then
  printf 'error: python3 is required for the clawctl-audit companion tool but not installed.\n' >&2
  case "$OS" in
    Linux)  printf '       install with: sudo apt-get install -y python3\n' >&2 ;;
    Darwin) printf '       install with: brew install python  (or use the Xcode-bundled python3)\n' >&2 ;;
  esac
  exit 3
fi

# ---------------------------------------------------------------------------
# 1. Determine which clawrium version's payload to fetch
# ---------------------------------------------------------------------------

VERSION="${CLAWCTL_VERSION:-}"
if [ -z "$VERSION" ] && command -v clawctl >/dev/null 2>&1; then
  detected="$(clawctl version 2>/dev/null | awk '{print $2}' || true)"
  if [ -n "${detected:-}" ]; then
    VERSION="v${detected}"
  fi
fi
# Fall back to main if clawctl isn't installed locally — the skill works
# standalone; the operator can install clawctl later.
: "${VERSION:=main}"

printf '==> Installing /%s skill + %s companion tool (version: %s)\n' "$SKILL_NAME" "$AUDIT_BIN_NAME" "$VERSION"
printf '    OS: %s\n' "$OS"

# ---------------------------------------------------------------------------
# 2. Detect installed AI assistants and install the skill globally for each
# ---------------------------------------------------------------------------

TOOLS_FOUND=0
DOWNLOAD_FAILURES=0

# Download one file from the repo at the chosen VERSION to a destination.
# Args: $1 label, $2 source-path-in-repo, $3 dest-file.
# Returns 0 on success.
download_to() {
  label="$1"
  source_path="$2"
  dest_file="$3"
  url="https://raw.githubusercontent.com/${REPO}/${VERSION}/${source_path}"
  tmpfile="$(mktemp)"

  printf '    %s: fetching %s\n' "$label" "$url"
  if curl -fsSL "$url" -o "$tmpfile"; then
    mkdir -p "$(dirname "$dest_file")"
    mv "$tmpfile" "$dest_file"
    printf '    %s: installed -> %s\n' "$label" "$dest_file"
    return 0
  else
    rm -f "$tmpfile"
    printf '    %s: download failed (url: %s)\n' "$label" "$url" >&2
    return 1
  fi
}

# Claude Code: looks for the `claude` binary or the conventional config dir.
if command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ]; then
  TOOLS_FOUND=$((TOOLS_FOUND + 1))
  if ! download_to "Claude Code" \
      ".claude/skills/${SKILL_NAME}/SKILL.md" \
      "$HOME/.claude/skills/${SKILL_NAME}/SKILL.md"; then
    DOWNLOAD_FAILURES=$((DOWNLOAD_FAILURES + 1))
  fi
fi

# opencode: looks for the `opencode` binary or the XDG config dir
# (same path on Linux and macOS — opencode follows XDG on both).
if command -v opencode >/dev/null 2>&1 || [ -d "$HOME/.config/opencode" ]; then
  TOOLS_FOUND=$((TOOLS_FOUND + 1))
  if ! download_to "opencode" \
      ".opencode/skills/${SKILL_NAME}/SKILL.md" \
      "$HOME/.config/opencode/skills/${SKILL_NAME}/SKILL.md"; then
    DOWNLOAD_FAILURES=$((DOWNLOAD_FAILURES + 1))
  fi
fi

if [ "$TOOLS_FOUND" -eq 0 ]; then
  cat >&2 <<'EOM'

No supported AI assistant detected. Looked for:
  - claude  (Claude Code)        - install: https://docs.claude.com/en/docs/claude-code/getting-started
  - opencode                     - install: https://opencode.ai

Install one and re-run this script.
EOM
  exit 1
fi

if [ "$DOWNLOAD_FAILURES" -eq "$TOOLS_FOUND" ]; then
  printf '\nerror: all detected assistants failed to download the skill.\n' >&2
  printf '       check network and try again, or pin a known-good version with CLAWCTL_VERSION=vXX.Y.Z\n' >&2
  exit 4
fi

# ---------------------------------------------------------------------------
# 3. Install the clawctl-audit companion tool
# ---------------------------------------------------------------------------

AUDIT_DEST="${AUDIT_INSTALL_DIR}/${AUDIT_BIN_NAME}"

if ! download_to "${AUDIT_BIN_NAME}" \
    "scripts/clawctl-audit.py" \
    "$AUDIT_DEST"; then
  printf 'error: failed to install %s\n' "$AUDIT_BIN_NAME" >&2
  exit 5
fi
chmod +x "$AUDIT_DEST"

# Warn if the install dir is not on PATH — the skill drives audit logging
# through this binary, so this is load-bearing.
case ":$PATH:" in
  *":${AUDIT_INSTALL_DIR}:"*) ;;
  *)
    cat >&2 <<EOM

warning: ${AUDIT_INSTALL_DIR} is not on your PATH.
         The /${SKILL_NAME} skill expects ${AUDIT_BIN_NAME} to be runnable as a bare command.
         Add this line to your shell profile (~/.bashrc, ~/.zshrc, etc.):

           export PATH="${AUDIT_INSTALL_DIR}:\$PATH"

         Then open a new shell. Verify with:  ${AUDIT_BIN_NAME} --help
EOM
    ;;
esac

# ---------------------------------------------------------------------------
# 4. Report
# ---------------------------------------------------------------------------

cat <<EOM

Done.
  /${SKILL_NAME} skill is globally available for every detected assistant.
  ${AUDIT_BIN_NAME} installed at ${AUDIT_DEST}

Audit trail will be written to:
  ~/.config/clawrium/changelog/<YYYYMMDD>.jsonl

Verify:
  ${AUDIT_BIN_NAME} --help
  ${AUDIT_BIN_NAME} stats

Open your assistant and type \`/${SKILL_NAME}\` to use it.
EOM
