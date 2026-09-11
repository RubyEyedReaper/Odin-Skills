#!/usr/bin/env bash
#
# project-status — the portfolio layer over `projects/*/`. Read-only, and it composes.
#
# WHAT THIS IS. `projects` owns one project: the routing table, the switch ritual, the artifact
# checklist (ADR-0106). Nothing owned the question one layer up — *which* projects exist, which are
# being worked on, which have drifted, and which are owed something. That question is asked before
# a campaign picks its slices and before a coordinator decides where a wave goes, and until now it
# was answered by reading five directories by hand.
#
# IT COMPOSES, IT NEVER RE-DERIVES. Every predicate below already has exactly one owner in this
# tree, and this program calls it:
#
#   nested-repo landedness   `bl_classify`            .claude/scripts/lib/branch-landedness.sh
#   the skills mirror        `sp_mirror_state`        .claude/scripts/lib/skill-provenance.sh
#   where a roadmap lives    `roadmap_candidates`     .claude/scripts/lib/roadmap-discovery.sh
#   which docs are protected `odin-project-doc-guard.sh --scan`
#
# A second copy of any of those would have no way to disagree out loud, which is the failure
# `one-implementation-check.sh` prosecutes. What this file owns is the JOIN and nothing else.
#
# `undetermined` IS NOT A VERDICT, AND IT IS NEVER FOLDED INTO ONE. Four recorded occurrences of
# `error-path/unreadable-input-returned-a-substantive-verdict` are functions that composed a path,
# a probe or a join on an input they had never established and answered with a real word anyway —
# `disjoint` for a root that was a branch name, `absent` for an argument that was not a directory,
# `failed` for a live worker. So every dimension here answers `undetermined` when its own input
# could not be read, that answer is printed rather than dropped, and a project carrying one is
# reported separately from a project that is clean (`cli/coding-style.md` § A Verdict Requires an
# Input You Actually Read).
#
# PRESENCE IS MEASURED BEFORE ANYTHING ELSE. A `projects/<slug>/` that is an uninitialised
# submodule is an EMPTY DIRECTORY in this checkout, and every other dimension asked about it
# answers about the harness instead. Both defects were found by this program's first run against
# the live tree and are recorded at `ps_is_repo_root` and `ps_presence`.
#
# ACTIVITY IS A NUMBER FIRST AND A WORD SECOND. `active` / `dormant` is a reading of a day count
# against a threshold, and the threshold is a judgment nobody here gets to make silently — so the
# count is always printed and `--dormant-days` is a declared flag. A verdict whose input the reader
# cannot see is a verdict the reader cannot disagree with.
#
# WHAT IT DOES NOT DO. It changes nothing, ever: no fetch, no checkout, no write, no cleanup. It
# does not run any project's gate — a portfolio probe that spent an hour per project would be run
# once and then avoided. It does not decide what to work on; that is `roadmap`, and for a fleet it
# is `gauntlet frontier`.
#
# Usage: project-status.sh <root> [--json] [--dormant-days N] [--project SLUG]
# Exit: 0 every project reported, none undetermined · 1 at least one dimension is undetermined
#       · 2 could not look — no root, no projects directory, or nothing under it
set -uo pipefail

ROOT=""
AS_JSON=0
DORMANT_DAYS=30
ONLY=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --json) AS_JSON=1; shift ;;
    --dormant-days) DORMANT_DAYS="${2:-}"; shift 2 ;;
    --project) ONLY="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '3,40p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*) echo "project-status: unknown flag: $1" >&2; exit 2 ;;
    *) [ -z "$ROOT" ] && ROOT="$1" || { echo "project-status: unexpected argument: $1" >&2; exit 2; }
       shift ;;
  esac
done

if [ -z "$ROOT" ]; then
  echo "project-status: usage: project-status.sh <root> [--json] [--dormant-days N] [--project SLUG]" >&2
  exit 2
fi
if [ ! -d "$ROOT" ]; then
  echo "project-status: cannot look — no such directory: $ROOT" >&2
  exit 2
fi
case "$DORMANT_DAYS" in
  ''|*[!0-9]*) echo "project-status: --dormant-days must be a whole number of days, got '$DORMANT_DAYS'" >&2; exit 2 ;;
