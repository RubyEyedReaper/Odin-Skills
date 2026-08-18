#!/usr/bin/env bash
# doc-links.test.sh — proves check-doc-links.sh refuses the link that shipped.
#
# The incident: this repository is public and was tagged v0.1.0 with five links
# to https://github.com/RubyEyedReaper/Odin, which is private. Every one of them
# is a 404 for every visitor. The first BLOCK case below is that exact string.
#
# Each case builds a synthetic tree violating (or deliberately not violating)
# exactly one thing, runs the checker, and asserts its EXIT CODE and its output.
# Nothing here greps the checker's source: a source-grep stays green through a
# rename of the very thing it checks.
#
# Run: bash scripts/tests/doc-links.test.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKER="$HERE/../check-doc-links.sh"
VALIDATOR="$HERE/../validate-skills.sh"
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

PASS=0
FAIL=0

ok()  { echo "  ok    $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $1"; [[ -n "${2:-}" ]] && sed 's/^/          /' <<<"$2"; FAIL=$((FAIL + 1)); }

# fixture <name> -> builds a tree with a valid allowlist and one clean doc,
# echoes its path. Cases add or overwrite documents from there.
fixture() {
  local root="$TMPROOT/$1"
  mkdir -p "$root/scripts" "$root/docs"
  cat > "$root/scripts/public-repos.txt" <<'LIST'
# repositories this tree may link to
RubyEyedReaper/Odin-Skills
obra/superpowers
LIST
  printf '# Doc\n\nInstall from <https://github.com/RubyEyedReaper/Odin-Skills>.\n' \
    > "$root/README.md"
  echo "$root"
}

# expect_exit <case> <want-code> <want-substring|-> <args...>
expect_exit() {
  local name="$1" want="$2" substr="$3"; shift 3
  local out rc
  out="$(bash "$CHECKER" "$@" 2>&1)"
  rc=$?
  if [[ $rc -ne $want ]]; then
    bad "$name — expected exit $want, got $rc" "$out"
    return
  fi
  if [[ "$substr" != "-" ]] && ! grep -qF "$substr" <<<"$out"; then
    bad "$name — exited $rc but never said '$substr'" "$out"
    return
  fi
  ok "$name"
}

echo "check-doc-links.sh matrix"

# --- the clean tree ---------------------------------------------------------
r="$(fixture clean)"
expect_exit "allowlisted link passes" 0 - --root "$r"

# --- THE INCIDENT -----------------------------------------------------------
# The literal artifact from README.md:3 of the published tree at v0.1.0.
r="$(fixture the-incident)"
printf 'The skills the [Odin](https://github.com/RubyEyedReaper/Odin) harness **owns**.\n' \
  > "$r/README.md"
expect_exit "private harness link is refused" 1 "RubyEyedReaper/Odin" --root "$r"

r="$(fixture the-incident-locates)"
printf 'x\nThe skills the [Odin](https://github.com/RubyEyedReaper/Odin) harness.\n' \
  > "$r/README.md"
expect_exit "refusal names file and line" 1 "README.md:2" --root "$r"

# --- near misses that must be ALLOWED ---------------------------------------
# A third-party upstream. PROVENANCE.md and the fork UPSTREAM.md files are
# required by their licences to cite upstream; refusing those breaks the repo.
r="$(fixture third-party)"
printf '| `tdd` | [obra/superpowers](https://github.com/obra/superpowers) | MIT |\n' \
  > "$r/docs/PROVENANCE.md"
expect_exit "allowlisted third-party upstream passes" 0 - --root "$r"

# Naming the harness in prose is fine. Linking it is not.
r="$(fixture bare-name)"
printf 'Skill content originates in the Odin harness and arrives here by sync.\n' \
  > "$r/CHANGELOG.md"
expect_exit "bare repository name in prose passes" 0 - --root "$r"

# The publish-target template in docs/PUBLISHING.md is not a repository.
r="$(fixture placeholder)"
printf 'One repository per skill, `https://github.com/RubyEyedReaper/skill-<name>` — 17 of them.\n' \
  > "$r/docs/PUBLISHING.md"
expect_exit "a <placeholder> slug is not treated as a link" 0 - --root "$r"

# An autolink's closing angle bracket is punctuation, not part of the name.
r="$(fixture autolink)"
printf 'Published at <https://github.com/RubyEyedReaper/Odin-Skills>.\n' > "$r/README.md"
expect_exit "autolink punctuation does not break the slug" 0 - --root "$r"

# --- a code block is not an exemption ---------------------------------------
# `git clone` of a private repository fails for a visitor exactly as a link 404s.
r="$(fixture code-block)"
printf '# Install\n\n```sh\ngit clone https://github.com/RubyEyedReaper/Odin\n```\n' \
  > "$r/README.md"
expect_exit "private link inside a fenced code block is refused" 1 "RubyEyedReaper/Odin" --root "$r"

