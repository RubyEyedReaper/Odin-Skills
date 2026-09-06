#!/usr/bin/env bash
#
# successor-deliverable.sh — did the declared deliverable reach the branch?
#
# THE GAP THIS CLOSES. A dispatched session can reach a complete deliverable and never commit it,
# and nothing observed that (harness:RM-0505, #921). `successor-status.sh` asks three questions —
# is the daemon alive, has the branch MOVED, has its content LANDED — and every one of them is
# correct about what it asks. None of them is a question about what the branch CONTAINS. So a worker
# that pushed a plan doc and left its deliverable uncommitted in a worktree reads `live`, at exit 0,
# the code documented as "every row classified live or landed". Measured on a fixture register
# before this file was written.
#
# THE FOURTH CHANNEL, deliberately separate from those three rather than a sixth verdict inside
# them. Its input — a `deliverable` line on the register row — is OPTIONAL, where the other three
# channels' inputs are not. Folding it in would force the field's absence to mean either "silently
# exempt", which re-opens the gap for every row nobody updates, or "undetermined", which flips every
# row in every existing register and every caller's exit code. And `successor-status.sh` forwards
# fleet-health's 2 and 3 unchanged, so there is no code left there for "this row's deliverable
# could not be established". Here there is.
#
# WHAT A DELIVERABLE IS, MECHANICALLY. One glob pattern per `deliverable` line on the register row —
# the row's only repeatable key — matched against `git ls-tree -r --name-only <ref>`, the paths that
# actually reached a commit on that branch. NOT the worktree: the deliverable IS in the worktree,
# uncommitted, and that is the defect. NOT `scope`, which records the paths a worker MAY edit — a
# permission boundary, deliberately wider than the work, and satisfied by a branch that touched none
# of it.
#
# ONE PATTERN PER LINE RATHER THAN SPACE-SEPARATED PATTERNS ON ONE, and the matrix is why. The
# space-separated form was written first, with a refusal for a pattern containing whitespace — and
# the refusal was unreachable, because the split had already turned `a path with spaces.sh` into
# four patterns that each matched nothing. The script would then have reported `unshipped` against a
# declaration nobody could have satisfied. A format that cannot express a path is worse than one
# that is slightly more verbose, and a limitation that can be removed should not be documented
# instead.
#
# THE NEAR MISS THAT KEEPS THIS WORTH RUNNING. A session in its first minutes has pushed a plan doc
# and nothing else, which is byte-identical to the defect. The only observable separating "working
# toward it" from "finished and forgot" is that the branch stopped moving, so the finding is gated
# on the same staleness window the verdict engine uses and a mid-flight row reads `pending`. A check
# that fires on every healthy worker is a false positive, not a strict check.
#
# PRESENCE, NOT CORRECTNESS. A stub file at a declared path satisfies this. The residue is stated
# rather than left to be discovered: this answers "did it reach a commit", and nothing else.
#
# READ-ONLY, AND IT MUST STAY THAT WAY. No fetch, no write, no consumption of what it inspects. Two
# logged occurrences in this repository consumed the state they were probing.
#
# Exit codes — the interface, so a caller greps nothing:
#
#   0   every classified row is shipped, pending or no-commits
#   1   findings — one or more rows unshipped
#   3   nothing could be classified, or a row is undetermined
#   64  usage error
#
# 3 OUTRANKS 1 when both are present. Exit 1 means "these rows need attention and the rest are
# fine" — a claim about the rest. One row whose input could not be read makes that claim false, so
# the run fails closed. 3 spends the code on the same meaning `successor-status.sh` spends it on:
# a channel could not be read, no verdict is claimed. 64 rather than 2 for usage, to match.
#
# Matrix: .claude/tests/successor-deliverable.test.sh

set -uo pipefail

EX_OK=0; EX_FINDINGS=1; EX_UNDETERMINED=3; EX_USAGE=64

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Resolved from this file's location, never from the process's working directory — a tool inherits
# whatever directory an earlier command left behind (cli/patterns.md § Resolving the Target).
HARNESS_ROOT="$(cd "$SELF_DIR/../../../.." && pwd)"

# shellcheck source=../../../scripts/lib/git-env.sh
. "$HARNESS_ROOT/.claude/scripts/lib/git-env.sh"

