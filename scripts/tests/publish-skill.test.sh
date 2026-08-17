#!/usr/bin/env bash
# publish-skill.test.sh — proves every decision publish-skill.sh makes before it
# reaches the network, and proves it reaches none.
#
# Publishing creates public repositories, so a test that shelled out to the real
# git or gh would leave one behind. Stubs sit earlier on PATH for the whole
# suite rather than per case: the gh stub only logs its argv and returns a
# configurable exit code, and the git stub logs every call, passes read-only and
# local-repository subcommands through to the real binary, and refuses
# clone/push/subtree/remote outright. Assertions about what the script would run
# read $TMP/calls.log.
#
# Run: bash scripts/tests/publish-skill.test.sh
# Exit: 0 when every case passes, 1 otherwise.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../publish-skill.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

CALLS="$TMP/calls.log"
: > "$CALLS"
REAL_GIT="$(command -v git)"
export CALLS REAL_GIT

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Stubs — installed before anything else runs
# ---------------------------------------------------------------------------
STUBS="$TMP/stubs"
mkdir -p "$STUBS"

cat > "$STUBS/git" <<'STUB'
#!/usr/bin/env bash
# Logs, then either runs the real git (read-only and local-repo subcommands) or
# stops (anything that could touch a remote or rewrite the harness).
printf 'git %s\n' "$*" >> "$CALLS"
sub=""
i=1
while [[ $i -le $# ]]; do
  case "${!i}" in
    -C|-c) i=$((i + 2)); continue ;;
    --git-dir=*|--work-tree=*|--no-pager|--exec-path=*) i=$((i + 1)); continue ;;
    *) sub="${!i}"; break ;;
  esac
done
case "$sub" in
  rev-parse|status|log|config|show|diff|init|add|commit) exec "$REAL_GIT" "$@" ;;
  *) exit 0 ;;
esac
STUB

cat > "$STUBS/gh" <<'STUB'
#!/usr/bin/env bash
printf 'gh %s\n' "$*" >> "$CALLS"
exit "${STUB_GH_EXIT:-1}"
STUB

chmod +x "$STUBS/git" "$STUBS/gh"
export PATH="$STUBS:$PATH"

