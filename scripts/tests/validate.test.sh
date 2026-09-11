#!/usr/bin/env bash
# validate.test.sh — proves every check in validate-skills.sh actually fires.
#
# Each case builds a synthetic repo root that violates exactly ONE rule, then
# asserts the validator exits non-zero AND names that rule. A check that cannot
# fail is not a check, so the clean-tree case asserting exit 0 matters just as
# much as the failing ones.
#
# Run: bash scripts/tests/validate.test.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATOR="$HERE/../validate-skills.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

PASS=0
FAIL=0

# fixture <name> -> builds a minimal VALID repo at $TMPROOT/<name>, echoes path.
# One authored skill (alpha) and one fork (beta) is the smallest tree that
# exercises both the authored and the fork branches of every check.
fixture() {
  local root="$TMPROOT/$1"
  mkdir -p "$root/.claude-plugin" "$root/skills/alpha" "$root/skills/beta" "$root/docs"

  printf -- '---\nname: alpha\ndescription: Use when testing the validator.\n---\n\nBody.\n' \
    > "$root/skills/alpha/SKILL.md"
  printf -- '---\nname: beta\ndescription: Use when testing the fork branch.\n---\n\nBody.\n' \
    > "$root/skills/beta/SKILL.md"

  printf 'MIT License\n' > "$root/skills/beta/LICENSE"
  printf '# Upstream: beta\n\nChanges made by Odin: none yet.\n' > "$root/skills/beta/UPSTREAM.md"

  cat > "$root/.claude-plugin/plugin.json" <<'JSON'
{
  "name": "odin-skills",
  "version": "0.1.0",
  "skills": ["./skills/alpha", "./skills/beta"]
}
JSON

  printf '# Provenance\n\n| Skill | Origin |\n|---|---|\n| `alpha` | odin-authored |\n| `beta` | fork |\n' \
    > "$root/docs/PROVENANCE.md"

  printf 'MIT\n' > "$root/LICENSE-MIT"
  printf 'CC-BY-SA-4.0\n' > "$root/LICENSE-CC-BY-SA-4.0"

  echo "$root"
}

# expect_fail <case-name> <expected-substring> <root>
expect_fail() {
  local name="$1" want="$2" root="$3" out rc
  out="$(bash "$VALIDATOR" --root "$root" 2>&1)"
  rc=$?
  if [[ $rc -eq 0 ]]; then
    echo "  FAIL  $name — validator exited 0, expected non-zero"
    FAIL=$((FAIL + 1))
    return
  fi
  if ! grep -qF "$want" <<<"$out"; then
    echo "  FAIL  $name — exited $rc but never said '$want'"
    echo "$out" | sed 's/^/          /'
    FAIL=$((FAIL + 1))
    return
  fi
  echo "  ok    $name"
  PASS=$((PASS + 1))
}

expect_pass() {
  local name="$1" root="$2" out rc
  out="$(bash "$VALIDATOR" --root "$root" 2>&1)"
  rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "  FAIL  $name — expected exit 0, got $rc"
    echo "$out" | sed 's/^/          /'
    FAIL=$((FAIL + 1))
    return
  fi
  echo "  ok    $name"
  PASS=$((PASS + 1))
}

echo "validate-skills.sh matrix"

# --- clean tree -------------------------------------------------------------
r="$(fixture clean)"
expect_pass "clean tree passes" "$r"

# --- check 1: SKILL.md present and frontmatter complete ---------------------
r="$(fixture no-skillmd)"; rm "$r/skills/alpha/SKILL.md"
expect_fail "missing SKILL.md" "missing SKILL.md" "$r"

r="$(fixture no-name)"
printf -- '---\ndescription: Use when a name is absent.\n---\n' > "$r/skills/alpha/SKILL.md"
expect_fail "frontmatter without name" "missing frontmatter 'name'" "$r"

r="$(fixture no-desc)"
printf -- '---\nname: alpha\n---\n' > "$r/skills/alpha/SKILL.md"
expect_fail "frontmatter without description" "missing frontmatter 'description'" "$r"

# --- check 2: name matches directory ----------------------------------------
r="$(fixture name-mismatch)"
printf -- '---\nname: not-alpha\ndescription: Use when the name lies.\n---\n' \
  > "$r/skills/alpha/SKILL.md"
expect_fail "name does not match directory" "name 'not-alpha' does not match" "$r"