REGISTER="$HARNESS_ROOT/.claude/.runtime/successor-register"
ROOT="$HARNESS_ROOT"
BASE="origin/main"
STALE_AFTER=1800
ONLY=""
AS_JSON=0

usage() {
  cat <<'EOF'
successor-deliverable.sh — did each delegated session's declared deliverable reach its branch?

  --register DIR        ownership register  (default .claude/.runtime/successor-register)
  --root REPO           repository whose refs are read (default: this harness)
  --base REF            ref the branch's own commits are counted against (default origin/main)
  --stale-after SECONDS a branch quiet longer than this is judged; inside it, pending (default 1800)
  --session ID          classify one row
  --json                one unindented document on stdout, stable key order
  --help                this text

States:
  shipped       every declared pattern matched a path on the branch
  unshipped     the branch moved, has been quiet past the window, and a declared path is missing
  pending       declared paths missing, but the branch is still moving — a session mid-flight
  no-commits    the branch has no commits of its own; successor-status.sh owns that row's verdict
  undeclared    the row declares no deliverable, so nothing is claimed about it
  undetermined  an input could not be read; the reason is named in the DETAIL column

Exit codes:
  0   every classified row is shipped, pending or no-commits
  1   findings — one or more rows unshipped
  3   nothing could be classified, or a row is undetermined
  64  usage error

An empty register, and a register in which no row declares a deliverable, both exit 3. Selecting
nothing is not a pass.

This answers whether a declared path reached a COMMIT. It does not judge what is in the file.

Reads only. It never fetches, never writes, and never consumes what it inspects.
EOF
}

die_usage() {  # die_usage <what failed> <what to do next>
  printf 'successor-deliverable: %s\n' "$1" >&2
  printf '                       %s\n' "$2" >&2
  exit "$EX_USAGE"
}

# --- arguments, before anything can touch a repository -----------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --register)    [ $# -ge 2 ] || die_usage "--register needs a directory" "pass --register <dir>"; REGISTER="$2"; shift 2 ;;
    --root)        [ $# -ge 2 ] || die_usage "--root needs a repository" "pass --root <dir>"; ROOT="$2"; shift 2 ;;
    --base)        [ $# -ge 2 ] || die_usage "--base needs a ref" "pass --base <ref>"; BASE="$2"; shift 2 ;;
    --stale-after) [ $# -ge 2 ] || die_usage "--stale-after needs a number of seconds" "pass --stale-after <seconds>"; STALE_AFTER="$2"; shift 2 ;;
    --session)     [ $# -ge 2 ] || die_usage "--session needs an id" "pass --session <id>"; ONLY="$2"; shift 2 ;;
    --json)        AS_JSON=1; shift ;;
    --help|-h)     usage; exit "$EX_OK" ;;
    *)             die_usage "unknown flag: $1" "run --help for the flag list" ;;
  esac
done

case "$STALE_AFTER" in
  ''|*[!0-9]*) die_usage "--stale-after must be a whole number of seconds, got: $STALE_AFTER" \
                         "pass --stale-after 1800" ;;
esac

# `git -C ""` means the CURRENT repository, so an empty root silently drives whichever tree the
# shell happens to be in. Refused here, before the first git call, rather than discovered by a
# report naming the wrong repository.
[ -n "$ROOT" ] || die_usage "--root was empty, and git reads an empty -C as the current repository" \
                            "name the repository: --root /path/to/checkout"
[ -d "$ROOT" ] || die_usage "--root is not a directory: $ROOT" "name an existing checkout"
if ! ge_git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  die_usage "--root is not a git repository: $ROOT" "name a checkout, or the worktree the fleet pushes from"
fi

# shellcheck source=../../../scripts/lib/branch-progress.sh
. "$HARNESS_ROOT/.claude/scripts/lib/branch-progress.sh" 2>/dev/null || {
  printf 'successor-deliverable: cannot read the branch-progress library — no verdict is claimed.\n' >&2
  exit "$EX_UNDETERMINED"
}

# --- the ownership register ---------------------------------------------------------------------
if [ ! -d "$REGISTER" ]; then
  printf 'successor-deliverable: the ownership register does not exist: %s\n' "$REGISTER" >&2
  printf '                       no verdict is claimed. Pass --register <dir>, or record a row per launch.\n' >&2
  exit "$EX_UNDETERMINED"
fi

