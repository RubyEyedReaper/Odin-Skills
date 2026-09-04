#!/usr/bin/env bash
# shellcheck source=/dev/null
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/lib/git-env.sh"
#
# tidy-verdict.sh — decide what may be done with one path that has outlived its purpose.
#
# It decides. It does not act. Nothing here removes, moves, truncates or writes; every git
# call is read-only. The caller receives a verdict, a reason, and — for the one verdict that
# authorizes anything — a paired removal recipe whose dry-run and apply lines are generated
# from one template so the two cannot drift apart.
#
# It also performs no discovery. A path arrives, a verdict comes out. Finding what is stale,
# leaked or accumulating belongs to `leek`, which diagnoses and never remediates (ADR-0088);
# a directory argument is a usage error here rather than a candidate list.
#
#   usage: tidy-verdict.sh [--root <dir>] <path|branch>
#
#   verdict: remove       0   a ledger records the basename — its content survived elsewhere
#   verdict: retain      10   no record, so this copy may be the only one
#   verdict: refuse      11   a branch: removal is permanently nobody's (ADR-0093)
#   verdict: unresolved  12   the check could not look; that is a finding, not a silence
#                         2   usage
#
# Every verdict other than `remove` keeps the material. That direction is deliberate: a wrong
# retain costs disk, a wrong removal costs the content.
set -uo pipefail

EX_REMOVE=0
EX_USAGE=2
EX_RETAIN=10
EX_REFUSE=11
EX_UNRESOLVED=12

die() { printf 'usage: %s\n' "$1" >&2; exit "$EX_USAGE"; }

emit() { # emit <verdict> <reason>
  printf 'verdict: %s\n' "$1"
  printf 'reason: %s\n' "$2"
}

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
SELF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
root="$SELF_ROOT"
root_given=0
target=""

while [ $# -gt 0 ]; do
  case "$1" in
    --root)
      [ $# -ge 2 ] || die "--root needs a directory"
      root="$2"; root_given=1; shift 2 ;;
    --root=*)
      root="${1#--root=}"; root_given=1; shift ;;
    -h|--help)
      die "tidy-verdict.sh [--root <dir>] <path|branch>" ;;
    --*)
      die "unknown option '$1'" ;;
    *)
      [ -z "$target" ] || die "one path at a time; got '$target' and '$1'"
      target="$1"; shift ;;
  esac
done

# An empty --root is refused before any git call. `git -C ""` means the CURRENT repository,
# so an empty root does not fail — it silently drives whatever tree the caller happens to be
# standing in, which for a script about deletion is the whole hazard.
if [ "$root_given" = 1 ] && [ -z "$root" ]; then
  die "an empty --root would resolve against the current repository; name the root"
fi
[ -d "$root" ] || die "--root '$root' is not a directory"
root="$(cd "$root" && pwd)"
[ -n "$target" ] || die "tidy-verdict.sh [--root <dir>] <path|branch>"

# ---------------------------------------------------------------------------
# Resolve the argument: a path on disk, a branch, or neither.
# ---------------------------------------------------------------------------
case "$target" in
  /*) abs="$target"; rel="${target#"$root"/}" ;;
  *)  abs="$root/$target"; rel="$target" ;;
esac

if [ -d "$abs" ]; then
  die "'$rel' is a directory; this skill decides about one path at a time — walking a directory for candidates is discovery, which belongs to leek"
fi

if [ ! -e "$abs" ]; then
  # Not a path. A branch, then — or nothing at all.
  ref="${target#refs/heads/}"
  if ge_git -C "$root" rev-parse --verify --quiet "refs/heads/$ref" >/dev/null 2>&1; then
    emit refuse "'$ref' is a branch, and branch deletion is permanently nobody's verdict to give (ADR-0093): the error is asymmetric and force-push is blocked, so a wrongly deleted branch has no reflex that restores it. Landedness can be computed; it is not authorization."
    exit "$EX_REFUSE"
  fi
  emit unresolved "could not resolve '$target' under '$root' as either a path or a branch — a check that could not look is a finding, not a silence"
  exit "$EX_UNRESOLVED"
fi

base="$(basename -- "$abs")"

# ---------------------------------------------------------------------------
# The ledgers. Both are committed files, so the verdict is reproducible from a
# clean checkout. CHANGELOG.md is the contract's canonical removal ledger
# (CLAUDE.md item 8); a numbered decision record is removal-grade evidence too.
# ---------------------------------------------------------------------------
ledgers=()
[ -r "$root/CHANGELOG.md" ] && ledgers+=("$root/CHANGELOG.md")
if [ -d "$root/.claude/docs/decisions" ]; then
  while IFS= read -r f; do [ -r "$f" ] && ledgers+=("$f"); done \
    < <(find "$root/.claude/docs/decisions" -maxdepth 1 -type f -name '*.md' 2>/dev/null | sort)
fi

if [ "${#ledgers[@]}" -eq 0 ]; then
  emit unresolved "no removal ledger is readable under '$root' — neither CHANGELOG.md nor a decision-ledger file — so no removal could be justified and none is offered"
  exit "$EX_UNRESOLVED"
fi

# Boundary-anchored literal match. A plain substring search would let a longer recorded
# basename authorize a shorter one — `live.md` "recorded" by a line naming `live.md.bak` —
# and a false positive here authorizes a deletion. `grep -w` is not enough: its word
# characters stop at `.` and `-`, which are exactly the characters that join these names.
esc="$(printf '%s' "$base" | sed 's/[][\.^$*+?(){}|\/]/\\&/g')"
pattern="(^|[^[:alnum:]._/-])${esc}([^[:alnum:]._-]|\$)"

hit=""
for f in "${ledgers[@]}"; do
  if grep -Eq -- "$pattern" "$f" 2>/dev/null; then hit="$f"; break; fi
done

if [ -z "$hit" ]; then
  emit retain "no removal record names '$base' in CHANGELOG.md or any decision-ledger file, so this copy may be the only place its content exists — retained"
  exit "$EX_RETAIN"
fi

# ---------------------------------------------------------------------------
# remove — and its paired recipe.
#
# One template, one flag slot, two values. The dry-run and apply lines therefore differ at
# exactly one token position, which is what makes "dry-run first, on the same code path as
# the apply" a checkable property rather than a promise: a --dry-run that runs different
# code from the apply proves nothing about the apply.
# ---------------------------------------------------------------------------
recipe() { # recipe <flag>
  if ge_git -C "$root" ls-files --error-unmatch -- "$rel" >/dev/null 2>&1; then
    printf 'git -C %s rm -r %s -- %s' "$root" "$1" "$rel"
  else
    printf 'git -C %s clean -d %s -- %s' "$root" "$1" "$rel"
  fi
}

emit remove "'$base' is recorded in $(basename -- "$hit") — its content survived the removal, which is the only evidence that authorizes one"
printf 'dry-run: %s\n' "$(recipe --dry-run)"
printf 'apply: %s\n' "$(recipe --force)"
printf 'note: run the dry-run, read what it names, then run the apply. This script does neither.\n'
exit "$EX_REMOVE"
