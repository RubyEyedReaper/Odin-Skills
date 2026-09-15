#!/usr/bin/env bash
# sync-from-odin.test.sh — proves the mirror sync compares and copies what git
# would publish, not whatever happens to be on disk.
#
# Every case builds its own harness and mirror under mktemp: a harness git
# repository with one skill, and a mirror whose scripts/ holds a copy of the
# script under test (it resolves the mirror as its own parent directory). Nothing
# reads this checkout or the real harness.
#
# The first case is the recorded occurrence (Odin-Skills#11): a local eval run
# left git-ignored PNGs under the skill's out/, --check reported DRIFT, and the
# harness pre-push refused a push until the files were deleted by hand.
#
# Run: bash scripts/tests/sync-from-odin.test.sh
# Exit: 0 when every case passes, 1 otherwise.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../sync-from-odin.sh"

TMP="$(mktemp -d)"
trap 'find "$TMP" -depth -delete' EXIT

PASS=0
FAIL=0
ok()  { echo "  ok    $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL  $1"; shift; [[ $# -gt 0 ]] && printf '%s\n' "$@" | sed 's/^/          /'; FAIL=$((FAIL + 1)); }

# fixture <name> [plain] — a harness and a mirror in sync for one skill, "demo",
# whose out/ ignores *.png. With "plain", the harness is not a git work tree.
fixture() {
  local root="$TMP/$1"
  mkdir -p "$root/odin/.claude/skills/demo/out" "$root/mirror/scripts" "$root/mirror/skills"
  printf '# demo\n' >"$root/odin/.claude/skills/demo/SKILL.md"
  printf '*.png\n' >"$root/odin/.claude/skills/demo/out/.gitignore"
  printf '{}\n' >"$root/odin/.claude/skills/demo/out/Demo.qa.json"
  if [[ "${2:-}" != plain ]]; then
    git -C "$root/odin" init -q
    git -C "$root/odin" add -A
    git -C "$root/odin" -c user.name=t -c user.email=t@t commit -q -m fixture >/dev/null 2>&1
  fi
  cp -R "$root/odin/.claude/skills/demo" "$root/mirror/skills/demo"
  printf 'MIT\n' >"$root/mirror/skills/demo/LICENSE"
  cp "$SCRIPT" "$root/mirror/scripts/sync-from-odin.sh"
  echo "$root"
}

run_check() { bash "$1/mirror/scripts/sync-from-odin.sh" --check --odin "$1/odin" 2>&1; }

# expect_rc <case> <want-rc> <root> [--check]
expect_check() {
  local name="$1" want="$2" root="$3" out rc
  out="$(run_check "$root")"; rc=$?
  [[ $rc -eq $want ]] && ok "$name" || bad "$name — expected exit $want, got $rc" "$out"
}

echo "sync-from-odin"

root="$(fixture ignored)"
printf 'png' >"$root/odin/.claude/skills/demo/out/Demo.compare.png"
expect_check "BLOCK→ALLOW a git-ignored eval output is not drift (Odin-Skills#11)" 0 "$root"

root="$(fixture ignored-sync)"
printf 'png' >"$root/odin/.claude/skills/demo/out/Demo.compare.png"
bash "$root/mirror/scripts/sync-from-odin.sh" --odin "$root/odin" >/dev/null 2>&1
[[ -e "$root/mirror/skills/demo/out/Demo.compare.png" ]] &&
  bad "a real sync never copies a git-ignored file" ||
  ok "a real sync never copies a git-ignored file"
[[ -f "$root/mirror/skills/demo/LICENSE" ]] && ok "a real sync keeps the mirror's packaging" ||
  bad "a real sync keeps the mirror's packaging"

root="$(fixture mirror-residue)"
printf 'png' >"$root/mirror/skills/demo/out/Stale.compare.png"
printf 'png\n' >"$root/mirror/skills/demo/out/.gitignore.bak"
# The mirror is not a git repository in this fixture, so its residue counts: an
# ignored file only stops counting where git is there to say it is ignored.
expect_check "a mirror-side file with no git to ignore it is still drift" 1 "$root"

root="$(fixture untracked)"
printf 'new\n' >"$root/odin/.claude/skills/demo/references.md"
expect_check "an untracked file that is not ignored is drift" 1 "$root"

root="$(fixture untracked-sync)"
printf 'new\n' >"$root/odin/.claude/skills/demo/references.md"
bash "$root/mirror/scripts/sync-from-odin.sh" --odin "$root/odin" >/dev/null 2>&1
[[ -f "$root/mirror/skills/demo/references.md" ]] && ok "a real sync copies an untracked file git would publish" ||
  bad "a real sync copies an untracked file git would publish"
expect_check "after syncing it, --check is clean" 0 "$root"

root="$(fixture modified)"
printf '# demo, changed\n' >"$root/odin/.claude/skills/demo/SKILL.md"
expect_check "a modified tracked file is drift" 1 "$root"

root="$(fixture deleted)"
rm "$root/odin/.claude/skills/demo/out/Demo.qa.json"
expect_check "a tracked file deleted from the harness work tree is drift" 1 "$root"

root="$(fixture clean)"
expect_check "a skill in sync is not drift" 0 "$root"

root="$(fixture plain plain)"
printf 'png' >"$root/odin/.claude/skills/demo/out/Demo.compare.png"
out="$(run_check "$root")"; rc=$?
[[ $rc -eq 1 ]] && ok "without git, every file on disk counts, as before" ||
  bad "without git, every file on disk counts, as before — expected exit 1, got $rc" "$out"
grep -q "not a git work tree" <<<"$out" && ok "without git, the check says it compared everything" ||
  bad "without git, the check says it compared everything" "$out"

echo
echo "passed: $PASS   failed: $FAIL"
[[ $FAIL -eq 0 ]]