# --- coverage: nested docs, and every finding reported -----------------------
r="$(fixture nested)"
printf 'Report at [Odin](https://github.com/RubyEyedReaper/Odin).\n' > "$r/docs/PROVENANCE.md"
expect_exit "a doc in a subdirectory is scanned" 1 "docs/PROVENANCE.md" --root "$r"

r="$(fixture two-offenders)"
printf 'a [Odin](https://github.com/RubyEyedReaper/Odin)\n' > "$r/CONTRIBUTING.md"
printf 'b [Priv](https://github.com/RubyEyedReaper/Secret)\n' > "$r/SECURITY.md"
out="$(bash "$CHECKER" --root "$r" 2>&1)"; rc=$?
if [[ $rc -eq 1 ]] && grep -qF 'CONTRIBUTING.md' <<<"$out" && grep -qF 'SECURITY.md' <<<"$out"; then
  ok "every offending file is reported, not just the first"
else
  bad "every offending file is reported, not just the first — exit $rc" "$out"
fi

# --- the allowlist must not be able to disable the check --------------------
# A check whose data is missing must refuse, not agree. Both cases carry a link
# to classify: with nothing to classify there is nothing to refuse.
r="$(fixture no-allowlist)"; rm "$r/scripts/public-repos.txt"
expect_exit "a missing allowlist refuses rather than passing" 1 "public-repos.txt" --root "$r"

r="$(fixture empty-allowlist)"
printf '# every line a comment\n\n' > "$r/scripts/public-repos.txt"
expect_exit "an allowlist with no entries refuses" 1 "public-repos.txt" --root "$r"

r="$(fixture allowlist-override)"
printf 'RubyEyedReaper/Odin\n' > "$TMPROOT/other-list.txt"
printf '[Odin](https://github.com/RubyEyedReaper/Odin)\n' > "$r/README.md"
expect_exit "--allowlist selects a different list" 0 - --root "$r" --allowlist "$TMPROOT/other-list.txt"

# A tree with no GitHub links at all has nothing to classify and is clean —
# this is what lets validate-skills.sh keep passing on its own fixtures.
r="$(fixture no-links)"; rm "$r/scripts/public-repos.txt"
printf '# Doc\n\nNo links here.\n' > "$r/README.md"
expect_exit "no GitHub links at all is clean" 0 - --root "$r"

# --- usage -------------------------------------------------------------------
expect_exit "unknown argument is a usage error" 2 - --nonsense
expect_exit "--help exits 0" 0 - --help

# --- the wiring: the gate runs from validate-skills.sh ------------------------
# A gate nobody's gate list calls is not a gate. This asserts the checker fires
# through the command CONTRIBUTING.md and .github/workflows/validate.yml run.
wiring_fixture() {
  local root="$TMPROOT/$1"
  mkdir -p "$root/.claude-plugin" "$root/skills/alpha" "$root/docs" "$root/scripts"
  printf -- '---\nname: alpha\ndescription: Use when testing the wiring.\n---\n\nBody.\n' \
    > "$root/skills/alpha/SKILL.md"
  cat > "$root/.claude-plugin/plugin.json" <<'JSON'
{"name":"odin-skills","version":"0.1.0","skills":["./skills/alpha"]}
JSON
  printf '# Provenance\n\n| `alpha` | odin-authored |\n' > "$root/docs/PROVENANCE.md"
  printf 'MIT\n' > "$root/LICENSE-MIT"
  printf 'CC-BY-SA-4.0\n' > "$root/LICENSE-CC-BY-SA-4.0"
  printf 'RubyEyedReaper/Odin-Skills\n' > "$root/scripts/public-repos.txt"
  cp "$CHECKER" "$root/scripts/check-doc-links.sh" 2>/dev/null || true
  echo "$root"
}

r="$(wiring_fixture wiring-clean)"
printf '# Alpha\n\nSee <https://github.com/RubyEyedReaper/Odin-Skills>.\n' > "$r/README.md"
out="$(bash "$VALIDATOR" --root "$r" 2>&1)"; rc=$?
if [[ $rc -eq 0 ]]; then
  ok "validate-skills.sh stays green on a tree with only allowlisted links"
else
  bad "validate-skills.sh stays green on a tree with only allowlisted links — exit $rc" "$out"
fi

r="$(wiring_fixture wiring-offender)"
printf '# Alpha\n\nSee [Odin](https://github.com/RubyEyedReaper/Odin).\n' > "$r/README.md"
out="$(bash "$VALIDATOR" --root "$r" 2>&1)"; rc=$?
if [[ $rc -ne 0 ]] && grep -qF 'RubyEyedReaper/Odin' <<<"$out"; then
  ok "validate-skills.sh refuses a tree linking a repository off the allowlist"
else
  bad "validate-skills.sh refuses a tree linking a repository off the allowlist — exit $rc" "$out"
fi

echo
echo "passed: $PASS   failed: $FAIL"
[[ $FAIL -eq 0 ]]
