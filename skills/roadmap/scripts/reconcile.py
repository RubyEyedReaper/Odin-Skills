"""Drift detection: does the roadmap still describe reality?

`analyze` is pure — it turns already-gathered evidence into findings, so it is fully
testable without git, `gh`, or a network. `gather_evidence` does the messy part.

Only cheap, reversible findings are auto-applicable. Promoting an item to `done` or
demoting one away from it always needs a human, otherwise reconciliation quietly
rewrites project history.
Stdlib only.
"""
from __future__ import annotations

import fnmatch
import glob
import json
import os
import re
import subprocess
from datetime import date

from . import schema as schema_mod
from .render import md_is_stale
from .schema import today_str

STALE_AFTER_DAYS = 14
RECONCILE_AFTER_DAYS = 7
READY_LABEL = "ready-for-agent"

# Per run, per channel. Same reasoning as `sweep.MAX_FINDINGS`: a bounded slice is readable and an
# unbounded one is a wall nobody scrolls. What is new is that the overflow is *counted* rather than
# dropped — `out[:20]` silently discarded 23 of this repository's own 43 unlinked CHANGELOG entries,
# which is the "instrument that will not admit it is blind" defect this change exists to remove.
MAX_CHANGELOG_UNLINKED = 20
MAX_UNLINKED_ISSUES = 20

# What a channel did, recorded per channel in `evidence["channel_status"]` (ADR-0069).
#
# `_run` used to return a bare `None` for both "the command produced nothing" and "the command could
# not run", and every caller collapsed the two into an empty result. A reconcile on a runner with no
# `gh` therefore printed exactly what a reconcile of a perfectly linked tracker prints, and a CI gate
# reading that output is green precisely when it is blind.
#
# `skipped` is deliberately not `unavailable`: `--no-git` / `--no-gh` are a caller's choice, and a
# gate that failed on them could never be run offline on purpose.
CHANNEL_RAN = "ran"
CHANNEL_SKIPPED = "skipped"
CHANNEL_UNAVAILABLE = "unavailable"
# A fourth state, distinct from all three above (ADR-0076). `skipped` is a caller's choice and
# `unavailable` is a blind spot; this is neither — the channel was not consulted because the
# question does not apply to this roadmap. Reported like the others, never silent: a filter that
# matches nothing is otherwise indistinguishable from a tracker with nothing to report, which is
# exactly the shape ADR-0069 exists to refuse.
CHANNEL_NOT_OWNED = "not-owned"

# Every kind `analyze` can emit. Its one consumer is `--fail-on`, which refuses a kind that is not
# in here rather than silently matching nothing — a typo'd gate that passes for the wrong reason is
# the same failure shape as the label that was never created (ADR-0069).
#
# Pinned by a test that reads the kinds out of `analyze` itself, so adding a kind without listing it
# here fails the suite rather than quietly becoming unselectable.
FINDING_KINDS = frozenset({
    "md-stale",
    "stale-item",
    "issue-closed",
    "untracked-issue",
    "unlinked-issue",
    "unlinked-issue-truncated",
    "false-done",
    "untracked-surface",
    "untracked-surface-truncated",
    "unrecorded-change",
    "unrecorded-change-truncated",
    "evidence-unavailable",
})

_ITEM_REF_RE = re.compile(r"\bRM-\d{4}\b")


def empty_evidence():
    return {
        "md_stale": False,
        "git_touched": {},
        "issues": [],
        "missing_files": {},
        "untracked_paths": [],
        "untracked_truncated": 0,
        "changelog_unlinked": [],
        "changelog_truncated": 0,
        "unlinked_issues": [],
        "unlinked_truncated": 0,
        "channel_status": {},
    }


def _days_between(start, end):
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except (TypeError, ValueError):
        return 0


def needs_reconcile(doc, today=None):
    last = doc.get("last_reconcile")
    if not last:
        return True
    return _days_between(last, today_str(today)) >= RECONCILE_AFTER_DAYS