rows=()
while IFS= read -r f; do rows+=("$f"); done < <(find "$REGISTER" -maxdepth 1 -type f 2>/dev/null | LC_ALL=C sort)

if [ "${#rows[@]}" -eq 0 ]; then
  # "I looked and found nothing" and "there is nothing to look at" are different answers, and
  # collapsing them is how a monitor stays green while asserting nothing.
  printf 'successor-deliverable: the ownership register holds no rows: %s\n' "$REGISTER" >&2
  printf '                       that is an unreadable channel, not an empty fleet. No verdict is claimed.\n' >&2
  exit "$EX_UNDETERMINED"
fi

field() {  # field <file> <key> — the first value, for the single-valued keys
  awk -F'\t' -v k="$2" '$1==k {sub(/^[^\t]*\t/,""); print; exit}' "$1"
}

fields() {  # fields <file> <key> — every value, one per line, for the repeatable keys
  awk -F'\t' -v k="$2" '$1==k {sub(/^[^\t]*\t/,""); print}' "$1"
}

resolve_ref() {  # resolve_ref <branch> -> the local ref that can be read, or ""
  local b="$1" r
  for r in "refs/remotes/origin/$b" "refs/heads/$b"; do
    if ge_git -C "$ROOT" rev-parse --verify --quiet "${r}^{commit}" >/dev/null 2>&1; then
      printf '%s' "$r"; return 0
    fi
  done
  printf '%s' ""
}

NOW=$(date +%s)

findings=0
undetermined=0
classified=0
matched=0
json_rows=""
[ "$AS_JSON" -eq 0 ] && printf '%-14s %-13s %-26s %s\n' SESSION STATE BRANCH DETAIL

for f in "${rows[@]}"; do
  # A ROW'S IDENTITY IS DECLARED, NEVER INFERRED FROM ITS FILENAME. The basename fallback that once
  # stood in the sibling script invented an id, and the invented id matched no session, so a live
  # worker classified as gone (harness:RM-0401). Same refusal here, for the same reason.
  declared_id="$(field "$f" session_id)"
  sid="${declared_id:-$f}"          # undeclared rows name their own path, so the finding is fixable
  if [ -n "$ONLY" ]; then
    [ "$ONLY" = "$declared_id" ] || continue
  fi
  matched=$((matched+1))

  branch="$(field "$f" branch)"
  # Every `deliverable` line is one pattern, verbatim — no splitting, so a path containing a space
  # is expressible. A line whose value is empty declares nothing and is dropped here rather than
  # becoming a pattern that matches everything.
  patterns=()
  while IFS= read -r _pat; do
    [ -n "$_pat" ] && patterns+=("$_pat")
  done < <(fields "$f" deliverable)
  launched_at="$(field "$f" launched_at)"
  bp_is_epoch "$launched_at" || launched_at="$NOW"

  state=""; detail=""

  # THE UNREADABLE-INPUT CONDITIONS ARE SEPARATED BEFORE THE SUBSTANTIVE COMPUTATION, not after it.
  # Every recorded occurrence of the class this guards against composed a path, a probe or a join on
  # an input it had never established (cli/coding-style.md § A Verdict Requires an Input You
  # Actually Read; this skill's other script is one of that key's four subjects).
  if [ -z "$declared_id" ]; then
    state=undetermined; detail="no-session-id"
  elif [ "${#patterns[@]}" -eq 0 ]; then
    # NOT a verdict. A row that declares no deliverable is a row this check has no subject for, and
    # saying so is the honest answer — the alternative, treating an absent declaration as satisfied,
    # is exactly the silent pass the whole file exists to remove.
    state=undeclared; detail="no deliverable declared on the row"
  elif [ -z "$branch" ]; then
    state=undetermined; detail="no-branch-recorded"
  fi

  if [ -z "$state" ]; then
    ref="$(resolve_ref "$branch")"
    if [ -z "$ref" ]; then
      # Either the branch exists nowhere, or it is published but unfetched — and this probe does not
      # fetch. Both are "the content could not be read", which is not "the deliverable is missing".
      state=undetermined; detail="ref-unreadable"
    elif ! tree="$(ge_git -C "$ROOT" ls-tree -r --name-only "$ref" 2>/dev/null)"; then
      state=undetermined; detail="tree-unreadable"
    elif ! ahead="$(ge_git -C "$ROOT" rev-list --count "$BASE..$ref" 2>/dev/null)" \
         || ! bp_is_epoch "$ahead"; then
      # A count this probe could not obtain is not zero. Fail closed, exactly as the unreadable
      # cases above do.
      state=undetermined; detail="commit-count-unreadable"
    elif [ "$ahead" -eq 0 ]; then
      # No work yet is not work that vanished. The branch never moved, so there is no worker action
      # for this check to be about; successor-status.sh already reports that row.
      state=no-commits; detail="branch has no commits of its own"
    else
      missing=()
      for pat in "${patterns[@]}"; do
        hit=0
        while IFS= read -r path; do
          # `*` crosses `/` here, deliberately: a declaration is a coarse statement about where the
          # work lands, and `.claude/tests/*.test.sh` should match however deeply it is nested.
          # shellcheck disable=SC2254
          case "$path" in $pat) hit=1; break ;; esac
        done <<< "$tree"
        [ "$hit" -eq 1 ] || missing+=("$pat")
      done

      if [ "${#missing[@]}" -eq 0 ]; then
        state=shipped; detail="all ${#patterns[@]} declared path(s) present"
      else
        if ! progress="$(bp_last_author_ts "$ROOT" "$ref" "$BASE" "$launched_at")"; then
          state=undetermined; detail="progress-date-unreadable"
        elif [ $((NOW - progress)) -lt "$STALE_AFTER" ]; then
          # THE NEAR MISS. Still moving, so the absence is work not yet done rather than work not
          # done. Reporting it would make this fire on every healthy worker.
          state=pending; detail="missing but still moving: ${missing[*]}"
        else
          state=unshipped; detail="missing: ${missing[*]}"
        fi
      fi
    fi
  fi

  case "$state" in
    unshipped)    findings=$((findings+1));     classified=$((classified+1)) ;;
    undetermined) undetermined=$((undetermined+1)) ;;
    undeclared)   ;;
    *)            classified=$((classified+1)) ;;
  esac

  if [ "$AS_JSON" -eq 1 ]; then
    [ -n "$json_rows" ] && json_rows="$json_rows,"
    json_rows="$json_rows{\"session\":\"$sid\",\"state\":\"$state\",\"branch\":\"$branch\",\"detail\":\"$detail\"}"
  else
    printf '%-14s %-13s %-26s %s\n' "$sid" "$state" "${branch:--}" "$detail"
  fi
