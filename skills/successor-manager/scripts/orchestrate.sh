#!/usr/bin/env bash
#
# orchestrate.sh — the console's read-only half, one screen.
#
# Filed as #1245 / harness:RM-0613: successor-manager named none of the orchestration skills a
# coordinator needs, so the ownership register was readable and the fleet around it was not.
#
# IT COMPOSES; IT COMPUTES NOTHING. Every verdict printed here belongs to the probe that produced
# it. A fourth opinion assembled from three probes' text is a second implementation of all three,
# and the looser copy wins silently (M-0003).
#
# THE ORDERING IS THE POINT, and it is control flow rather than a comment because a comment cannot
# short-circuit:
#
#   1. fleet-health.sh FIRST. Its exit code gates everything after it. A monitor cannot read its own
#      subject: the registry outlives the daemon that served it, so five sessions that died together
#      at 2026-08-19T00:22Z rendered as ordinary for eight hours (M-0014, ADR-0072).
#        rc 2 — daemon down. Downstream still runs: the per-row detail is what a coordinator acts
#               on, and `successor-status.sh` gates on the same signal and reports every row failed.
#        rc 3 — the registry could not be read. NO VERDICT MAY BE CLAIMED FOR ANYTHING, so the run
#               STOPS here rather than printing rows nobody may act on.
#   2. successor-status.sh — what is true of each delegated session.
#   3. successor-deliverable.sh — whether what each session was for reached a commit.
#
# Exit codes — the interface, so a caller greps nothing. Precedence 3 > 2 > 1 > 0:
#
#   0   every probe clean
#   1   findings — a row stalled, failed, undetermined, or a deliverable unshipped
#   2   daemon down
#   3   an input could not be read; no verdict is claimed
#   64  usage error
#
# 2 and 3 carry the meanings fleet-health.sh spends them on, unchanged through two layers, so a
# caller that already handles the fleet monitor handles this too. 3 outranks 2 deliberately: "every
# session is dead" is a verdict, "nobody could look" is the absence of one, and only the second
# makes the first unsupportable.
#
# READ-ONLY. No fetch, no write, and it never consumes the state it inspects — two logged
# occurrences in this repository stripped a live session's posture on the way past a read.
set -uo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SELF_DIR/../../../.." && pwd)"

JSON=0
PASSTHRU=()
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    --register|--root|--window-hours|--session)
      [ $# -ge 2 ] || { echo "orchestrate: $1 needs a value" >&2; exit 64; }
      PASSTHRU+=("$1" "$2"); shift ;;
    -h|--help)
      sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "orchestrate: unknown argument: $1" >&2; exit 64 ;;
  esac
  shift
done

HEALTH="$ROOT/.claude/scripts/fleet-health.sh"
STATUS="$SELF_DIR/successor-status.sh"
DELIV="$SELF_DIR/successor-deliverable.sh"

for probe in "$HEALTH" "$STATUS" "$DELIV"; do
  [ -f "$probe" ] || {
    echo "orchestrate: a composed probe is missing: $probe" >&2
    echo "             no verdict is claimed." >&2
    exit 3
  }
done

# oc_run <path> [args…] — capture a probe's combined output and its OWN status.
#
# Assigned in two statements, never `out="$(…)"; rc=$?` on one line with a pipe in it: under
# pipefail a pipeline's status belongs to whichever stage exited first (C-0005), and there is no
# pipeline here precisely so the status is the probe's.
oc_out=""
oc_rc=0
oc_run() {
  oc_out="$("$@" 2>&1)"
  oc_rc=$?
}

worst=0
# oc_worst <rc> — precedence 3 > 2 > 1 > 0, which is not numeric max in general but is here; the
# function exists so the ordering is stated once and cannot be re-derived differently below.
oc_worst() {
  case "$1" in
    3) worst=3 ;;
    2) [ "$worst" = 3 ] || worst=2 ;;
    1) case "$worst" in 2|3) ;; *) worst=1 ;; esac ;;
  esac
}

oc_run bash "$HEALTH"
health_out="$oc_out"; health_rc="$oc_rc"
oc_worst "$health_rc"

gated=0
status_out=""; status_rc=""
deliv_out=""; deliv_rc=""

if [ "$health_rc" = 3 ]; then
  gated=1
else
  oc_run bash "$STATUS" ${PASSTHRU+"${PASSTHRU[@]}"}
  status_out="$oc_out"; status_rc="$oc_rc"
  oc_worst "$status_rc"

  oc_run bash "$DELIV" ${PASSTHRU+"${PASSTHRU[@]}"}
  deliv_out="$oc_out"; deliv_rc="$oc_rc"
  oc_worst "$deliv_rc"
fi

# The daemon can die between two reads of it. Say so rather than letting a later probe's worse code
# read as a contradiction of the header line this run already printed.
drift=""
if [ "$health_rc" = 0 ] && { [ "${status_rc:-0}" = 2 ] || [ "${deliv_rc:-0}" = 2 ]; }; then
  drift="the daemon was alive at the first read and down at a later one — every verdict above it is stale"
fi

if [ "$JSON" = 1 ]; then
  ORC_HEALTH_OUT="$health_out" ORC_HEALTH_RC="$health_rc" \
  ORC_STATUS_OUT="$status_out" ORC_STATUS_RC="$status_rc" \
  ORC_DELIV_OUT="$deliv_out" ORC_DELIV_RC="$deliv_rc" \
  ORC_GATED="$gated" ORC_DRIFT="$drift" ORC_EXIT="$worst" \
  python3 -c '
import json, os
def probe(o, r):
    return None if r == "" else {"exit": int(r), "text": os.environ[o]}
doc = {
  "health": probe("ORC_HEALTH_OUT", os.environ["ORC_HEALTH_RC"]),
  "status": probe("ORC_STATUS_OUT", os.environ["ORC_STATUS_RC"]),
  "deliverable": probe("ORC_DELIV_OUT", os.environ["ORC_DELIV_RC"]),
  "gated_by_health": os.environ["ORC_GATED"] == "1",
  "drift": os.environ["ORC_DRIFT"] or None,
  "exit": int(os.environ["ORC_EXIT"]),
}
print(json.dumps(doc, sort_keys=True))'
  exit "$worst"
fi

printf '── 1. fleet health ─────────────────────────────────────────── rc %s\n' "$health_rc"
printf '%s\n' "$health_out"
if [ "$gated" = 1 ]; then
  printf '\norchestrate: STOPPED. The registry could not be read, so no verdict may be claimed for\n'
  printf '             any session — not live, not stalled, not landed. Nothing downstream ran.\n'
  exit 3
fi
printf '\n── 2. session verdicts ─────────────────────────────────────── rc %s\n' "$status_rc"
printf '%s\n' "$status_out"
printf '\n── 3. deliverables ─────────────────────────────────────────── rc %s\n' "$deliv_rc"
printf '%s\n' "$deliv_out"
[ -z "$drift" ] || printf '\norchestrate: %s\n' "$drift"
printf '\norchestrate: exit %s (3 no verdict > 2 daemon down > 1 findings > 0 clean)\n' "$worst"
exit "$worst"