# --- check 3: description length --------------------------------------------
r="$(fixture desc-too-long)"
long="$(head -c 1100 < /dev/zero | tr '\0' 'x')"
printf -- '---\nname: alpha\ndescription: %s\n---\n' "$long" > "$r/skills/alpha/SKILL.md"
expect_fail "description over 1024 chars" "description too long" "$r"

# --- check 4: plugin.json parity, both directions ---------------------------
r="$(fixture manifest-missing-skill)"
cat > "$r/.claude-plugin/plugin.json" <<'JSON'
{"name":"odin-skills","version":"0.1.0","skills":["./skills/alpha"]}
JSON
expect_fail "skill on disk absent from manifest" "not listed in plugin.json" "$r"

r="$(fixture manifest-extra-skill)"
cat > "$r/.claude-plugin/plugin.json" <<'JSON'
{"name":"odin-skills","version":"0.1.0","skills":["./skills/alpha","./skills/beta","./skills/ghost"]}
JSON
expect_fail "manifest lists a skill not on disk" "listed in plugin.json but missing" "$r"

# --- check 5: root licensing -------------------------------------------------
r="$(fixture no-mit)"; rm "$r/LICENSE-MIT"
expect_fail "missing LICENSE-MIT" "LICENSE-MIT" "$r"

r="$(fixture bare-license)"; printf 'x\n' > "$r/LICENSE"
expect_fail "bare root LICENSE present" "bare LICENSE" "$r"

# --- check 6: fork completeness ---------------------------------------------
r="$(fixture fork-no-upstream)"; rm "$r/skills/beta/UPSTREAM.md"
expect_fail "fork with LICENSE but no UPSTREAM.md" "UPSTREAM.md" "$r"

r="$(fixture fork-no-license)"; rm "$r/skills/beta/LICENSE"
expect_fail "fork with UPSTREAM.md but no LICENSE" "LICENSE" "$r"

# A fork that declares upstream shipped no license, and carries a NOTICE, passes.
r="$(fixture fork-declared-no-license)"; rm "$r/skills/beta/LICENSE"
printf 'no LICENSE file accompanied the vendored copy\n' >> "$r/skills/beta/UPSTREAM.md"
printf 'Upstream shipped no LICENSE; provenance is recorded in PROVENANCE.md\n' > "$r/skills/beta/NOTICE"
expect_pass "fork declaring no upstream license, with NOTICE" "$r"

# The declaration alone is not enough — the NOTICE has to exist.
r="$(fixture fork-declared-no-notice)"; rm "$r/skills/beta/LICENSE"
printf 'no LICENSE file accompanied the vendored copy\n' >> "$r/skills/beta/UPSTREAM.md"
expect_fail "fork declaring no upstream license without NOTICE" "ships no NOTICE" "$r"

# A NOTICE without the declaration must NOT substitute for a real upstream license.
r="$(fixture fork-notice-no-declaration)"; rm "$r/skills/beta/LICENSE"
printf 'Some notice text\n' > "$r/skills/beta/NOTICE"
expect_fail "fork with NOTICE but no declaration" "no upstream LICENSE file" "$r"

# --- check 7: provenance coverage -------------------------------------------
r="$(fixture no-provenance-row)"
printf '# Provenance\n\n| `alpha` | odin-authored |\n' > "$r/docs/PROVENANCE.md"
expect_fail "skill absent from PROVENANCE" "not documented in docs/PROVENANCE.md" "$r"

# --- check 11: PROVENANCE.md headings carry no standing count ---------------
r="$(fixture provenance-heading-count)"
printf '# Provenance\n\n## Odin-authored (9)\n\n| `alpha` | odin-authored |\n\n## Forks (10)\n\n| `beta` | fork |\n' \
  > "$r/docs/PROVENANCE.md"
expect_fail "PROVENANCE heading carries a standing count" "standing count" "$r"

# a dated measurement in prose (not a heading) is not a standing count
r="$(fixture provenance-dated-measurement)"
printf '# Provenance\n\nMirrors 27 of 122 (measured 2026-09-04).\n\n| `alpha` | odin-authored |\n| `beta` | fork |\n' \
  > "$r/docs/PROVENANCE.md"
expect_pass "PROVENANCE dated prose measurement passes" "$r"

# a heading date, e.g. "### Decision — ... (2026-08-17)", is not a bare-integer count
r="$(fixture provenance-heading-date)"
printf '# Provenance\n\n### Decision — something (2026-08-17)\n\n| `alpha` | odin-authored |\n| `beta` | fork |\n' \
  > "$r/docs/PROVENANCE.md"