def reconcile_status(doc, today=None):
    """The reconcile-due verdict, with the numbers a caller needs to say it out loud.

    `due` comes from `needs_reconcile` rather than a second comparison. A caller that needs the
    day count to compose a message is exactly how a threshold ends up restated somewhere else —
    which is the defect this function exists to stop (a hook carried its own copy, at 14, and
    shadowed the documented 7 for as long as it existed).
    """
    last = doc.get("last_reconcile")
    return {
        "last_reconcile": last,
        "days": _days_between(last, today_str(today)) if last else None,
        "threshold": RECONCILE_AFTER_DAYS,
        "due": needs_reconcile(doc, today),
    }


def _finding(kind, message, proposal, auto, item=None, payload=None):
    # `payload` carries the structured facts an applier needs. Without it an applier would have to
    # parse them back out of `message`, which is prose written for a human and free to change.
    return {
        "kind": kind,
        "item": item,
        "message": message,
        "proposal": proposal,
        "auto": auto,
        "payload": payload or {},
    }


def claims(path, patterns):
    """Does any of `patterns` — a `links.files` value — cover `path`?

    The single interpretation of that field. It held three before: `fnmatch` in `_git_touched`,
    `glob.glob` in `_missing_files`, and literal prefix comparison here — under which every
    glob-shaped claim (`.claude/rules/ci/**`, nearly half the live entries) matched nothing. Harmless
    only while nothing produced `untracked_paths`; the moment something does, a sweep reports the
    whole *claimed* surface as unclaimed and auto-apply mints an item per path, every run.

    Semantics, stated because a reader's shell intuition disagrees with `fnmatch`:

    * `*` **crosses `/`** — `fnmatch`'s does, and `_git_touched` has always relied on it. `**` is
      normalised to `*` so the two spellings cannot diverge.
    * A claim naming a directory covers everything beneath it, which is how these entries are
      written. `src/app` covers `src/app/billing/page.tsx` and **not** `src/append.ts` — the
      separator is required, so this is not a bare string prefix.
    * `fnmatchcase`, not `fnmatch`: paths here are repo-relative and case-sensitive, and the verdict
      must not depend on the runner's filesystem.
    """
    for pattern in patterns:
        pattern = str(pattern)
        if path == pattern:
            return True
        if fnmatch.fnmatchcase(path, pattern.replace("**", "*")):
            return True
        if path.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def _is_claimed(path, claimed):
    """True when some item's `links.files` already covers `path`.

    Symmetric with the issue check above, and for the same reason: without it a second
    `--apply-auto` run re-reports a path the first run just claimed and adds a duplicate item.
    Evidence producers are not required to filter — this is the layer that knows the doc.
    """
    return claims(path, claimed)


def _issue_keys(item):
    links = item.get("links") or {}
    keys = set()
    for issue in links.get("issues") or []:
        keys.add(str(issue).lstrip("#"))
    if links.get("prd"):
        keys.add(str(links["prd"]).lstrip("#"))
    return keys


