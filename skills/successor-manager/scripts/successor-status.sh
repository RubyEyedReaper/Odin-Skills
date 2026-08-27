#!/usr/bin/env bash
#
# successor-status.sh — what is true of each delegated session, from evidence.
#
# THE ORDERING IS THE POINT, and it is expressed below as control flow rather than as a comment,
# because a comment cannot short-circuit:
#
#   1. FLEET HEALTH FIRST. Its exit code gates everything after it. A monitor cannot read its own
#      subject: the session registry outlives the daemon that served it, so five sessions that died
#      together at 2026-08-19T00:22Z went on rendering as ordinary for eight hours (M-0014,
#      ADR-0072). Exit 2 from the health gate means every session is dead whatever the registry
#      says. Exit 3 means the registry is unreadable and no verdict may be claimed for anything.
#   2. BRANCH MOVEMENT. `git ls-remote` for the published sha, and the tip's own commit date.
#   3. LANDEDNESS BY CONTENT, via bl_classify. Never `git merge-base --is-ancestor`: this
#      repository lands by rebase merge, which rewrites every sha, and ancestry answered
#      "not merged" for 56 of 110 branches that had in fact landed (ADR-0093).
#
# A SESSION'S OWN REPORT OF ITSELF IS NEVER SUFFICIENT EVIDENCE. This script reads the registry's
# id SET and nothing else from it. Membership is the daemon's account of who exists, and step 1 has
# just proved the daemon is alive and therefore that its account is current; the per-session field
# describing how a session feels about itself is the subject talking, and a wedged one lies.
#
# READ-ONLY, AND IT MUST STAY THAT WAY. No fetch, no write, no consumption of what it inspects.
# Two logged occurrences in this repository consumed the state they were probing.
#
# Exit codes — the interface, so a caller greps nothing:
#
#   0   every row classified live or landed
#   1   findings — one or more rows stalled / failed / undetermined
#   2   daemon down; every row is failed
#   3   a register could not be read; no verdict claimed for anything
#   64  usage error
#
# 2 and 3 are forwarded from fleet-health.sh, which spends them on the same two meanings, so a
# caller that already handles the fleet monitor handles this unchanged. 64 rather than 2 for usage,
# because 2 is taken here.

set -uo pipefail

EX_OK=0; EX_FINDINGS=1; EX_DAEMON=2; EX_REGISTER=3; EX_USAGE=64

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Resolved from this file's location, never from the process's working directory — a tool inherits
# whatever directory an earlier command left behind (cli/patterns.md § Resolving the Target).
HARNESS_ROOT="$(cd "$SELF_DIR/../../../.." && pwd)"

REGISTER="$HARNESS_ROOT/.claude/.runtime/successor-register"
ROOT="$HARNESS_ROOT"
BASE="origin/main"
STALE_AFTER=1800
ONLY=""
AS_JSON=0

# Both overrides exist for the test matrix, and follow the convention fleet-health.sh documents for
# its own. ODIN_FLEET_AGENTS_CMD is deliberately the SAME variable that script uses, so one stub
# serves both.
FLEET_CMD=${ODIN_SUCCESSOR_FLEET_CMD:-"bash $HARNESS_ROOT/.claude/scripts/fleet-health.sh"}
AGENTS_CMD=${ODIN_FLEET_AGENTS_CMD:-"claude agents --json"}

usage() {
  cat <<'EOF'
successor-status.sh — classify each delegated session from evidence, never from its own report.

  --register DIR        ownership register  (default .claude/.runtime/successor-register)
  --root REPO           repository whose refs are read (default: this harness)
  --base REF            landedness comparison ref (default origin/main)
  --stale-after SECONDS branch quiet for longer than this is stalled, not live (default 1800)
  --session ID          classify one row
  --json                one unindented document on stdout, stable key order
  --help                this text

Verdicts: live | stalled | failed | landed | undetermined
  undetermined is mandatory, not a fallback: it is the honest answer when the channels disagree
  or one of them could not be read. A classifier without it invents verdicts silently.

Exit codes:
  0   every row is live or landed
  1   findings — one or more rows stalled, failed or undetermined
  2   daemon down (forwarded from fleet-health.sh); every row is failed
  3   a register could not be read; no verdict is claimed for anything
  64  usage error

Reads only. It never fetches, never writes, and never consumes what it inspects.
EOF
}