esac

PROJECTS_DIR="$ROOT/projects"
if [ ! -d "$PROJECTS_DIR" ]; then
  echo "project-status: cannot look — no projects directory at $PROJECTS_DIR" >&2
  exit 2
fi

slugs=()
while IFS= read -r d; do
  [ -n "$d" ] || continue
  n="${d%/}"; n="${n##*/}"
  [ -n "$ONLY" ] && [ "$n" != "$ONLY" ] && continue
  slugs+=("$n")
done < <(find "$PROJECTS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

if [ "${#slugs[@]}" -eq 0 ]; then
  if [ -n "$ONLY" ]; then
    echo "project-status: cannot look — no project named '$ONLY' under $PROJECTS_DIR" >&2
  else
    echo "project-status: cannot look — no projects under $PROJECTS_DIR" >&2
    echo "    An empty enumeration is not an empty portfolio; the scan found nothing to report on." >&2
  fi
  exit 2
fi

# The incumbents. Sourced, never reimplemented; a missing library is "could not look", because a
# fallback copy is exactly the second implementation this program is built to avoid.
for lib in branch-landedness.sh skill-provenance.sh; do
  if [ -r "$ROOT/.claude/scripts/lib/$lib" ]; then
    # shellcheck disable=SC1090
    . "$ROOT/.claude/scripts/lib/$lib"
  else
    echo "project-status: cannot look — missing $ROOT/.claude/scripts/lib/$lib" >&2
    echo "    That library owns a predicate this program composes; a local copy of it would be" >&2
    echo "    a second answer with no way to disagree out loud." >&2
    exit 2
  fi
done

undetermined_total=0

# ps_is_repo_root <dir> — true only when <dir> IS a repository root, not merely inside one.
#
# THE DEFECT THIS EXISTS FOR, found by this program's own first run against the live tree. `git -C
# <dir> rev-parse --git-dir` SUCCEEDS for any directory inside a repository, because git walks up.
# A `projects/<slug>/` that is a plain subdirectory therefore answered every branch question with
# the HARNESS's branches — four projects reported the identical "8 unlanded, 13 landed", which is
# the harness's own branch set, attributed to four repositories that do not have one.
#
# It is `common/security.md` § Name the Target, Don't Infer It, one layer in: the command resolved
# its target from ambient position rather than from its argument, and reported a real-looking answer
# about the wrong repository. Four agreeing numbers is what made it visible, exactly as in the
# `bl_classify` incident that library's own header records.
ps_is_repo_root() {
  local dir="$1" top
  top="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || return 1
  [ -n "$top" ] || return 1
  [ "$(cd "$dir" 2>/dev/null && pwd -P)" = "$(cd "$top" 2>/dev/null && pwd -P)" ]
}

# ps_presence <root> <slug> — populated | uninitialised | empty.
#
# THE SECOND DEFECT THIS PROGRAM'S OWN FIRST RUN FOUND, and the more dangerous one: two projects
# reported `missing: README.md CHANGELOG.md docs/adr/ docs/roadmap/roadmap.json`. Both are real,
# well-documented repositories. The directories were simply EMPTY in this worktree, because a
# submodule that has not been initialised here is an empty directory and nothing else.
#
# A probe that reads an empty directory and reports four missing artifacts has not found four gaps.
# It has failed to look, and said something specific and false about a project as a result — the
# same shape `sp_mirror_state` is four-valued to avoid, which is why that function is cited above
# rather than a boolean being invented here.
#
# So presence is measured FIRST, and when it is not `populated` every other dimension is
# `undetermined` and the artifact list is not printed at all. Absence of evidence, stated as such.
ps_presence() {
  local root="$1" slug="$2" dir="$1/projects/$2"
  [ -d "$dir" ] || { echo empty; return; }
  [ -n "$(ls -A "$dir" 2>/dev/null)" ] && { echo populated; return; }
  if [ -f "$root/.gitmodules" ] && grep -q "projects/$slug" "$root/.gitmodules" 2>/dev/null; then
    echo uninitialised; return
  fi
  echo empty
}

# ps_days_since_commit <repo> <pathspec|-> — whole days since the last commit, or `undetermined`.
ps_days_since_commit() {
  local repo="$1" spec="$2" when now
  if [ "$spec" = "-" ]; then
    # The whole-repo form asks about THIS repository, so the argument must BE one.
    ps_is_repo_root "$repo" || { echo undetermined; return; }
  else
    git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || { echo undetermined; return; }
  fi
  if [ "$spec" = "-" ]; then
    when="$(git -C "$repo" log -1 --format=%ct 2>/dev/null)"
  else
    when="$(git -C "$repo" log -1 --format=%ct -- "$spec" 2>/dev/null)"
  fi
  case "$when" in
    ''|*[!0-9]*) echo undetermined; return ;;
  esac
  now="$(date +%s)"
  echo $(( (now - when) / 86400 ))
}

