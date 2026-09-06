#!/usr/bin/env bash
# leek-scan.sh — the entry point SKILL.md and CI cite.
#
# A thin shim on purpose. All analysis lives in leek.py so that the read-only
# invariant and the finding schema are properties of ONE file the matrix can
# pin (ADR-0088); a second implementation here would be a second thing to prove.
#
# Resolve the module from this script's own location, never from `pwd` — a hook
# or a prior command may have left the working directory somewhere else
# entirely (ADR-0032).
#
# Exit codes pass through unchanged: 0 no findings, 1 findings, 2 usage error.
#
#   leek-scan.sh                          # every family, text report
#   leek-scan.sh --json                   # same, as JSON
#   leek-scan.sh --check memory,isolation # two families
#   leek-scan.sh --check skills-unused    # which skills have never been used
#   leek-scan.sh --min-severity high      # critical + high only
#
# Paths outside the repository are reached only through these overrides, which
# is what lets the matrix point the whole scanner at a fixture tree:
#   LEEK_ROOT  LEEK_CLAUDE_HOME  LEEK_MEM_DB  LEEK_TRANSCRIPT_DIR  LEEK_PROC_CMD

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "leek: python3 not found — the scanner cannot run." >&2
  echo "  A scan that cannot look must not report a clean host." >&2
  exit 2
fi

exec python3 "$SCRIPT_DIR/leek.py" "$@"
