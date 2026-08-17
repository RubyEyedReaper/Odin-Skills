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