# ---------------------------------------------------------------------------
# Assertion helpers
#
# validate.test.sh's expect_pass/expect_fail take a fixture root and run the
# validator; a function-level assertion needs the function and its arguments
# instead, so these are their own shape.
# ---------------------------------------------------------------------------
ok()   { echo "  ok    $1"; PASS=$((PASS + 1)); }
bad()  { echo "  FAIL  $1"; shift; [[ $# -gt 0 ]] && printf '%s\n' "$@" | sed 's/^/          /'; FAIL=$((FAIL + 1)); }

# expect_ok <case> <cmd...> — exits 0
expect_ok() {
  local name="$1"; shift
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  [[ $rc -eq 0 ]] && ok "$name" || bad "$name — expected exit 0, got $rc" "$out"
}

# expect_fail_fn <case> <cmd...> — exits non-zero
expect_fail_fn() {
  local name="$1"; shift
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  [[ $rc -ne 0 ]] && ok "$name" || bad "$name — expected non-zero exit, got 0" "$out"
}

# expect_out <case> <expected-stdout> <cmd...> — stdout equals exactly
expect_out() {
  local name="$1" want="$2"; shift 2
  local got
  got="$("$@" 2>/dev/null)"
  [[ "$got" == "$want" ]] && ok "$name" || bad "$name — want '$want', got '$got'"
}

# expect_contains <case> <substring> <cmd...>
expect_contains() {
  local name="$1" want="$2"; shift 2
  local got
  got="$("$@" 2>&1)"
  grep -qF -- "$want" <<<"$got" && ok "$name" || bad "$name — output never said '$want'" "$got"
}

# expect_lines <case> <expected-multiline-stdout> <cmd...>
expect_lines() {
  local name="$1" want="$2"; shift 2
  local got
  got="$("$@" 2>/dev/null)"
  [[ "$got" == "$want" ]] && ok "$name" || bad "$name — line set differs" "want:" "$want" "got:" "$got"
}

# expect_no_gh <case> <cmd...> — the invocation logs no gh call at all
expect_no_gh() {
  local name="$1"; shift
  : > "$CALLS"
  "$@" >/dev/null 2>&1
  if grep -q '^gh ' "$CALLS"; then
    bad "$name — reached gh" "$(grep '^gh ' "$CALLS")"
  else
    ok "$name"
  fi
}

# expect_call <case> <substring> <cmd...> — the invocation logs this argv,
# whatever it goes on to do afterwards
expect_call() {
  local name="$1" want="$2"; shift 2
  : > "$CALLS"
  "$@" >/dev/null 2>&1
  grep -qF -- "$want" "$CALLS" && ok "$name" || bad "$name — never ran '$want'" "$(cat "$CALLS")"
}

# expect_reachable_links <case> <skill> — every GitHub repository the landing
# page links to is one a visitor can actually open. The harness repository is
# private, so a link to it renders as a 404 and an issue tracker nobody outside
# the account can file on; only the published mirror and the skill's own
# repository are reachable from a public page.
expect_reachable_links() {
  local name="$1" skill="$2" page slug unreachable=""
  page="$(readme_body "$skill" 2>/dev/null)"
  while IFS= read -r slug; do
    [[ -z "$slug" ]] && continue
    case "$slug" in
      "$OWNER/Odin-Skills"|"$OWNER/skill-$skill") ;;
      *) unreachable+="$slug " ;;
    esac
  done < <(grep -oE 'github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+' <<<"$page" |
             sed -e 's#^github\.com/##' -e 's#\.git$##' | sort -u)
  if [[ -z "$unreachable" ]]; then
    ok "$name"
  else
    bad "$name — links a visitor cannot open: $unreachable" "$page"
  fi
}

# ---------------------------------------------------------------------------
# Fixtures
#
# A harness-shaped git repository: the skills live at
# <toplevel>/projects/Odin-Skills/skills/, which is what makes the
# repo-root-relative subtree prefix observable. Every licence class gets a
# skill, including the fork with neither artefact, so nothing here reads the
# live tree.
# ---------------------------------------------------------------------------
skill_md() { # skill_md <dir> <name> <description>
  printf -- '---\nname: %s\ndescription: %s\n---\n\nBody.\n' "$2" "$3" > "$1/SKILL.md"
}

HARNESS="$TMP/harness"
FIXTURE_ROOT="$HARNESS/projects/Odin-Skills"
mkdir -p "$FIXTURE_ROOT/skills"/{roadmap,impeccable,rules-distill,fork-with-no-license}
git init -q "$HARNESS"

skill_md "$FIXTURE_ROOT/skills/roadmap" roadmap \
  "Use when the user asks what to work on next or what is left to build."
skill_md "$FIXTURE_ROOT/skills/impeccable" impeccable \
  "Use when an interface needs design, critique or polish."
skill_md "$FIXTURE_ROOT/skills/rules-distill" rules-distill \
  "Use when recurring patterns across skills belong in a rule file."
skill_md "$FIXTURE_ROOT/skills/fork-with-no-license" fork-with-no-license \
  "Use when proving the licence check fails closed."

printf 'Apache License 2.0\n' > "$FIXTURE_ROOT/skills/impeccable/LICENSE"
printf '# Upstream: impeccable\n' > "$FIXTURE_ROOT/skills/impeccable/UPSTREAM.md"
printf '# Upstream: rules-distill\n' > "$FIXTURE_ROOT/skills/rules-distill/UPSTREAM.md"
printf 'Upstream ships no LICENSE file.\n' > "$FIXTURE_ROOT/skills/rules-distill/NOTICE"
printf '# Upstream: fork-with-no-license\n' > "$FIXTURE_ROOT/skills/fork-with-no-license/UPSTREAM.md"

printf 'MIT\n' > "$FIXTURE_ROOT/LICENSE-MIT"
printf 'CC-BY-SA-4.0\n' > "$FIXTURE_ROOT/LICENSE-CC-BY-SA-4.0"
printf 'Odin-Skills NOTICE\n' > "$FIXTURE_ROOT/NOTICE"

# clean_repo: one committed file, nothing outstanding.
# dirty_repo: the same plus an untracked file.
CLEAN_REPO="$TMP/clean"
DIRTY_REPO="$TMP/dirty"
for repo in "$CLEAN_REPO" "$DIRTY_REPO"; do
  mkdir -p "$repo"
  git init -q "$repo"
  git -C "$repo" config user.email test@example.com
  git -C "$repo" config user.name Test
  printf 'committed\n' > "$repo/file.txt"
  git -C "$repo" add file.txt
  git -C "$repo" commit -qm "seed"
done
printf 'untracked\n' > "$DIRTY_REPO/loose.txt"

desc_of() { sed -n 's/^description: //p' "$FIXTURE_ROOT/skills/$1/SKILL.md" | head -1; }

# ---------------------------------------------------------------------------
echo "publish-skill.sh matrix"

if [[ ! -f "$SCRIPT" ]]; then
  bad "publish-skill.sh exists at scripts/publish-skill.sh"
  echo
  echo "passed: $PASS   failed: $FAIL"
  exit 1
fi

ROOT="$FIXTURE_ROOT"
# shellcheck source=../publish-skill.sh
source "$SCRIPT"

# --- name validation --------------------------------------------------------
expect_ok      "accepts an existing skill"            validate_skill_name roadmap
expect_fail_fn "rejects a skill that is not on disk"  validate_skill_name no-such-skill
expect_fail_fn "rejects an uppercase name"            validate_skill_name Roadmap
expect_fail_fn "rejects a path traversal"             validate_skill_name ../../etc
# The one traversal the existence check cannot catch: skills/../skills/roadmap
# is a real SKILL.md, and it would name a repository 'skill-../skills/roadmap'
# and a subtree prefix outside the tree. Only the pattern rejects it.
expect_fail_fn "rejects a traversal that resolves onto a real skill" \
  validate_skill_name ../skills/roadmap

# --- repo naming and the subtree prefix -------------------------------------
# The prefix is repository-root-relative: git subtree runs cd_to_toplevel before
# reading -P, so a $ROOT-relative prefix silently splits nothing.
expect_out "repo name is prefixed"   "skill-roadmap"                        repo_name_for roadmap
expect_out "prefix is repo-relative" "projects/Odin-Skills/skills/roadmap"  subtree_prefix_for roadmap

# --- landing page -----------------------------------------------------------
expect_contains "banner names the coordinating repo" "RubyEyedReaper/Odin-Skills" readme_body roadmap
expect_contains "banner refuses PRs"                 "not merged"          readme_body roadmap
expect_reachable_links "page links only where a visitor can go" roadmap
expect_contains "page carries the skill description" "$(desc_of roadmap)"  readme_body roadmap
expect_contains "page shows how to install it"       "~/.claude/skills"    readme_body roadmap
expect_contains "page names the licence artefacts"   "LICENSE-MIT"         readme_body roadmap

# --- licence selection, by skill class --------------------------------------
expect_lines "fork with LICENSE carries it plus the root NOTICE" "skills/impeccable/LICENSE
NOTICE" license_files_for impeccable
expect_lines "declared-absence fork carries its NOTICE plus the root NOTICE" "skills/rules-distill/NOTICE
NOTICE" license_files_for rules-distill
expect_lines "authored skill carries split licensing" "LICENSE-MIT
LICENSE-CC-BY-SA-4.0" license_files_for roadmap
expect_fail_fn "fork with neither artefact is refused" license_files_for fork-with-no-license
expect_contains "refusal names the missing artefact" "fork-with-no-license" license_files_for fork-with-no-license

# --- rerun behaviour --------------------------------------------------------
expect_out "absent repo means create" "create" publish_mode RubyEyedReaper/skill-nothing-here
STUB_GH_EXIT=0 expect_out "present repo means update" "update" publish_mode RubyEyedReaper/skill-roadmap
expect_fail_fn "clean tree needs no commit" needs_commit "$CLEAN_REPO"
expect_ok      "dirty tree needs a commit"  needs_commit "$DIRTY_REPO"

# --- dry run: no network, and the plan it prints is the argv it would run ----
expect_contains "dry run prints the gh call it skips"    "gh repo create"  main roadmap --dry-run
expect_contains "dry run prints the repo-relative split" "subtree split -P projects/Odin-Skills/skills/roadmap" main roadmap --dry-run
expect_ok       "dry run exits 0"                        main roadmap --dry-run
expect_no_gh    "dry run makes no gh call"               main roadmap --dry-run
expect_call     "create mode runs the repo-relative split" \
  "subtree split -P projects/Odin-Skills/skills/roadmap" main roadmap

# A licence class it cannot satisfy stops the run before any network call.
expect_fail_fn "unsatisfiable licence class aborts" main fork-with-no-license --dry-run
expect_no_gh   "aborted run makes no gh call"       main fork-with-no-license

# --- interface --------------------------------------------------------------
expect_contains "--help prints usage" "Usage:" main --help
expect_fail_fn  "no arguments is a usage error" main
expect_fail_fn  "an unknown flag is a usage error" main roadmap --nope

echo
echo "passed: $PASS   failed: $FAIL"
[[ $FAIL -eq 0 ]]
