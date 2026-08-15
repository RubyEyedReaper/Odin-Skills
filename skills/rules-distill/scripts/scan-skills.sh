#!/usr/bin/env bash
# scan-skills.sh — enumerate skill files, extract frontmatter and UTC mtime.
#
# Usage:  scan-skills.sh [SKILLS_DIR]      # default: <repo>/.claude/skills
# Output: JSON to stdout, diagnostics to stderr.
# Exit:   0 with at least one SKILL.md · 1 on a missing or empty target · 2 on a missing dependency.
#
# Fork note (Odin): upstream merged a $HOME/.claude/skills scan with the project one and, when a
# directory held no skills, printed `[]` and exited 0. Pointed at a wrong path it therefore reported
# `{"found":true,"count":0}` — success, having examined nothing (audit F10). That is the failure
# mode both sibling skills name as the worst one, so an empty scan now exits non-zero naming the
# path. Odin vendors its skills into the repository (ADR-0001); the repo tree is the default and the
# only required source.
#
# Environment:
#   RULES_DISTILL_GLOBAL_DIR   additional skills root to merge (optional; absent is fine)
#   RULES_DISTILL_PROJECT_DIR  override the project skills dir (testing)

set -euo pipefail

command -v jq >/dev/null 2>&1 || {
  echo "scan-skills.sh: jq not found — refusing to report an empty scan" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
GLOBAL_DIR="${RULES_DISTILL_GLOBAL_DIR:-}"
SKILLS_DIR="${RULES_DISTILL_PROJECT_DIR:-${1:-$REPO_ROOT/.claude/skills}}"

if [[ ! -d "$SKILLS_DIR" ]]; then
  echo "scan-skills.sh: skills directory not found: $SKILLS_DIR" >&2
  exit 1
fi

# Scan a directory into a JSON array. `find` errors are surfaced, not swallowed — a permission
# error that reads as "no skills here" is the same silent pass in a different costume.
scan_dir_to_json() {
  local dir="$1"
  local tmpdir; tmpdir=$(mktemp -d)
  local _scan_tmpdir="$tmpdir"
  _scan_cleanup() { rm -rf "$_scan_tmpdir"; }
  trap _scan_cleanup RETURN

  local i=0
  while IFS= read -r file; do
    local name desc mtime rel
    name=$(extract_field "$file" "name")
    desc=$(extract_field "$file" "description")
    mtime=$(get_mtime "$file")
    rel="${file#"$REPO_ROOT"/}"

    jq -n \
      --arg path "$rel" \
      --arg name "$name" \
      --arg description "$desc" \
      --arg mtime "$mtime" \
      '{path:$path,name:$name,description:$description,mtime:$mtime}' \
      > "$tmpdir/$i.json"
    i=$((i+1))
  done < <(find "$dir" -name "SKILL.md" -type f | sort)

  if [[ $i -eq 0 ]]; then
    echo "[]"
  else
    jq -s '.' "$tmpdir"/*.json
  fi
}

# Extract a frontmatter field (quoted or unquoted single-line values).
# Does NOT support multi-line YAML blocks (| or >) or nested keys.
extract_field() {
  local file="$1" field="$2"
  awk -v f="$field" '
    BEGIN { fm=0 }
    /^---$/ { fm++; next }
    fm==1 {
      n = length(f) + 2
      if (substr($0, 1, n) == f ": ") {
        val = substr($0, n+1)
        gsub(/^"/, "", val)
        gsub(/"$/, "", val)
        print val
        exit
      }
    }
    fm>=2 { exit }
  ' "$file"
}

# File mtime in UTC ISO8601 (GNU and BSD).
get_mtime() {
  local file="$1" secs
  secs=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null) || return 1
  date -u -d "@$secs" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null ||
  date -u -r "$secs" +%Y-%m-%dT%H:%M:%SZ
}

project_skills=$(scan_dir_to_json "$SKILLS_DIR")
project_count=$(echo "$project_skills" | jq 'length')

if [[ "$project_count" -eq 0 ]]; then
  echo "scan-skills.sh: no SKILL.md under $SKILLS_DIR — an empty corpus is a wrong path, not a clean scan" >&2
  exit 1
fi

global_found="false"
global_count=0
global_skills="[]"
if [[ -n "$GLOBAL_DIR" && -d "$GLOBAL_DIR" ]]; then
  global_found="true"
  global_skills=$(scan_dir_to_json "$GLOBAL_DIR")
  global_count=$(echo "$global_skills" | jq 'length')
fi

all_skills=$(jq -s 'add' <(echo "$global_skills") <(echo "$project_skills"))

jq -n \
  --arg global_found "$global_found" \
  --argjson global_count "$global_count" \
  --arg project_path "${SKILLS_DIR#"$REPO_ROOT"/}" \
  --argjson project_count "$project_count" \
  --argjson skills "$all_skills" \
  '{
    scan_summary: {
      global: { found: ($global_found == "true"), count: $global_count },
      project: { found: true, path: $project_path, count: $project_count }
    },
    skills: $skills
  }'
