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
# What is compared is what git would publish: tracked files plus untracked ones
# that are not ignored (`git ls-files --cached --others --exclude-standard`),
# on each side that is a git work tree. A local eval run's ignored outputs are
# not skill content, and reading them as drift blocked a harness push until
# somebody deleted them by hand (Odin-Skills#11). A side that is not a git work
# tree falls back to every file on disk, and --check says so.
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
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
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
# a drift check gets ignored. Usually git-ignored as well; excluded here too so
# the fallback without git agrees.
is_excluded() {
  case "/$1" in
    */UPSTREAM.md|*/LICENSE|*/NOTICE|*/.DS_Store|*.pyc|*/__pycache__/*) return 0 ;;
  esac
  return 1
}

# content_files <dir> — sorted paths, relative to <dir>, of the files that are
# skill content: what git would publish when <dir> is in a work tree, every file
# otherwise. A path git still indexes but the work tree has lost is left out, so
# a deletion reads as drift rather than as a copy of nothing.
content_files() {
  local dir="$1" rel
  if git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$dir" ls-files --cached --others --exclude-standard
  else
    (cd "$dir" && find . -type f | sed 's|^\./||')
  fi | while IFS= read -r rel; do
    [[ -f "$dir/$rel" ]] && ! is_excluded "$rel" && printf '%s\n' "$rel"
  done | LC_ALL=C sort -u
}

FALLBACK_NOTED=0
note_fallback() {
  git -C "$1" rev-parse --is-inside-work-tree >/dev/null 2>&1 && return
  [[ $FALLBACK_NOTED -eq 1 ]] && return
  echo "note: $1 is not a git work tree; comparing every file on disk, ignored or not" >&2
  FALLBACK_NOTED=1
}

# differences <src> <dst> — one line per path that differs; nothing when in sync.
differences() {
  local src="$1" dst="$2" rel
  local a b
  a="$(content_files "$src")"
  b="$(content_files "$dst")"
  LC_ALL=C comm -23 <(printf '%s\n' "$a" | sed '/^$/d') <(printf '%s\n' "$b" | sed '/^$/d') | sed 's/^/only in the harness: /'
  LC_ALL=C comm -13 <(printf '%s\n' "$a" | sed '/^$/d') <(printf '%s\n' "$b" | sed '/^$/d') | sed 's/^/only in the mirror:  /'
  LC_ALL=C comm -12 <(printf '%s\n' "$a" | sed '/^$/d') <(printf '%s\n' "$b" | sed '/^$/d') | while IFS= read -r rel; do
    cmp -s "$src/$rel" "$dst/$rel" || printf 'differs:             %s\n' "$rel"
  done
}

for name in "${MEMBERS[@]}"; do
  src="$SRC/$name"
  dst="$ROOT/skills/$name"

  if [[ ! -d "$src" ]]; then
    echo "DRIFT: $name is a member here but no longer exists in the harness"
    DRIFTED=$((DRIFTED + 1))
    continue
  fi

  note_fallback "$src"
  note_fallback "$dst"
  diffs="$(differences "$src" "$dst")"
  [[ -z "$diffs" ]] && continue

  if [[ $CHECK -eq 1 ]]; then
    echo "DRIFT: $name differs from the harness copy"
    printf '%s\n' "$diffs" | sed 's/^/       /'
    DRIFTED=$((DRIFTED + 1))
    continue
  fi

  # Copy content, then restore the packaging files this repository owns.
  tmp="$(mktemp -d)"
  [[ -f "$dst/UPSTREAM.md" ]] && cp "$dst/UPSTREAM.md" "$tmp/"
  [[ -f "$dst/LICENSE" ]] && cp "$dst/LICENSE" "$tmp/"
  [[ -f "$dst/NOTICE" ]] && cp "$dst/NOTICE" "$tmp/"
  files="$(content_files "$src")"
  rm -rf "$dst"
  mkdir -p "$dst"
  while IFS= read -r rel; do
    [[ -n "$rel" ]] || continue
    mkdir -p "$dst/$(dirname "$rel")"
    cp -p "$src/$rel" "$dst/$rel"
  done <<<"$files"
  [[ -f "$tmp/UPSTREAM.md" ]] && cp "$tmp/UPSTREAM.md" "$dst/"
  [[ -f "$tmp/LICENSE" ]] && cp "$tmp/LICENSE" "$dst/"
  [[ -f "$tmp/NOTICE" ]] && cp "$tmp/NOTICE" "$dst/"
  rm -rf "$tmp"
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