# ps_artifacts <dir> — which of the four per-project artifacts the `projects` checklist names are
# present. Reports the missing ones by name; a count alone does not say what to write.
ps_artifacts() {
  local dir="$1" missing=""
  [ -f "$dir/README.md" ]                  || missing="$missing README.md"
  [ -f "$dir/CHANGELOG.md" ]               || missing="$missing CHANGELOG.md"
  [ -d "$dir/docs/adr" ]                   || missing="$missing docs/adr/"
  [ -f "$dir/docs/roadmap/roadmap.json" ]  || missing="$missing docs/roadmap/roadmap.json"
  printf '%s' "${missing# }"
}

# ps_roadmap <dir> — "<open>/<total>" from the project's own roadmap, or `undetermined`.
#
# Read with python3 from the canonical JSON. Never from the generated ROADMAP.md: that file is
# regenerated from this one, so a stale copy of it reports a portfolio that has already moved.
ps_roadmap() {
  local file="$1/docs/roadmap/roadmap.json"
  [ -f "$file" ] || { echo undetermined; return; }
  python3 - "$file" <<'PY' 2>/dev/null || echo undetermined
import json, sys
OPEN = {"proposed", "ready", "in-progress"}
try:
    items = json.load(open(sys.argv[1]))["items"]
except Exception:
    raise SystemExit(1)
print("%d/%d" % (sum(1 for i in items if i.get("status") in OPEN), len(items)))
PY
}

# ps_unlanded <dir> — local branches whose work is not on the project's default branch.
#
# Every verdict comes from `bl_classify`, including its refusals: a branch it could not measure is
# counted as undetermined and never as landed. Silence about a branch is indistinguishable from
# that branch being clean, which is the whole reason this counts three buckets and not one.
ps_unlanded() {
  local dir="$1" base verdict landed=0 unlanded=0 unknown=0 b
  # Not `rev-parse --git-dir`: that succeeds for any path inside a repository, so a plain
  # subdirectory would be answered with the enclosing harness's branches. See ps_is_repo_root.
  ps_is_repo_root "$dir" || { echo not-a-repository; return; }

  base=""
  for candidate in main master; do
    git -C "$dir" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1 && { base="$candidate"; break; }
  done
  [ -n "$base" ] || { echo undetermined; return; }

  while IFS= read -r b; do
    [ -n "$b" ] || continue
    [ "$b" = "$base" ] && continue
    verdict="$(bl_classify "$dir" "$b" "$base" 2>/dev/null)"
    case "$verdict" in
      landed|contained) landed=$((landed + 1)) ;;
      evidence-unavailable|undetermined|'') unknown=$((unknown + 1)) ;;
      *) unlanded=$((unlanded + 1)) ;;
    esac
  done < <(git -C "$dir" for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null)

  printf '%d unlanded, %d landed, %d unmeasured' "$unlanded" "$landed" "$unknown"
}

# ── report ───────────────────────────────────────────────────────────────────