def analyze(doc, evidence=None, today=None):
    """Turn evidence into findings. Deterministic, ordered, de-duplicated."""
    ev = evidence or empty_evidence()
    stamp = today_str(today)
    findings = []

    # First, because everything below it is conditional on having been able to look. A report that
    # opens with "no drift" and buries "gh could not run" is the report that produced this campaign.
    for channel in sorted(ev.get("channel_status") or {}):
        if (ev["channel_status"] or {}).get(channel) != CHANNEL_UNAVAILABLE:
            continue
        findings.append(_finding(
            "evidence-unavailable",
            "the `%s` evidence channel could not run — its findings are unknown, not absent"
            % channel,
            "make `%s` available, or pass the flag that skips it deliberately" % channel,
            False,
            payload={"channel": channel},
        ))

    if ev.get("md_stale"):
        findings.append(_finding(
            "md-stale",
            "ROADMAP.md does not match roadmap.json",
            "regenerate with `/roadmap render`",
            True,
        ))

    items = sorted(doc.get("items", []), key=lambda i: i.get("id", ""))
    linked = set()
    claimed = set()
    for item in items:
        linked |= _issue_keys(item)
        claimed |= {str(f) for f in ((item.get("links") or {}).get("files") or [])}

    for item in items:
        item_id = item.get("id")
        touched = ev.get("git_touched", {}).get(item_id)
        if item.get("status") == "in-progress" and not touched:
            since = item.get("updated") or item.get("created")
            age = _days_between(since, stamp)
            if age >= STALE_AFTER_DAYS:
                findings.append(_finding(
                    "stale-item",
                    "%s has been in-progress for %d days with no matching commits"
                    % (item_id, age),
                    "confirm it is still active, or move it back to `ready`",
                    False,
                    item_id,
                ))

    issues_by_number = {str(i.get("number")): i for i in ev.get("issues", [])}
    for item in items:
        if item.get("status") in ("done", "dropped"):
            continue
        for key in sorted(_issue_keys(item)):
            issue = issues_by_number.get(key)
            if issue and str(issue.get("state", "")).upper() == "CLOSED":
                findings.append(_finding(
                    "issue-closed",
                    "%s is %s but its issue #%s is closed"
                    % (item.get("id"), item.get("status"), key),
                    "confirm, then `/roadmap set %s status=done`" % item.get("id"),
                    False,
                    item.get("id"),
                ))
                break

    for issue in sorted(ev.get("issues", []), key=lambda i: str(i.get("number"))):
        if str(issue.get("state", "")).upper() != "OPEN":
            continue
        labels = [str(label) for label in (issue.get("labels") or [])]
        if READY_LABEL not in labels:
            continue
        if str(issue.get("number")) in linked:
            continue
        findings.append(_finding(
            "untracked-issue",
            "issue #%s (%s) is ready-for-agent but has no roadmap item"
            % (issue.get("number"), issue.get("title")),
            "add it as a `proposed` item",
            True,
            payload={"issue": str(issue.get("number")), "title": issue.get("title") or ""},
        ))

    # DEC-0014. `untracked-issue` above keys on READY_LABEL; this reports the rest. A separate
    # kind rather than a relaxed filter, because `APPLIERS` is a closed dict keyed by kind — a new
    # kind cannot reach `apply_auto` by construction, so the 77-item flood is impossible rather
    # than merely avoided. Relaxing the filter would also make `_apply_untracked_issue`'s own
    # "ready-for-agent" message text false for every finding it produced.
    unlinked_issues = []
    for issue in sorted(ev.get("issues", []), key=lambda i: str(i.get("number"))):
        if str(issue.get("state", "")).upper() != "OPEN":
            continue
        if READY_LABEL in [str(label) for label in (issue.get("labels") or [])]:
            continue  # already reported, actionably, as `untracked-issue`
        if str(issue.get("number")) in linked:
            continue
        unlinked_issues.append(issue)

    for issue in unlinked_issues[:MAX_UNLINKED_ISSUES]:
        findings.append(_finding(
            "unlinked-issue",
            "issue #%s (%s) is open but no roadmap item links it"
            % (issue.get("number"), issue.get("title")),
            "link it from an item, or capture it with `/roadmap add`",
            False,
            payload={"issue": str(issue.get("number")), "title": issue.get("title") or ""},
        ))

    dropped_issues = (ev.get("unlinked_truncated") or 0) + max(
        0, len(unlinked_issues) - MAX_UNLINKED_ISSUES)
    if dropped_issues:
        findings.append(_finding(
            "unlinked-issue-truncated",
            "%d further open issue(s) with no roadmap item were not reported (per-run cap)"
            % dropped_issues,
            "link or capture the reported ones, then reconcile again",
            False,
        ))

    for item in items:
        if item.get("status") != "done":
            continue
        missing = ev.get("missing_files", {}).get(item.get("id"))
        if missing:
            findings.append(_finding(
                "false-done",
                "%s is done but none of its files exist: %s"
                % (item.get("id"), ", ".join(missing)),
                "confirm, then reopen the item or correct `links.files`",
                False,
                item.get("id"),
            ))

    for path in sorted(ev.get("untracked_paths", [])):
        if _is_claimed(path, claimed):
            continue
        findings.append(_finding(
            "untracked-surface",
            "%s exists on disk but no roadmap item claims it" % path,
            "add it as a `proposed` item, or extend an item's `links.files`",
            True,
            payload={"path": path},
        ))

    dropped = ev.get("untracked_truncated") or 0
    if dropped:
        # Reported rather than silent: a sweep that drops findings without saying so makes the next
        # run's output depend on what this one happened to see. Not auto-applicable — the answer is
        # to claim some surfaces or narrow the roots, not to mint ten more items.
        findings.append(_finding(
            "untracked-surface-truncated",
            "%d further unclaimed surface(s) were not reported (per-run cap)" % dropped,
            "claim the reported ones, or narrow `surface_roots`, then reconcile again",
            False,
        ))

    for entry in ev.get("changelog_unlinked", []):
        findings.append(_finding(
            "unrecorded-change",
            "CHANGELOG entry references no roadmap item: %s" % entry.strip()[:120],
            "link it to an item, or capture the work as a `done` item",
            False,
        ))

    dropped_changes = ev.get("changelog_truncated") or 0
    if dropped_changes:
        findings.append(_finding(
            "unrecorded-change-truncated",
            "%d further unlinked CHANGELOG entr(ies) were not reported (per-run cap)"
            % dropped_changes,
            "link the reported ones, then reconcile again",
            False,
        ))

    return findings


