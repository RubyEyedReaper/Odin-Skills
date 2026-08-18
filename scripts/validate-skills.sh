#!/usr/bin/env bash
# validate-skills.sh — the gate for this repository.
#
# Ten checks, each one a mistake that is otherwise silent until an installer
# hits it: a skill whose frontmatter name does not match its directory is simply
# never invocable, a manifest that has drifted from disk installs nothing, a
# fork missing its upstream LICENSE is a license violation rather than a typo,
# and a doc linking a repository that is not public 404s for every visitor.
#
# Usage: scripts/validate-skills.sh [--root DIR]
# Exit:  0 clean, 1 with one 'FAIL: <reason>' line per violation.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

FAILURES=0
fail() { echo "FAIL: $*"; FAILURES=$((FAILURES + 1)); }

SKILLS_DIR="$ROOT/skills"
PLUGIN_JSON="$ROOT/.claude-plugin/plugin.json"
PROVENANCE="$ROOT/docs/PROVENANCE.md"
MAX_DESC=1024

[[ -d "$SKILLS_DIR" ]] || { fail "no skills/ directory at $ROOT"; exit 1; }

# frontmatter_field <file> <key> — value of a top-level YAML key in the leading
# --- block. Folded continuation lines are joined so a wrapped description is
# measured at its true length rather than its first line.
frontmatter_field() {
  awk -v key="$2" '
    NR == 1 && $0 != "---" { exit }
    NR == 1 { next }
    $0 == "---" { exit }
    {
      if ($0 ~ "^" key ":") { found = 1; sub("^" key ":[ \t]*", ""); val = $0; next }
      if (found && $0 ~ /^[ \t]+[^ \t]/) { sub(/^[ \t]+/, " "); val = val $0; next }
      if (found) { exit }
    }
    END { if (found) print val }
  ' "$1"
}