die_usage() {  # die_usage <what failed> <what to do next>
  printf 'successor-status: %s\n' "$1" >&2
  printf '                  %s\n' "$2" >&2
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
if ! git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  die_usage "--root is not a git repository: $ROOT" "name a checkout, or the worktree the fleet pushes from"
fi

# --- 1. the health gate, first and short-circuiting ---------------------------------------------
fleet_out="$($FLEET_CMD 2>&1)"; fleet_rc=$?
printf '%s\n' "$fleet_out" >&2

if [ "$fleet_rc" -eq 3 ]; then
  printf 'successor-status: the session registry is unreadable — no verdict is claimed for any row.\n' >&2
  printf '                  fix the fleet tooling, then re-run. Nothing here guesses.\n' >&2
  exit "$EX_REGISTER"
fi

# --- 2. the ownership register ------------------------------------------------------------------
if [ ! -d "$REGISTER" ]; then
  printf 'successor-status: the ownership register does not exist: %s\n' "$REGISTER" >&2
  printf '                  no verdict is claimed. Pass --register <dir>, or record a row per launch.\n' >&2
  exit "$EX_REGISTER"
fi

rows=()
while IFS= read -r f; do rows+=("$f"); done < <(find "$REGISTER" -maxdepth 1 -type f 2>/dev/null | LC_ALL=C sort)

if [ "${#rows[@]}" -eq 0 ]; then
  # An empty register is not a clean fleet. "I looked and found nothing" and "there is nothing to
  # look at" are different answers, and collapsing them is how a monitor stays green while
  # asserting nothing (ci/testing.md § A Check That Could Not Run Says So).
  printf 'successor-status: the ownership register holds no rows: %s\n' "$REGISTER" >&2
  printf '                  that is an unreadable channel, not an empty fleet. No verdict is claimed.\n' >&2
  exit "$EX_REGISTER"
fi

field() {  # field <file> <key>
  awk -F'\t' -v k="$2" '$1==k {sub(/^[^\t]*\t/,""); print; exit}' "$1"
}

# --- the registry's id set, and nothing else from it ---------------------------------------------
DAEMON_DOWN=0
[ "$fleet_rc" -eq 2 ] && DAEMON_DOWN=1

registry_ids=""
if [ "$DAEMON_DOWN" -eq 0 ]; then
  registry_ids="$($AGENTS_CMD 2>/dev/null \
    | grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | sed -E 's/.*:[[:space:]]*"([^"]*)".*/\1/' || true)"
fi
in_registry() { printf '%s\n' "$registry_ids" | grep -qxF "$1"; }

NOW=$(date +%s)

resolve_ref() {  # resolve_ref <branch> -> the local ref that can be read, or ""
  local b="$1" r
  for r in "refs/remotes/origin/$b" "refs/heads/$b"; do
    if git -C "$ROOT" rev-parse --verify --quiet "${r}^{commit}" >/dev/null 2>&1; then
      printf '%s' "$r"; return 0
    fi
  done
  printf '%s' ""
}

# shellcheck source=../../../scripts/lib/branch-landedness.sh
. "$HARNESS_ROOT/.claude/scripts/lib/branch-landedness.sh" 2>/dev/null || {
  printf 'successor-status: cannot read the landedness library — no verdict is claimed.\n' >&2
  exit "$EX_REGISTER"
}

findings=0
json_rows=""
[ "$AS_JSON" -eq 0 ] && printf '%-14s %-13s %-26s %-6s %-19s %-8s %s\n' \
  SESSION VERDICT BRANCH MOVED LANDEDNESS MODEL INTEGRATOR

for f in "${rows[@]}"; do
  sid="$(field "$f" session_id)"; [ -n "$sid" ] || sid="$(basename "$f")"
  [ -n "$ONLY" ] && [ "$ONLY" != "$sid" ] && continue

  branch="$(field "$f" branch)"
  model="$(field "$f" model)";           [ -n "$model" ]      || model="-"
  integrator="$(field "$f" integrator)"; [ -n "$integrator" ] || integrator="-"
  launch_sha="$(field "$f" launch_sha)"
  launched_at="$(field "$f" launched_at)"
  case "$launched_at" in ''|*[!0-9]*) launched_at="$NOW" ;; esac

  if [ -z "$branch" ]; then
    verdict=undetermined; moved="?"; landedness="no-branch-recorded"
  elif [ "$DAEMON_DOWN" -eq 1 ]; then
    # The gate has spoken. The registry is not consulted, the refs are not consulted, and no row
    # gets a kinder verdict than the daemon's absence allows.
    verdict=failed; moved="?"; landedness="not-consulted"
  else
    if remote_line="$(git -C "$ROOT" ls-remote --heads origin "$branch" 2>/dev/null)"; then
      remote_sha="${remote_line%%$'\t'*}"
    else
      remote_sha="?"
    fi

    if [ "$remote_sha" = "?" ]; then
      moved="?"
    elif [ -n "$remote_sha" ] && [ "$remote_sha" != "$launch_sha" ]; then
      moved="yes"
    else
      moved="no"
    fi

    ref="$(resolve_ref "$branch")"
    if [ -n "$ref" ]; then
      landedness="$(bl_classify "$ROOT" "$ref" "$BASE")"
      progress="$(git -C "$ROOT" log -1 --format=%ct "$ref" 2>/dev/null)"
      case "$progress" in ''|*[!0-9]*) progress="$launched_at" ;; esac
    elif [ "$remote_sha" = "?" ]; then
      landedness="remote-unreadable"; progress="$launched_at"
    elif [ -n "$remote_sha" ]; then
      # Published, but its content cannot be read without a fetch — and this probe does not fetch.
      landedness="unfetched"; progress="$launched_at"
    else
      landedness="absent"; progress="$launched_at"
    fi

    case "$landedness" in
      landed)
        verdict=landed ;;
      undetermined|evidence-unavailable|remote-unreadable|unfetched)
        verdict=undetermined ;;
      *)
        if in_registry "$sid"; then
          if [ $((NOW - progress)) -lt "$STALE_AFTER" ]; then verdict=live; else verdict=stalled; fi
        else
          # Gone from a registry the health gate has just proved current, with nothing landed.
          verdict=failed
        fi ;;
    esac
  fi

  case "$verdict" in live|landed) ;; *) findings=$((findings+1)) ;; esac

  if [ "$AS_JSON" -eq 1 ]; then
    [ -n "$json_rows" ] && json_rows="$json_rows,"
    json_rows="$json_rows{\"session\":\"$sid\",\"verdict\":\"$verdict\",\"branch\":\"$branch\",\"moved\":\"$moved\",\"landedness\":\"$landedness\",\"model\":\"$model\",\"integrator\":\"$integrator\"}"
  else
    printf '%-14s %-13s %-26s %-6s %-19s %-8s %s\n' \
      "$sid" "$verdict" "${branch:--}" "$moved" "$landedness" "$model" "$integrator"
  fi
done

if [ "$AS_JSON" -eq 1 ]; then
  printf '{"daemon":%s,"register":"%s","rows":[%s]}\n' \
    "$([ "$DAEMON_DOWN" -eq 1 ] && printf 'false' || printf 'true')" "$REGISTER" "$json_rows"
fi

if [ "$DAEMON_DOWN" -eq 1 ]; then
  printf 'successor-status: the session daemon is gone. Every session is dead whatever the registry\n' >&2
  printf '                  last knew. Relaunch the fleet from amended handoffs — see the successor skill.\n' >&2
  exit "$EX_DAEMON"
fi

[ "$findings" -eq 0 ] && exit "$EX_OK"
printf 'successor-status: %s row(s) need attention — see references/escalation-paths.md.\n' "$findings" >&2
exit "$EX_FINDINGS"