def auto_applicable(findings):
    """Split findings into (auto-applicable, needs-confirmation)."""
    auto = [f for f in findings if f.get("auto")]
    manual = [f for f in findings if not f.get("auto")]
    return auto, manual


# ------------------------------------------------------------ appliers

def _apply_untracked_issue(doc, finding, today):
    number = finding.get("payload", {}).get("issue")
    if not number:
        return None
    title = finding.get("payload", {}).get("title") or ("issue #%s" % number)
    links = schema_mod.empty_links()
    links["issues"] = [str(number)]
    return schema_mod.add_item(
        doc, title=title, kind="feature", today=today,
        tier="next", links=links,
        notes="reconcile: issue #%s is ready-for-agent; confirm scope or drop" % number,
    )


def _apply_untracked_surface(doc, finding, today):
    path = finding.get("payload", {}).get("path")
    if not path:
        return None
    links = schema_mod.empty_links()
    links["files"] = [path]
    return schema_mod.add_item(
        doc, title="Account for %s" % path, kind="research", today=today,
        tier="someday", links=links,
        notes="reconcile: on disk, claimed by no item; confirm, reassign or drop",
    )


# `md-stale` is auto-applicable and deliberately absent: its application is the re-render, which
# `cmd_reconcile` performs on every run. An entry here would either duplicate that or lie about it.
APPLIERS = {
    "untracked-issue": _apply_untracked_issue,
    "untracked-surface": _apply_untracked_surface,
}


def apply_auto(doc, findings, today=None):
    """Apply every auto-applicable finding with an applier. Mutates `doc`; returns the new items.

    Each new item lands as `proposed` with a `notes` line naming reconcile as its source, because
    an item nobody chose still has to be confirmed or dropped by a human. Re-running is safe: the
    item carries the link (`links.issues` / `links.files`) that made the finding fire, so the next
    `analyze` no longer sees it as untracked.
    """
    added = []
    for finding in findings:
        if not finding.get("auto"):
            continue
        applier = APPLIERS.get(finding.get("kind"))
        if applier is None:
            continue
        item = applier(doc, finding, today)
        if item is not None:
            added.append(item)
    return added


# ------------------------------------------------------------ evidence gathering

