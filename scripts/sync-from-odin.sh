#!/usr/bin/env bash
# sync-from-odin.sh — one-way mirror of member skills from the Odin harness.
#
# .claude/skills/ in the Odin harness is authoritative; this repository is a
# published mirror of the subset Odin authored or forked. Sync only ever runs in
# that direction, because Odin commits its skills to survive container resets and
# so cannot take delivery from here.
#
# Files this repository adds per skill — UPSTREAM.md, the upstream LICENSE, and
# the NOTICE a fork ships when no upstream LICENSE exists — are preserved: they
# are packaging, not skill content, and the harness has no copy of them to sync
# back. All three are gate inputs, so losing one here re-reddens validate-skills.sh.
#
# Usage:
#   scripts/sync-from-odin.sh [--odin DIR]           copy harness -> skills/
#   scripts/sync-from-odin.sh --check [--odin DIR]   report drift, change nothing
#
# Exit: 0 in sync (or copy succeeded), 1 on drift under --check, 2 on bad usage.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ODIN=""
CHECK=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK=1; shift ;;
    --odin) ODIN="$2"; shift 2 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# Default: this repo lives at <odin>/projects/Odin-Skills, so the harness is two
# levels up. An extracted standalone clone has no such parent and must say where.
if [[ -z "$ODIN" ]]; then
  ODIN="$(cd "$ROOT/../.." 2>/dev/null && pwd)"
fi

SRC="$ODIN/.claude/skills"
if [[ ! -d "$SRC" ]]; then
  echo "error: no Odin skills directory at $SRC" >&2
  echo "       pass --odin /path/to/Odin when running outside the harness checkout" >&2
  exit 2
fi

# Members are whatever this repository already ships. Adding a member is a
# deliberate act with a PROVENANCE row and a manifest entry (see CONTRIBUTING.md),
# never a side effect of a sync.
MEMBERS=()
for dir in "$ROOT/skills"/*/; do
  [[ -d "$dir" ]] && MEMBERS+=("$(basename "$dir")")
done

if [[ ${#MEMBERS[@]} -eq 0 ]]; then
  echo "error: no member skills in $ROOT/skills" >&2
  exit 2
fi

DRIFTED=0
COPIED=0

# UPSTREAM.md, LICENSE and NOTICE are this repository's own packaging, not skill
# content — three files, not two: a fork whose upstream published no LICENSE
# declares that in UPSTREAM.md and substantiates it with NOTICE, and check 6 of
# validate-skills.sh reads both. Omitting NOTICE here reports permanent drift and
# then deletes the file on the next real sync.
# __pycache__/*.pyc are build residue that appears in the harness the moment a
# skill's tests are run — comparing it reports drift nobody caused, which is how
# a drift check gets ignored.
EXCLUDE=(-x UPSTREAM.md -x LICENSE -x NOTICE -x __pycache__ -x '*.pyc' -x .DS_Store)

for name in "${MEMBERS[@]}"; do
  src="$SRC/$name"
  dst="$ROOT/skills/$name"

  if [[ ! -d "$src" ]]; then
    echo "DRIFT: $name is a member here but no longer exists in the harness"
    DRIFTED=$((DRIFTED + 1))
    continue
  fi

  # Packaging files are ours; everything else must match the harness exactly.
  if diff -r -q "${EXCLUDE[@]}" -- "$src" "$dst" >/dev/null 2>&1; then
    continue
  fi

  if [[ $CHECK -eq 1 ]]; then
    echo "DRIFT: $name differs from the harness copy"
    diff -r -q "${EXCLUDE[@]}" -- "$src" "$dst" 2>&1 | sed 's/^/       /'
    DRIFTED=$((DRIFTED + 1))
    continue
  fi

  # Copy content, then restore the packaging files this repository owns.
  tmp="$(mktemp -d)"
  [[ -f "$dst/UPSTREAM.md" ]] && cp "$dst/UPSTREAM.md" "$tmp/"
  [[ -f "$dst/LICENSE" ]] && cp "$dst/LICENSE" "$tmp/"
  [[ -f "$dst/NOTICE" ]] && cp "$dst/NOTICE" "$tmp/"
  rm -rf "$dst"
  cp -R "$src" "$dst"
  [[ -f "$tmp/UPSTREAM.md" ]] && cp "$tmp/UPSTREAM.md" "$dst/"
  [[ -f "$tmp/LICENSE" ]] && cp "$tmp/LICENSE" "$dst/"
  [[ -f "$tmp/NOTICE" ]] && cp "$tmp/NOTICE" "$dst/"
  rm -rf "$tmp"
  # cp -R carries whatever residue the harness had; drop it so the mirror never
  # publishes build artefacts of someone else's test run.
  find "$dst" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  find "$dst" \( -name '*.pyc' -o -name .DS_Store \) -delete 2>/dev/null
  echo "synced: $name"
  COPIED=$((COPIED + 1))
done

if [[ $CHECK -eq 1 ]]; then
  if [[ $DRIFTED -gt 0 ]]; then
    echo
    echo "$DRIFTED skill(s) have drifted from the harness. Run scripts/sync-from-odin.sh to update."
    exit 1
  fi
  echo "OK: ${#MEMBERS[@]} skills in sync with $SRC"
  exit 0
fi

echo "OK: ${#MEMBERS[@]} members checked, $COPIED updated."