rows_json=""
for slug in "${slugs[@]}"; do
  dir="$PROJECTS_DIR/$slug"

  presence="$(ps_presence "$ROOT" "$slug")"

  if [ "$presence" != "populated" ]; then
    # Nothing further is measurable, and every number this probe could print about an empty
    # directory would be about the harness rather than about the project.
    undetermined_total=$((undetermined_total + 1))
    if [ "$AS_JSON" -eq 1 ]; then
      rows_json="$rows_json{\"project\":\"$slug\",\"presence\":\"$presence\",\"activity\":\"undetermined\",\"days_since_last_commit\":null,\"missing_artifacts\":null,\"roadmap_open_of_total\":null,\"branches\":\"undetermined\"},"
    else
      printf '%-22s %-12s %s\n' "$slug" "$presence" \
        "$([ "$presence" = uninitialised ] \
            && echo "submodule not checked out here — nothing measurable, and an empty directory is not a project with missing files" \
            || echo "directory is empty and .gitmodules does not declare it")"
    fi
    continue
  fi

  nested="no"
  [ -e "$dir/.git" ] && nested="yes"

  # Activity is measured inside the nested repo when there is one, and from the harness's own log
  # over that path when there is not. A plain subdirectory has no history of its own, and reading
  # the harness's would otherwise report every project as active on the day the harness moved.
  if [ "$nested" = "yes" ]; then
    days="$(ps_days_since_commit "$dir" -)"
  else
    days="$(ps_days_since_commit "$ROOT" "projects/$slug")"
  fi

  case "$days" in
    undetermined) activity="undetermined"; undetermined_total=$((undetermined_total + 1)) ;;
    *) if [ "$days" -le "$DORMANT_DAYS" ]; then activity="active"; else activity="dormant"; fi ;;
  esac

  missing="$(ps_artifacts "$dir")"
  roadmap="$(ps_roadmap "$dir")"
  [ "$roadmap" = "undetermined" ] && undetermined_total=$((undetermined_total + 1))

  unlanded="$(ps_unlanded "$dir")"
  # `not-a-repository` is a MEASUREMENT — the probe looked and established the directory is not a
  # repository root. Only `undetermined` counts as an input it could not read; folding a fact into
  # that bucket would report an answer as a gap.
  [ "$unlanded" = "undetermined" ] && undetermined_total=$((undetermined_total + 1))

  if [ "$AS_JSON" -eq 1 ]; then
    rows_json="$rows_json$(python3 - "$slug" "$nested" "$activity" "$days" "$missing" "$roadmap" "$unlanded" <<'PY'
import json, sys
slug, nested, activity, days, missing, roadmap, unlanded = sys.argv[1:8]
print(json.dumps({
    "project": slug,
    "presence": "populated",
    "nested_repo": nested == "yes",
    "activity": activity,
    "days_since_last_commit": None if days == "undetermined" else int(days),
    "missing_artifacts": missing.split() if missing else [],
    "roadmap_open_of_total": None if roadmap == "undetermined" else roadmap,
    "branches": unlanded,
}))
PY
),"
  else
    printf '%-22s %-12s %-22s roadmap %-12s %s\n' \
      "$slug" \
      "$activity" \
      "$([ "$days" = undetermined ] && echo "(age unmeasured)" || echo "last commit ${days}d ago")" \
      "$roadmap" \
      "$unlanded"
    [ -n "$missing" ] && printf '%-22s   missing: %s\n' "" "$missing"
  fi
done

# The two portfolio-wide facts, reported once. `sp_mirror_state` is four-valued deliberately: an
# unpopulated submodule directory is not an empty mirror, and reporting it as one is how a sync
# gets run against nothing.
mirror="$(sp_mirror_state "$ROOT" 2>/dev/null || echo undetermined)"
[ "$mirror" = "undetermined" ] && undetermined_total=$((undetermined_total + 1))

if [ "$AS_JSON" -eq 1 ]; then
  printf '{"projects":[%s],"skills_mirror":"%s","undetermined_dimensions":%d,"dormant_after_days":%d}\n' \
    "${rows_json%,}" "$mirror" "$undetermined_total" "$DORMANT_DAYS"
else
  printf '\nskills mirror: %s · %d project(s) · dormant after %d day(s)\n' \
    "$mirror" "${#slugs[@]}" "$DORMANT_DAYS"
  if [ "$undetermined_total" -gt 0 ]; then
    printf '%d dimension(s) undetermined — an input this probe could not read, reported rather than\n' "$undetermined_total" >&2
    printf 'folded into a verdict. Each is a finding about the probe or the project, never a reading.\n' >&2
  fi
fi

[ "$undetermined_total" -eq 0 ] || exit 1
exit 0