done

if [ "$AS_JSON" -eq 1 ]; then
  printf '{"register":"%s","rows":[%s]}\n' "$REGISTER" "$json_rows"
fi

if [ -n "$ONLY" ] && [ "$matched" -eq 0 ]; then
  # Nothing was inspected, so nothing may be claimed. Exit 0 here would mean "every row is fine"
  # about a run that read no row.
  printf 'successor-deliverable: no row declares session_id %s in %s\n' "$ONLY" "$REGISTER" >&2
  printf '                       no verdict is claimed. Run without --session to list the declared ids.\n' >&2
  exit "$EX_UNDETERMINED"
fi

# 3 OUTRANKS 1. Exit 1 asserts something about the rows it did not flag; one unreadable row makes
# that assertion unsupportable, so the run fails closed and names what is missing.
if [ "$undetermined" -gt 0 ]; then
  printf 'successor-deliverable: %s row(s) could not be classified — see the DETAIL column.\n' "$undetermined" >&2
  printf '                       no verdict is claimed for the run while an input is unreadable.\n' >&2
  exit "$EX_UNDETERMINED"
fi

if [ "$classified" -eq 0 ]; then
  # Selecting nothing is not a pass. Every row was `undeclared`, so this run asserted nothing at all
  # — which reads identically to a clean fleet unless it says so.
  printf 'successor-deliverable: no row in %s declares a deliverable.\n' "$REGISTER" >&2
  printf '                       nothing was classified. Record a `deliverable` line per launch.\n' >&2
  exit "$EX_UNDETERMINED"
fi

[ "$findings" -eq 0 ] && exit "$EX_OK"
printf 'successor-deliverable: %s row(s) reached a commit without their deliverable.\n' "$findings" >&2
printf '                       the work may be sitting uncommitted in the worker'\''s worktree.\n' >&2
exit "$EX_FINDINGS"
