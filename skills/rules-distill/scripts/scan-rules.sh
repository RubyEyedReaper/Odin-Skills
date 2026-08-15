#!/usr/bin/env bash
# scan-rules.sh — enumerate rule files and extract their H2 heading index.
#
# Usage:  scan-rules.sh [RULES_DIR]        # default: <repo>/.claude/rules
# Output: JSON to stdout, diagnostics to stderr.
# Exit:   0 with at least one rule file · 1 on a missing, empty, or unreadable target · 2 on a
#         missing dependency.
#
# Fork note (Odin): upstream defaulted to $HOME/.claude/rules and printed `~/`-prefixed paths. Odin
# vendors its rules into the repository (ADR-0001), so that default resolved to nothing and the
# skill's first documented command failed — for 49 days, in a skill nobody could start. The default
# is the repository's own tree, and paths are printed repo-relative so they can be opened.
#
# An empty scan is an ERROR, never `{"total":0}` with exit 0: a scanner reporting success having
# examined nothing is indistinguishable from one that agrees with everything (audit F10).

set -euo pipefail

command -v jq >/dev/null 2>&1 || {
  echo "scan-rules.sh: jq not found — refusing to report an empty scan" >&2; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
RULES_DIR="${RULES_DISTILL_DIR:-${1:-$REPO_ROOT/.claude/rules}}"

if [[ ! -d "$RULES_DIR" ]]; then
  echo "scan-rules.sh: rules directory not found: $RULES_DIR" >&2
  exit 1
fi

files=()
while IFS= read -r f; do
  files+=("$f")
done < <(find "$RULES_DIR" -name '*.md' -not -path '*/_archived/*' -print | sort)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "scan-rules.sh: no rule files under $RULES_DIR — an empty corpus is a wrong path, not a clean scan" >&2
  exit 1
fi

total=${#files[@]}

tmpdir=$(mktemp -d)
_rules_cleanup() { rm -rf "$tmpdir"; }
trap _rules_cleanup EXIT

for i in "${!files[@]}"; do
  file="${files[$i]}"
  rel_path="${file#"$REPO_ROOT"/}"

  headings_json=$({ grep -E '^## ' "$file" 2>/dev/null || true; } | sed 's/^## //' | jq -R . | jq -s '.')
  line_count=$(wc -l < "$file" | tr -d ' ')
  # `paths:` in frontmatter is what makes a rule conditional; without it the file is always-on and
  # costs context on every turn of every session. The distiller must see the tier to decide one.
  tier=$(head -5 "$file" | grep -q '^paths:' && echo scoped || echo always-on)

  jq -n \
    --arg path "$rel_path" \
    --arg file "$(basename "$file")" \
    --arg tier "$tier" \
    --argjson lines "$line_count" \
    --argjson headings "$headings_json" \
    '{path:$path,file:$file,tier:$tier,lines:$lines,headings:$headings}' \
    > "$tmpdir/$i.json"
done

jq -n \
  --arg dir "${RULES_DIR#"$REPO_ROOT"/}" \
  --argjson total "$total" \
  --argjson rules "$(jq -s '.' "$tmpdir"/*.json)" \
  '{rules_dir:$dir,total:$total,rules:$rules}'