expect_pass "PROVENANCE heading with a date passes" "$r"

# --- check 12: a live published doc states the mirror's size in prose --------
#
# Each BLOCK case is a REAL site this campaign repaired (#1238-#1241). The ALLOW
# cases are the near misses that must keep passing, and they carry the weight:
# a detector over prose that fires on a history entry or a numbered list is the
# one that gets the whole gate disabled. A broader first draft matched 82 lines
# in 5969 and was discarded rather than tuned.

r="$(fixture readme-typed-count)"
printf '# Odin Skills\n\n**Authored here (7)** — `alpha`\n' > "$r/README.md"
expect_fail "README states the authored count in prose" "standing number" "$r"

r="$(fixture readme-typed-count-parenthesised)"
printf '# Odin Skills\n\n**Forked and modified (10)** — `beta`\n' > "$r/README.md"
expect_fail "README states the fork count behind intervening words" "standing number" "$r"

r="$(fixture publishing-typed-count)"
mkdir -p "$r/docs"
printf '# Publishing\n\nOf the 17 published skills, 7 are Odin own.\n' > "$r/docs/PUBLISHING.md"
expect_fail "PUBLISHING states the split in prose" "standing number" "$r"

r="$(fixture provenance-undated-subtraction)"
printf '# Provenance\n\n84 = the harness 122 skill directories minus the 38 here.\n\n| `alpha` | odin-authored |\n| `beta` | fork |\n' \
  > "$r/docs/PROVENANCE.md"
expect_fail "PROVENANCE subtraction with no date" "standing number" "$r"

# ALLOW: a dated measurement whose date WRAPS onto the next line. The first
# version of this check was line-scoped and reported the shipped PROVENANCE.md
# as a finding for exactly this reason.
r="$(fixture provenance-wrapped-date)"
printf '# Provenance\n\n88 = the harness 127 skill directories minus the 39 mirrored here;\nmeasured 2026-09-11, not inherited.\n\n| `alpha` | odin-authored |\n| `beta` | fork |\n' \
  > "$r/docs/PROVENANCE.md"
expect_pass "a dated measurement whose date wraps passes" "$r"

# ALLOW: a fenced block is sample output, not a claim about this tree.
r="$(fixture readme-count-in-fence)"
printf '# Odin Skills\n\n```sh\nls -d skills/*/ | wc -l   # 39 skills\n```\n' > "$r/README.md"
expect_pass "a count inside a fenced block passes" "$r"

# ALLOW: an inline-code span is an identifier, not a statement (C-0013's lesson).
r="$(fixture readme-count-in-code-span)"
printf '# Odin Skills\n\nRun `ls -d skills/*/ | wc -l` — never 39 skills typed out.\n' > "$r/README.md"
expect_fail "prose beside a code span is still checked" "standing number" "$r"

# ALLOW: the CHANGELOG is history. An entry recording that the mirror once held
# 17 skills is correct forever, and firing on it is how a gate gets disabled.
r="$(fixture changelog-history-count)"
printf '# Changelog\n\n- Initial repository: the 12 skills Odin authored (5) or forked (7).\n' > "$r/CHANGELOG.md"
expect_pass "a count in CHANGELOG history passes" "$r"

# --- check 8: dangling symlinks ---------------------------------------------
r="$(fixture dangling-symlink)"
ln -s ../../nowhere/data "$r/skills/alpha/data"
expect_fail "dangling symlink in a skill" "dangling symlink" "$r"

# --- check 9: unreachable references ----------------------------------------
r="$(fixture orphan-reference)"
mkdir -p "$r/skills/alpha/references"
printf 'orphan\n' > "$r/skills/alpha/references/nobody-links-me.md"
expect_fail "reference unreachable from SKILL.md" "unreachable from SKILL.md" "$r"

# a reference reached only via another reference is NOT an orphan
r="$(fixture transitive-reference)"
mkdir -p "$r/skills/alpha/references"
printf 'see [hop](references/hop.md)\n' >> "$r/skills/alpha/SKILL.md"
printf 'see [leaf](leaf.md)\n' > "$r/skills/alpha/references/hop.md"
printf 'leaf\n' > "$r/skills/alpha/references/leaf.md"
expect_pass "transitively reachable reference passes" "$r"

echo
echo "passed: $PASS   failed: $FAIL"
[[ $FAIL -eq 0 ]]