def _run(args, cwd=None):
    """`(stdout, status)` — the output, and whether the command could run at all.

    The status is the whole point. Returning a bare `None` for both failure and emptiness is what
    made "could not look" and "looked, saw nothing" indistinguishable at every call site.
    """
    try:
        result = subprocess.run(
            args, cwd=cwd, check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None, CHANNEL_UNAVAILABLE
    return result.stdout, CHANNEL_RAN


def _git_touched(root, items, since_days=STALE_AFTER_DAYS):
    """`(touched, status)` — commits per item, and whether git could be consulted."""
    out, status = _run(
        ["git", "log", "--since=%d.days" % since_days, "--name-only", "--pretty=format:"],
        cwd=root,
    )
    if not out:
        return {}, status
    changed = [line.strip() for line in out.splitlines() if line.strip()]
    touched = {}
    for item in items:
        patterns = (item.get("links") or {}).get("files") or []
        hits = [path for path in changed if claims(path, patterns)]
        if hits:
            touched[item.get("id")] = sorted(set(hits))[:10]
    return touched, status


def owns_tracker(root):
    """`(owns, status)` — may this roadmap's repository be asked to account for the tracker?

    `_gh_issues` runs `gh` with `cwd=root`, and `gh` resolves the repository by walking *up* from
    there. A roadmap in a subtree — `projects/<x>/docs/roadmap/` — therefore queries a tracker it
    never named, and every open issue in the enclosing repository comes back as its drift. Measured
    before this existed: the harness roadmap reported zero unlinked issues while each project
    roadmap reported eight plus "14 further open issue(s) … were not reported".

    The predicate is the layout, mirroring `schema.derive_slug`: a roadmap owns the tracker when its
    own root **is** the git toplevel. That is correct for every case without a schema change and
    without a special case — the harness roadmap sits at the toplevel and owns Odin's tracker; a
    project subtree sits below it and owns none; a project that is its own repository (a submodule,
    or one extracted later) starts owning its own tracker the moment that becomes true.

    An explicit `tracker` field was rejected for now (DEC-0030): no project has its own tracker, and
    `slug` is the cautionary precedent — a declared-optional field with no writer, populable only by
    the hand edit this system forbids. If one is ever added, its writer ships in the same commit.

    **Failure is not non-ownership.** When the probe cannot run, the answer is `unavailable`, so the
    caller falls back to consulting the tracker rather than silently claiming nothing is owed.
    "Could not look" must never collapse into "nothing to look at" (ADR-0069).
    """
    out, status = _run(["git", "-C", root, "rev-parse", "--show-toplevel"], cwd=root)
    if status != CHANNEL_RAN or not (out or "").strip():
        return None, CHANNEL_UNAVAILABLE
    toplevel = os.path.realpath(out.strip())
    return os.path.realpath(root) == toplevel, CHANNEL_RAN


def _gh_issues(root):
    """`(issues, status)` — the tracker's issues, and whether the tracker could be reached.

    Unparseable output is `unavailable`, not `ran`: `gh` answered with something this code cannot
    read, so the channel saw nothing and knows it.
    """
    out, status = _run(
        ["gh", "issue", "list", "--state", "all", "--limit", "200",
         "--json", "number,title,state,labels"],
        cwd=root,
    )
    if not out:
        return [], status
    try:
        raw = json.loads(out)
    except ValueError:
        return [], CHANNEL_UNAVAILABLE
    issues = []
    for entry in raw:
        issues.append({
            "number": entry.get("number"),
            "title": entry.get("title"),
            "state": entry.get("state"),
            "labels": [lbl.get("name") for lbl in entry.get("labels") or []],
        })
    return issues, status


def escapes_root(pattern):
    """True when a `links.files` pattern would resolve outside the repository.

    `_missing_files` joins these onto the repo root and hands the result to `glob`, so an absolute
    pattern or one containing `..` reaches the filesystem outside the boundary — a doc-supplied path
    used without a check (`.claude/rules/cli/security.md`). `validate()` rejects these at the source;
    this is the second line, for a document written before that check existed.

    One implementation, in `schema`. A second copy here is the exact defect this change removes.
    """
    return schema_mod.pattern_escapes_root(pattern)


def _missing_files(root, items):
    missing = {}
    for item in items:
        patterns = (item.get("links") or {}).get("files") or []
        if not patterns:
            continue
        unresolved = [
            pattern for pattern in patterns
            if escapes_root(pattern)
            or not glob.glob(os.path.join(root, pattern), recursive=True)
        ]
        if unresolved and len(unresolved) == len(patterns):
            missing[item.get("id")] = unresolved
    return missing


def _changelog_unlinked(root, doc):
    """`(entries, dropped)` — dated CHANGELOG entries naming no roadmap item, bounded and counted.

    A null `last_reconcile` means **examine everything**, not "examine nothing" (#188). The early
    return this replaced made the channel unable to fire on a roadmap that had never been
    reconciled — which is every roadmap, until a reconcile that by construction had nothing to
    report has stamped it. Under that shape the source could only ever describe history it had
    already seen, so a backlog accumulated beneath a standing `no drift`.

    A reconciled roadmap keeps the incremental filter: re-reporting entries a human already
    dispositioned is how a drift report becomes noise nobody reads.
    """
    path = os.path.join(root, "CHANGELOG.md")
    if not os.path.exists(path):
        return [], 0
    last = doc.get("last_reconcile")
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    out = []
    for line in lines:
        if not line.startswith("- **"):
            continue
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", line)
        if not dates:
            continue
        if last and max(dates) <= last:
            continue
        if not _ITEM_REF_RE.search(line):
            out.append(line)
    if len(out) <= MAX_CHANGELOG_UNLINKED:
        return out, 0
    return out[:MAX_CHANGELOG_UNLINKED], len(out) - MAX_CHANGELOG_UNLINKED


def gather_evidence(json_path, doc, run_git=True, run_gh=True, surface_roots=None):
    from .schema import paths_for

    paths = paths_for(json_path)
    root = paths["root"]
    items = doc.get("items", [])
    ev = empty_evidence()
    ev["md_stale"] = md_is_stale(json_path)
    ev["channel_status"]["git"] = CHANNEL_SKIPPED
    ev["channel_status"]["gh"] = CHANNEL_SKIPPED
    if run_git:
        ev["git_touched"], ev["channel_status"]["git"] = _git_touched(root, items)
        # The sweep enumerates from git, so `--no-git` disables it. That is the honest reading of
        # the flag: there is deliberately no filesystem fallback, because a hand-written ignore
        # list would report a different set of paths than git does — and under `--apply-auto` the
        # difference becomes items in the canonical file.
        from . import sweep as sweep_mod
        ev["untracked_paths"], ev["untracked_truncated"] = sweep_mod.untracked_surfaces(
            root, doc, override=surface_roots,
        )
    if run_gh:
        # Applied here rather than in `analyze`, and deliberately so. `MAX_UNLINKED_ISSUES` is
        # applied *inside* `analyze`, so a filter placed after it would already have discarded owned
        # issues in favour of foreign ones — the crowding-out this defect reports. Placing it at the
        # evidence boundary also means `reconcile --apply-auto` inherits it: `untracked-issue` is
        # auto-applicable off this same list, so an unscoped one would mint a foreign repository's
        # issues into a project's canonical file. A predicate in the gate script could reach neither
        # (DEC-0015: the severity decision lives in Python, and the gate never parses the report).
        owns, _probe = owns_tracker(root)
        if owns is False:
            ev["channel_status"]["gh"] = CHANNEL_NOT_OWNED
        else:
            # `owns is True`, or the probe itself failed — in which case consult the tracker exactly
            # as before. Failing *open* is the deliberate direction: an unreadable probe leaves the
            # verdict identical to today's rather than inventing a new way for the gate to redden on
            ev["issues"], ev["channel_status"]["gh"] = _gh_issues(root)
    # Disk is the one channel with no external dependency: `_missing_files` and `_changelog_unlinked`
    # are filesystem reads that either succeed or raise. It is recorded anyway so the status map
    # enumerates every channel rather than only the fragile ones — a consumer asking "did disk run?"
    # should get an answer, not a `KeyError`.
    ev["channel_status"]["disk"] = CHANNEL_RAN
    ev["missing_files"] = _missing_files(root, items)
    ev["changelog_unlinked"], ev["changelog_truncated"] = _changelog_unlinked(root, doc)
    return ev


def reconcile(json_path, doc, today=None, run_git=True, run_gh=True, surface_roots=None):
    evidence = gather_evidence(
        json_path, doc, run_git=run_git, run_gh=run_gh, surface_roots=surface_roots,
    )
    findings = analyze(doc, evidence, today=today)
    auto, manual = auto_applicable(findings)
    return {
        "findings": findings,
        "auto": auto,
        "manual": manual,
        "evidence": evidence,
    }