# ---------------------------------------------------------------------------
# Checks 1-3, 6: per-skill
# ---------------------------------------------------------------------------
SKILL_DIRS=()
for dir in "$SKILLS_DIR"/*/; do
  [[ -d "$dir" ]] || continue
  name="$(basename "$dir")"
  SKILL_DIRS+=("$name")

  skill_md="$dir/SKILL.md"
  if [[ ! -f "$skill_md" ]]; then
    fail "$name: missing SKILL.md"
    continue
  fi

  fm_name="$(frontmatter_field "$skill_md" name)"
  fm_desc="$(frontmatter_field "$skill_md" description)"

  if [[ -z "$fm_name" ]]; then
    fail "$name: missing frontmatter 'name'"
  elif [[ "$fm_name" != "$name" ]]; then
    fail "$name: frontmatter name '$fm_name' does not match directory name '$name'"
  fi

  if [[ -z "$fm_desc" ]]; then
    fail "$name: missing frontmatter 'description'"
  elif [[ ${#fm_desc} -gt $MAX_DESC ]]; then
    fail "$name: description too long (${#fm_desc} chars, max $MAX_DESC)"
  fi

  # A fork is any skill carrying either upstream artefact. Carrying one without
  # the other is the actual hazard: an UPSTREAM.md with no LICENSE ships someone
  # else's work with no license text, and a LICENSE with no UPSTREAM.md fails
  # Apache-2.0's requirement to state modifications.
  #
  # One case is neither: an upstream that published no LICENSE file at all. That
  # absence cannot be fixed by shipping a license nobody granted, so the fork
  # declares it — the literal string 'no LICENSE file accompanied' in UPSTREAM.md
  # — and substantiates it with a sibling NOTICE carrying the provenance. Both
  # artefacts are required, and neither alone passes: a declaration without a
  # NOTICE states a fact it never records, and a NOTICE without the declaration
  # would let any ordinary fork skip the license it does have.
  has_license=0; [[ -f "$dir/LICENSE" ]] && has_license=1
  has_upstream=0; [[ -f "$dir/UPSTREAM.md" ]] && has_upstream=1
  has_notice=0;  [[ -f "$dir/NOTICE"  ]] && has_notice=1
  declares_none=0
  if [[ $has_upstream -eq 1 ]] && grep -qF 'no LICENSE file accompanied' "$dir/UPSTREAM.md"; then
    declares_none=1
  fi

  if [[ $has_license -eq 1 && $has_upstream -eq 0 ]]; then
    fail "$name: has upstream LICENSE but no UPSTREAM.md stating the local changes"
  fi
  if [[ $has_upstream -eq 1 && $has_license -eq 0 ]]; then
    if [[ $declares_none -eq 1 && $has_notice -eq 1 ]]; then
      : # declared absence, substantiated by a NOTICE — see docs/PROVENANCE.md
    elif [[ $declares_none -eq 1 ]]; then
      fail "$name: UPSTREAM.md declares no upstream license but ships no NOTICE"
    else
      fail "$name: has UPSTREAM.md but no upstream LICENSE file"
    fi
  fi
done

if [[ ${#SKILL_DIRS[@]} -eq 0 ]]; then
  fail "skills/ contains no skill directories"
fi

# ---------------------------------------------------------------------------
# Check 4: plugin.json parity, both directions
# ---------------------------------------------------------------------------
if [[ ! -f "$PLUGIN_JSON" ]]; then
  fail "missing .claude-plugin/plugin.json"
else
  if ! manifest_skills="$(python3 -c '
import json, sys
data = json.load(open(sys.argv[1]))
for entry in data.get("skills", []):
    print(entry.rstrip("/").split("/")[-1])
' "$PLUGIN_JSON" 2>&1)"; then
    fail "plugin.json is not valid JSON: $manifest_skills"
    manifest_skills=""
  fi

  for name in "${SKILL_DIRS[@]}"; do
    grep -qx "$name" <<<"$manifest_skills" || fail "$name: on disk but not listed in plugin.json"
  done

  while IFS= read -r listed; do
    [[ -n "$listed" ]] || continue
    [[ -d "$SKILLS_DIR/$listed" ]] || fail "$listed: listed in plugin.json but missing from skills/"
  done <<<"$manifest_skills"
fi

# ---------------------------------------------------------------------------
# Check 5: root licensing
# ---------------------------------------------------------------------------
[[ -f "$ROOT/LICENSE-MIT" ]] || fail "missing LICENSE-MIT at repository root"
[[ -f "$ROOT/LICENSE-CC-BY-SA-4.0" ]] || fail "missing LICENSE-CC-BY-SA-4.0 at repository root"
if [[ -f "$ROOT/LICENSE" ]]; then
  fail "bare LICENSE at repository root — this repo uses split licensing, and one file cannot describe it"
fi

# ---------------------------------------------------------------------------
# Check 7: provenance coverage
# ---------------------------------------------------------------------------
if [[ ! -f "$PROVENANCE" ]]; then
  fail "missing docs/PROVENANCE.md"
else
  for name in "${SKILL_DIRS[@]}"; do
    grep -qF "\`$name\`" "$PROVENANCE" || fail "$name: not documented in docs/PROVENANCE.md"
  done
fi

# ---------------------------------------------------------------------------
# Check 8: dangling symlinks
# ---------------------------------------------------------------------------
while IFS= read -r link; do
  [[ -n "$link" ]] || continue
  fail "dangling symlink: ${link#$ROOT/} -> $(readlink "$link")"
done < <(find "$SKILLS_DIR" -type l ! -exec test -e {} \; -print 2>/dev/null)

# ---------------------------------------------------------------------------
# Check 9: references reachable from SKILL.md
#
# Transitive: a reference linked only from another reference is reachable. Only
# references/ is walked — a skill using a different directory name is making its
# own arrangement and is not held to this rule.
# ---------------------------------------------------------------------------
while IFS= read -r line; do
  [[ -n "$line" ]] || continue
  fail "$line"
done < <(python3 - "$SKILLS_DIR" <<'PY'
import os, sys

skills_dir = sys.argv[1]
for name in sorted(os.listdir(skills_dir)):
    refs_dir = os.path.join(skills_dir, name, "references")
    if not os.path.isdir(refs_dir):
        continue
    files = {f for f in os.listdir(refs_dir) if f.endswith(".md")}
    reached, frontier = set(), [os.path.join(skills_dir, name, "SKILL.md")]
    while frontier:
        try:
            text = open(frontier.pop(), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for f in files - reached:
            if f in text:
                reached.add(f)
                frontier.append(os.path.join(refs_dir, f))
    for orphan in sorted(files - reached):
        print(f"{name}: references/{orphan} is unreachable from SKILL.md")
PY
)

# ---------------------------------------------------------------------------
# Check 10: published docs link only where a visitor can go
#
# Delegated to scripts/check-doc-links.sh, which keeps its own exit codes and
# its own matrix. Wiring it HERE rather than into .github/workflows/validate.yml
# is deliberate: that workflow already runs this script, and it must stay
# workflow_dispatch-only while this directory lives inside the Odin monorepo.
# ---------------------------------------------------------------------------
DOC_LINKS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/check-doc-links.sh"
if [[ ! -f "$DOC_LINKS" ]]; then
  fail "missing scripts/check-doc-links.sh"
else
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    fail "${line#FAIL: }"
  done < <(bash "$DOC_LINKS" --root "$ROOT" | grep '^FAIL: ')
fi

# ---------------------------------------------------------------------------
if [[ $FAILURES -gt 0 ]]; then
  echo
  echo "$FAILURES check(s) failed."
  exit 1
fi
echo "OK: ${#SKILL_DIRS[@]} skills validated."
