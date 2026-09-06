#!/usr/bin/env python3
"""gauntlet — the frontier, the wave it re-arms with, and the refusal to call a batch finished.

WHAT THIS ENGINE OWNS, AND WHAT IT DELIBERATELY DOES NOT.

It owns three questions nothing else in this repository answers:

  * `frontier` — what open work exists RIGHT NOW, across every channel, ordered quick-win first.
  * `rearm`    — which of it goes in the next wave, refusing to co-schedule two items whose
                 declared surfaces intersect.
  * `verify`   — may this batch be called finished? It calls `campaign close` rather than
                 re-deciding landedness, and adds the one question `close` does not ask:
                 what has APPEARED since the batch was pinned.

It owns none of: landedness (`bl_classify`, via `campaign`), a session's liveness
(`successor-manager`), a loop's contract or ledger (`work-loop`), scheduling (`revive`). Each is
called or cited, never reimplemented — two copies of a rule drift and the looser copy wins.

THE STANCE: THE FRONTIER IS COMPUTED, NEVER STORED.

A frontier is a status, and ADR-0113's finding is that a stored status reads identically whether it
is current or six hours old — measured in this repository at 31 of 43 issues already fixed while the
tracker still said otherwise. So nothing here writes state. `rearm` prints a wave; a human or a
coordinator copies it into the campaign manifest, which stores the PLAN.

THE OTHER STANCE: "I COULD NOT LOOK" IS NOT "THERE IS NOTHING".

Every channel below can fail to be read, and each failure is `undetermined` (exit 2) rather than an
empty contribution. A gauntlet that reports an empty frontier because `gh` was unauthenticated is
the exact shape of a campaign declared complete with work still open.

EXIT CODES — the interface, so a caller greps nothing.

  frontier   0 the frontier is EMPTY and every channel was read
             1 work remains (the ordinary case; this is a finding, not a failure)
             2 undetermined — a channel could not be read
            64 usage
  rearm      0 a wave was emitted
             3 no wave — the frontier holds nothing assignable
             2 undetermined
            64 usage
  verify     0 the batch may close AND the frontier is empty — the only "finished" there is
             1 refused — items unlanded, or new work has appeared since the batch was pinned
             2 undetermined
            64 usage

`rearm`'s "nothing to assign" is 3 rather than 1 on purpose: it is not a refusal and not an error,
and a caller that cannot tell it from "a wave was emitted" cannot drive the loop.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys

EXIT_OK = 0
EXIT_WORK_REMAINS = 1
EXIT_UNDETERMINED = 2
EXIT_NOTHING_TO_ASSIGN = 3
EXIT_USAGE = 64

ROADMAP_REL = os.path.join(".claude", "docs", "roadmap", "roadmap.json")
CAMPAIGNS_REL = os.path.join(".claude", "docs", "campaigns")
CAMPAIGN_SKILL_REL = os.path.join(".claude", "skills", "campaign")
WORKLOOP_REL = os.path.join(".claude", ".runtime", "work-loop")

#: Statuses that put an item on the frontier. `ready` is included and `dropped` is not: the
#: roadmap engine's STATUSES is (proposed, ready, in-progress, done, dropped), and there is no
#: `blocked` — blockedness is DERIVED here, never stored. See the skill body, Fork 5.
OPEN_STATUSES = ("proposed", "ready", "in-progress")

#: Gain proxy, read from `tier`. Declared on every open item in this repository, which is why it
#: is the fallback rather than an invented constant: a default nobody declared is a guess wearing
#: a measurement's clothes.
TIER_GAIN = {"now": 3.0, "next": 2.0, "later": 1.0, "someday": 0.5}

#: Reversibility proxy, read from `kind`. The roadmap engine's KINDS, grouped by how much of the
#: world a change of that kind can touch. A number here is a ranking, not a probability.
KIND_REVERSIBILITY = {
    "docs": 1.0, "ops": 1.0, "research": 1.0,
    "infra": 0.75,
    "feature": 0.5, "page": 0.5, "function": 0.5, "integration": 0.5,
    "data": 0.25,
}

#: `priority.score` is a weighted-sum total on a 0-100 scale (decision-matrix). Divided by this it
#: lands on the same scale as the tier proxy, so one item's recorded DEC and another's tier are
#: comparable in the same ordering rather than one swamping the other.
SCORE_DIVISOR = 25.0

#: Branch prefix by kind — the change classes CLAUDE.md item 7 names.
KIND_BRANCH_PREFIX = {"docs": "docs", "research": "docs"}
DEFAULT_BRANCH_PREFIX = "harness"


class Undetermined(Exception):
    """A channel could not be read. Never converted to an empty contribution."""


# ------------------------------------------------------------------ helpers

def _check_root(root: str) -> None:
    """A root is validated before it is used, never assumed.

    `git -C ""` means the *current* repository, and an engine handed an empty root does not
    fail — it silently answers about whatever tree the process happens to be in.
    """
    if not root or not isinstance(root, str) or not os.path.isdir(root):
        raise Undetermined(f"refusing to run against an unusable root: {root!r}")
    if not os.path.isabs(root):
        # A relative root is not wrong here, but it becomes wrong the moment it is handed to a
        # subprocess with a different cwd — `verify` runs `campaign close` from inside the
        # campaign skill directory, where `../../..` resolves to a different tree only by luck
        # of matching depth. Absolutise once, at the boundary.
        raise Undetermined(
            f"root must be absolute once it leaves this process: {root!r} — "
            "pass an absolute path, or let main() resolve it"
        )


def _run(argv: list[str], cwd: str | None = None, timeout: int = 60) -> tuple[int, str, str]:
    """Run a command; return (rc, stdout, stderr). A missing program is rc 127, not a crash."""
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return 127, "", f"no such program: {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s: {' '.join(argv)}"
    return proc.returncode, proc.stdout, proc.stderr


def _roadmap_schema(root: str):
    """The roadmap engine's own `schema` module, loaded rather than reimplemented.

    The slug rule — the half of `harness:RM-0372` before the colon — belongs to that engine.
    A copy of it here reads every qualified id in this repository as foreign the first time
    the rule changes.
    """
    import importlib.util

    path = os.path.join(root, ".claude", "skills", "roadmap", "scripts", "schema.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("_gauntlet_roadmap_schema", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # an engine this one cannot load is a channel it cannot read
        return None
    return module


# ------------------------------------------------------------------ channel: roadmap

def read_roadmap(root: str) -> tuple[str | None, list[dict]]:
    """(slug, items). Unreadable is `Undetermined`, never an empty roadmap."""
    path = os.path.join(root, ROADMAP_REL)
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise Undetermined(f"roadmap could not be read: {path}: {exc}") from exc
    items = doc.get("items") if isinstance(doc, dict) else doc
    if not isinstance(items, list):
        raise Undetermined(f"roadmap has no item list: {path}")

    slug = doc.get("slug") if isinstance(doc, dict) else None
    if not slug:
        module = _roadmap_schema(root)
        if module is not None:
            try:
                slug = module.slug_of(doc if isinstance(doc, dict) else {}, path)
            except Exception:
                slug = None
    return slug, [item for item in items if isinstance(item, dict)]


def blockedness(item: dict, by_id: dict) -> str | None:
    """Derived, never stored.

    The roadmap schema has no `blocked` status, so an item is blocked when a channel that
    already exists says so: an unmet `deps` edge, or an escalate record naming it (added by
    the caller through `escalated`). Absence of a dep is not evidence that nothing blocks it —
    it is the absence of that one kind of evidence.
    """
    for dep in item.get("deps") or []:
        target = by_id.get(dep)
        if target is None:
            return f"blocked-by-dep:{dep} (no such item)"
        if target.get("status") not in ("done", "dropped"):
            return f"blocked-by-dep:{dep}"
    return None


def escalated_items(root: str) -> set[str]:
    """Item ids named by a work-loop escalate record.

    An unreadable ledger directory is NOT `Undetermined`: in-flight loop state is a runtime
    class that may legitimately be absent, and treating "no loops have run here" as a channel
    failure would make every fresh checkout undetermined forever. What it costs is stated in
    the skill body: an external blocker recorded nowhere else is invisible to this reading.
    """
    out: set[str] = set()
    base = os.path.join(root, WORKLOOP_REL)
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(base, name)
        try:
            with open(path, encoding="utf-8") as handle:
                ledger = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            # A file that EXISTS and cannot be read is a failure, not a skip — the same rule
            # `read_campaign_items` already applies. Skipping it dropped an externally-blocked
            # item back into the assignable set while the channel still reported `read`, which
            # is `error-path/unreadable-input-returned-a-substantive-verdict`. The *absent*
            # directory stays absent; only unreadable content raises.
            raise Undetermined(f"work-loop ledger could not be read: {path}: {exc}") from exc

        records = ledger.get("iterations") or []
        for position, record in enumerate(records):
            if record.get("outcome") != "escalate":
                continue
            # An escalate is terminal in `work-loop`'s six outcomes, so an iteration recorded
            # after it means the loop was re-opened and this record is history. Without this a
            # blocker never expires — the item stays blocked until somebody deletes the file.
            if any(later.get("outcome") for later in records[position + 1:]):
                continue
            # `blocker` and `evidence` describe WHAT STOPPED. `recommended_next` describes what
            # to do instead, so an id there names the successor, not the casualty: a record
            # reading "do RM-1 next instead" marked RM-1 blocked and left the item the
            # escalation was actually about assignable.
            text = " ".join(str(record.get(key) or "") for key in ("blocker", "evidence"))
            for token in text.replace(",", " ").split():
                token = token.strip("`'\"()[]<>.,;:")
                if token.startswith("RM-") or ":RM-" in token:
                    out.add(token.rpartition(":")[2])
    return out


# ------------------------------------------------------------------ channel: tracker

def read_tracker(root: str, limit: int = 500) -> list[dict]:
    """Open issues from the tracker. Unauthenticated or absent `gh` is `Undetermined`.

    This is the channel most likely to fail quietly, and the failure is indistinguishable from
    a clean tracker in every output format `gh` produces — which is why it raises instead of
    returning [].
    """
    rc, out, err = _run(
        ["gh", "issue", "list", "--state", "open", "--limit", str(limit),
         "--json", "number,title,labels,updatedAt"],
        cwd=root,
    )
    if rc != 0:
        raise Undetermined(f"tracker could not be read (gh exited {rc}): {err.strip() or out.strip()}")
    try:
        rows = json.loads(out or "[]")
    except json.JSONDecodeError as exc:
        raise Undetermined(f"tracker returned unreadable JSON: {exc}") from exc
    if not isinstance(rows, list):
        raise Undetermined("tracker returned something other than a list")
    if len(rows) >= limit:
        # At exactly the cap, "there are this many" and "there are at least this many" are the
        # same output. A truncated tracker read silently understates the frontier, which is the
        # one thing this channel exists not to do.
        raise Undetermined(
            f"tracker returned {len(rows)} rows at the --issue-limit of {limit} — a truncated "
            "read is indistinguishable from a complete one; raise --issue-limit and re-run"
        )
    return rows


# ------------------------------------------------------------------ channel: campaigns

def read_campaign_items(root: str) -> set[str]:
    """Every qualified item id any committed campaign manifest claims.

    A missing campaigns directory is an empty claim set, not a failure: a repository with no
    campaigns has none, and that is a fact rather than an unread channel. A manifest that
    exists and cannot be parsed IS a failure — something is there and it could not be read.
    """
    out: set[str] = set()
    base = os.path.join(root, CAMPAIGNS_REL)
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(base, name)
        try:
            with open(path, encoding="utf-8") as handle:
                doc = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise Undetermined(f"campaign manifest could not be read: {path}: {exc}") from exc
        for wave in doc.get("waves") or []:
            for row in wave.get("workers") or []:
                item = row.get("item")
                if item:
                    out.add(item)
    return out


# ------------------------------------------------------------------ ordering

def quickwin(item: dict) -> dict:
    """The quick-win score and, per factor, the field it was read from.

    `gain × confidence × reversibility ÷ cost`. Every factor names its source so the ordering
    is inspectable rather than a black box, and an item missing the fields a factor needs is
    returned with `score: None` and `provenance: "underdeclared"` — never with an invented
    default. Absent is not zero.
    """
    factors: dict[str, dict] = {}

    priority = item.get("priority") or {}
    score = priority.get("score") if isinstance(priority, dict) else None
    if isinstance(score, (int, float)):
        factors["gain"] = {"value": round(float(score) / SCORE_DIVISOR, 4),
                           "from": "priority.score", "raw": score}
        provenance = "scored"
    elif item.get("tier") in TIER_GAIN:
        factors["gain"] = {"value": TIER_GAIN[item["tier"]], "from": "tier", "raw": item["tier"]}
        provenance = "tier"
    else:
        return {"score": None, "provenance": "underdeclared", "factors": factors,
                "why": "neither `priority.score` nor a recognised `tier`"}

    # CONFIDENCE IS A GATE HERE, NOT A DISCOUNT — a deliberate departure from the formula as it
    # was first written, forced by running it on the real corpus. As a multiplier (1.0 with
    # acceptance, 0.4 without) it ranked an item with NOTHING declared above a fully-declared
    # one: no acceptance meant `cost` collapsed to its floor of 1, and the 0.4 did not cover the
    # gap. `3.0 x 0.4 / 1` beat `3.0 x 1.0 / 3`, so the ordering put undeclared work first — the
    # opposite of a quick win, and exactly the failure a discount always hides. An item with no
    # checkable definition of done does not have a cheap estimate; it has NO estimate, and the
    # honest output is `underdeclared`, sorted last, rather than a number with a haircut.
    acceptance = item.get("acceptance") or []
    if not acceptance:
        return {"score": None, "provenance": "underdeclared", "factors": factors,
                "why": "no acceptance criteria — nothing decides when it is done, so its cost "
                       "cannot be estimated and it is not orderable as a quick win"}
    factors["confidence"] = {"value": 1.0, "from": "acceptance", "raw": len(acceptance),
                             "role": "gate — an item without this is unscored, never discounted"}

    kind = item.get("kind")
    if kind not in KIND_REVERSIBILITY:
        return {"score": None, "provenance": "underdeclared", "factors": factors,
                "why": f"kind {kind!r} is not one this engine ranks"}
    factors["reversibility"] = {"value": KIND_REVERSIBILITY[kind], "from": "kind", "raw": kind}

    deps = item.get("deps") or []
    cost = 1 + len(acceptance) + len(deps)
    factors["cost"] = {"value": float(cost), "from": "acceptance+deps",
                       "raw": {"acceptance": len(acceptance), "deps": len(deps)}}

    value = (
        factors["gain"]["value"]
        * factors["confidence"]["value"]
        * factors["reversibility"]["value"]
        / factors["cost"]["value"]
    )
    return {"score": round(value, 4), "provenance": provenance, "factors": factors}


# ------------------------------------------------------------------ surfaces

def surface_of(item: dict) -> list[str] | None:
    """The paths an item declares it will touch, or None when it declares none.

    None is NOT []. An undeclared surface is unknown, and reading it as empty is what makes
    two workers collide on one file while a checker reports no collision.
    """
    files = ((item.get("links") or {}).get("files")) or []
    files = [f for f in files if isinstance(f, str) and f.strip()]
    return files or None


def _normalise(pattern: str) -> str:
    """A glob reduced to the directory prefix it certainly covers.

    `lstrip("./")` was here and is a CHARACTER-CLASS strip, not a prefix strip: it removes every
    leading `.` and `/` it finds, so `.claude/docs/x.md` normalised to `claude/docs/x.md`. The
    `fnmatch` arm below then compared a de-dotted literal against a still-dotted pattern and
    answered `False` — which made the collision check return "disjoint" for **every**
    `.claude/**`-rooted mid-pattern glob pair in this repository, the one namespace the skill
    exists to protect. `src/*/index.ts` worked, so the defect was invisible to any undotted case.
    Trailing globs survived it because they are cut here and caught by the prefix arm instead,
    which is why every glob case in the matrix passed.
    """
    pattern = pattern.strip()
    while pattern.startswith("./"):
        pattern = pattern[2:]
    for cut in ("/**", "/*", "**", "*"):
        if pattern.endswith(cut):
            pattern = pattern[: -len(cut)]
            break
    return pattern.rstrip("/")


def surfaces_intersect(a: list[str], b: list[str]) -> bool:
    """Do two declared surfaces overlap?

    Deliberately generous: a prefix relationship counts, and either side's glob is matched
    against the other's literal. A false "they collide" costs one wave of parallelism; a false
    "they are disjoint" costs a conflicted merge and the serial run it was supposed to replace.
    """
    for pa in a:
        na = _normalise(pa)
        for pb in b:
            nb = _normalise(pb)
            if not na or not nb:
                return True  # a surface that normalises to the repo root touches everything
            if na == nb or na.startswith(nb + "/") or nb.startswith(na + "/"):
                return True
            if fnmatch.fnmatch(nb, pa) or fnmatch.fnmatch(na, pb):
                return True
    return False


# ------------------------------------------------------------------ the frontier

def build_frontier(root: str, want_tracker: bool = True, issue_limit: int = 500) -> dict:
    """Every open item across every channel, ordered quick-win first.

    Channels are read in a fixed order and each one's outcome is recorded, so a caller can see
    WHICH channel it is missing rather than reading a short frontier as a short backlog.
    """
    _check_root(root)
    channels: dict[str, str] = {}

    slug, items = read_roadmap(root)
    channels["roadmap"] = "read"
    by_id = {item.get("id"): item for item in items}
    escalated = escalated_items(root)
    channels["work-loop"] = "read" if os.path.isdir(os.path.join(root, WORKLOOP_REL)) else "absent"

    claimed = read_campaign_items(root)
    channels["campaigns"] = "read"

    rows: list[dict] = []
    linked_issues: set[str] = set()

    for item in items:
        if item.get("status") not in OPEN_STATUSES:
            continue
        item_id = item.get("id") or ""
        qualified = f"{slug}:{item_id}" if slug else item_id
        for issue in ((item.get("links") or {}).get("issues")) or []:
            linked_issues.add(str(issue))

        blocked = blockedness(item, by_id)
        if blocked is None and item_id in escalated:
            blocked = "blocked-external:work-loop escalate record"

        order = quickwin(item)
        rows.append({
            "source": "roadmap",
            "id": qualified,
            "raw_id": item_id,
            "title": item.get("title") or "",
            "kind": item.get("kind"),
            "tier": item.get("tier"),
            "status": item.get("status"),
            "blocked": blocked,
            "claimed_by_campaign": qualified in claimed,
            "surface": surface_of(item),
            "issues": [str(i) for i in (((item.get("links") or {}).get("issues")) or [])],
            "score": order["score"],
            "provenance": order["provenance"],
            "factors": order["factors"],
            "why_unscored": order.get("why"),
        })

    if want_tracker:
        for issue in read_tracker(root, issue_limit):
            number = str(issue.get("number"))
            if number in linked_issues:
                continue  # already on the frontier as its roadmap item; one row per unit of work
            rows.append({
                "source": "tracker",
                "id": f"#{number}",
                "raw_id": number,
                "title": issue.get("title") or "",
                "kind": None,
                "tier": None,
                "status": "open",
                "blocked": None,
                "claimed_by_campaign": False,
                "surface": None,
                "issues": [number],
                "labels": [l.get("name") for l in (issue.get("labels") or [])],
                "score": None,
                "provenance": "untriaged",
                "factors": {},
                "why_unscored": "an open issue with no roadmap item — route it through `triage`",
            })
        channels["tracker"] = "read"
    else:
        channels["tracker"] = "skipped (--no-tracker)"

    # Scored first, descending. Everything unscored sorts last and keeps a stable order, so a
    # reader can tell an unscored item from a badly-scored one at a glance.
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0.0), r["id"]))

    return {
        "root": root,
        "roadmap_slug": slug,
        "channels": channels,
        "counts": {
            "total": len(rows),
            "roadmap": sum(1 for r in rows if r["source"] == "roadmap"),
            "tracker": sum(1 for r in rows if r["source"] == "tracker"),
            # The two senses of blocked are counted apart, never summed into one number. An
            # unmet deps edge is the roadmap's own arithmetic; an escalate record is a hard
            # external blocker with a credential or a rate limit behind it. Collapsing them is
            # how a rate limit gets reported as a dependency and waited on forever.
            "blocked_by_dep": sum(
                1 for r in rows if (r["blocked"] or "").startswith("blocked-by-dep")
            ),
            "blocked_external": sum(
                1 for r in rows if (r["blocked"] or "").startswith("blocked-external")
            ),
            "claimed": sum(1 for r in rows if r["claimed_by_campaign"]),
            "scored": sum(1 for r in rows if r["score"] is not None),
            "unscored": sum(1 for r in rows if r["score"] is None),
            "surface_declared": sum(1 for r in rows if r["surface"]),
            "surface_unknown": sum(1 for r in rows if not r["surface"]),
        },
        "coverage": _coverage(rows),
        "items": rows,
    }


def _coverage(rows: list[dict]) -> dict:
    """Declaration coverage, as numerator over denominator, printed on every run.

    Not a footnote in a plan doc. The two proxies this engine leans on are only as good as the
    fields they read, and both were thin when it was written — 11 of 149 items declared a
    surface, 1 of 149 carried a recorded score. Printing the fraction every run means a reader
    watches it improve (or fail to) without being told what it was, and neither number is ever
    inherited from prose that has gone stale.
    """
    roadmap_rows = [r for r in rows if r["source"] == "roadmap"]
    denom = len(roadmap_rows) or 1
    surf = sum(1 for r in roadmap_rows if r["surface"])
    scored = sum(1 for r in roadmap_rows if r["provenance"] == "scored")
    return {
        "surface_declared": surf,
        "surface_denominator": len(roadmap_rows),
        "surface_percent": round(100.0 * surf / denom, 2),
        "recorded_score": scored,
        "score_denominator": len(roadmap_rows),
        "score_percent": round(100.0 * scored / denom, 2),
    }


#: `--metric` names, and the expression each one reads out of a computed frontier. This exists so
#: a `work-loop` rubric dimension can name a command that really produces a number: the loop engine
#: READS an evidence command and never runs one (ADR-0143), so a command that prints a JSON
#: document instead of a scalar is a dimension nobody can measure.
METRICS = {
    "open": lambda p: p["counts"]["total"],
    "roadmap-open": lambda p: p["counts"]["roadmap"],
    "tracker-open": lambda p: p["counts"]["tracker"],
    "blocked-by-dep": lambda p: p["counts"]["blocked_by_dep"],
    "blocked-external": lambda p: p["counts"]["blocked_external"],
    "surface-coverage": lambda p: p["coverage"]["surface_percent"],
    "score-coverage": lambda p: p["coverage"]["score_percent"],
}


# ------------------------------------------------------------------ the wave

def compute_wave(frontier: dict, width: int = 4) -> dict:
    """The next wave: assignable rows, quick-win first, with colliding surfaces held back.

    Two rules, and the second is the one that does not exist anywhere else in this harness:

      * an item with a DECLARED surface is placed only if that surface intersects nothing
        already placed;
      * at most ONE item with an UNKNOWN surface is placed per wave, because two unknowns
        cannot be shown disjoint. `endless` states this check in prose ("diff the surfaces
        before fanning out") and nothing implemented it.
    """
    placed: list[dict] = []
    deferred: list[dict] = []
    unknown_placed = False

    for row in frontier["items"]:
        if row["source"] != "roadmap":
            deferred.append({**row, "held": "untriaged — route through `triage` before assigning"})
            continue
        if row["blocked"]:
            deferred.append({**row, "held": row["blocked"]})
            continue
        if row["claimed_by_campaign"]:
            deferred.append({**row, "held": "already claimed by a campaign manifest"})
            continue
        if len(placed) >= width:
            deferred.append({**row, "held": "wave is full"})
            continue

        surface = row["surface"]
        if surface is None:
            if unknown_placed:
                deferred.append({
                    **row,
                    "held": "surface-unknown, and this wave already holds one — two undeclared "
                            "surfaces cannot be shown disjoint",
                })
                continue
            unknown_placed = True
        else:
            clash = next(
                (p for p in placed if p["surface"] and surfaces_intersect(surface, p["surface"])),
                None,
            )
            if clash is not None:
                deferred.append({**row, "held": f"surface collides with {clash['id']}"})
                continue
        placed.append(row)

    workers = [
        {
            "worker": _worker_name(row),
            "branch": _branch_name(row),
            "item": row["id"],
            "scope": row["surface"] or [],
            "surface_provenance": "declared" if row["surface"] else "unknown",
        }
        for row in placed
    ]

    return {
        "width": width,
        "workers": workers,
        # The breakdown SUMS to `deferred`. Without `held_wave_full` and `held_claimed` it did
        # not: the width check runs before the surface checks, so on the real corpus 125 of 149
        # deferrals were in no bucket at all and `held_surface_unknown` read 4 against a frontier
        # holding 138 unknown surfaces. A breakdown that does not add up reads as a measurement.
        "counts": {
            "placed": len(placed),
            "deferred": len(deferred),
            "held_blocked": sum(1 for r in deferred if r.get("held", "").startswith("blocked")),
            "held_collision": sum(1 for r in deferred if "collides" in r.get("held", "")),
            "held_surface_unknown": sum(
                1 for r in deferred if r.get("held", "").startswith("surface-unknown")
            ),
            "held_untriaged": sum(1 for r in deferred if r.get("held", "").startswith("untriaged")),
            "held_claimed": sum(1 for r in deferred if r.get("held", "").startswith("already")),
            "held_wave_full": sum(1 for r in deferred if r.get("held", "").startswith("wave is")),
        },
        "deferred": deferred,
    }


def _slugify(text: str, limit: int = 32) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:limit].strip("-") or "item"


def _worker_name(row: dict) -> str:
    return f"g-{row['raw_id'].lower()}"


def _branch_name(row: dict) -> str:
    prefix = KIND_BRANCH_PREFIX.get(row.get("kind") or "", DEFAULT_BRANCH_PREFIX)
    return f"{prefix}/{row['raw_id'].lower()}-{_slugify(row['title'])}"


# ------------------------------------------------------------------ verify

def verify_batch(root: str, manifest: str | None, want_tracker: bool = True) -> dict:
    """May this batch be called finished, and what has appeared since it was pinned?

    Two questions, deliberately separate. `campaign close` answers the first and is CALLED,
    never re-decided — it owns landedness by content, and reimplementing it here would create
    the second copy that drifts. The second question is this engine's own, and it is the one a
    close-out never asks: a batch can be legitimately closeable while the frontier has grown.
    """
    out: dict = {"root": root, "manifest": manifest}

    if manifest:
        rc, stdout, stderr = _run(
            ["python3", "-m", "scripts.campaign", "close",
             "--root", root, "--manifest", manifest],
            cwd=os.path.join(root, CAMPAIGN_SKILL_REL),
            timeout=300,
        )
        out["campaign_close"] = {
            "exit": rc,
            "verdict": {0: "closeable", 1: "blocked", 2: "undetermined"}.get(rc, "error"),
            "output": (stdout + stderr).strip(),
        }
    else:
        out["campaign_close"] = {"exit": None, "verdict": "not-asked",
                                 "output": "no --manifest given; only the frontier was computed"}

    frontier = build_frontier(root, want_tracker=want_tracker)
    out["channels"] = frontier["channels"]
    out["counts"] = frontier["counts"]
    out["frontier_empty"] = frontier["counts"]["total"] == 0
    return out


# ------------------------------------------------------------------ rendering

def _print_frontier(payload: dict, limit: int, explain: bool) -> None:
    counts = payload["counts"]
    print(f"frontier — {counts['total']} open across "
          f"{len([c for c in payload['channels'].values() if c == 'read'])} channel(s)")
    for name, state in payload["channels"].items():
        print(f"  channel {name}: {state}")
    print(f"  roadmap={counts['roadmap']} tracker={counts['tracker']} "
          f"blocked-by-dep={counts['blocked_by_dep']} "
          f"blocked-external={counts['blocked_external']} claimed={counts['claimed']}")
    cov = payload["coverage"]
    print(f"  declaration coverage — surface {cov['surface_declared']}/"
          f"{cov['surface_denominator']} ({cov['surface_percent']}%), "
          f"recorded score {cov['recorded_score']}/{cov['score_denominator']} "
          f"({cov['score_percent']}%)")
    print()
    for row in payload["items"][:limit]:
        score = "     —" if row["score"] is None else f"{row['score']:6.3f}"
        flags = []
        if row["blocked"]:
            flags.append(row["blocked"])
        if row["claimed_by_campaign"]:
            flags.append("claimed")
        if not row["surface"]:
            flags.append("surface-unknown")
        tail = f"   [{'; '.join(flags)}]" if flags else ""
        print(f"{score}  {row['id']:<20} {row['provenance']:<13} {row['title'][:72]}{tail}")
        if explain:
            for factor, detail in row["factors"].items():
                print(f"           {factor:<14} {detail['value']:<8} "
                      f"read from `{detail['from']}` = {detail.get('raw')!r}")
            if row["why_unscored"]:
                print(f"           unscored: {row['why_unscored']}")


def _print_wave(wave: dict) -> None:
    counts = wave["counts"]
    print(f"wave — {counts['placed']} placed, {counts['deferred']} deferred "
          f"(blocked={counts['held_blocked']} collision={counts['held_collision']} "
          f"surface-unknown={counts['held_surface_unknown']} "
          f"untriaged={counts['held_untriaged']} claimed={counts['held_claimed']} "
          f"wave-full={counts['held_wave_full']})")
    print("  the breakdown sums to `deferred`; wave-full rows were never surface-checked, so "
          "collision=0 is not evidence the collision rule fired")
    print()
    print("campaign-shaped worker rows — copy into the manifest's `waves[]`:")
    print(json.dumps({"wave": None, "workers": wave["workers"]}, indent=2))


# ------------------------------------------------------------------ commands

def cmd_frontier(args) -> int:
    try:
        payload = build_frontier(args.root, want_tracker=not args.no_tracker,
                                 issue_limit=args.issue_limit)
    except Undetermined as exc:
        print(f"UNDETERMINED: {exc}", file=sys.stderr)
        return EXIT_UNDETERMINED
    if args.metric:
        if args.metric not in METRICS:
            print(f"usage: unknown --metric {args.metric!r}; one of {', '.join(METRICS)}",
                  file=sys.stderr)
            return EXIT_USAGE
        print(METRICS[args.metric](payload))
        return EXIT_OK if payload["counts"]["total"] == 0 else EXIT_WORK_REMAINS
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_frontier(payload, args.limit, args.explain)
    return EXIT_OK if payload["counts"]["total"] == 0 else EXIT_WORK_REMAINS


def cmd_rearm(args) -> int:
    try:
        frontier = build_frontier(args.root, want_tracker=not args.no_tracker,
                                  issue_limit=args.issue_limit)
    except Undetermined as exc:
        print(f"UNDETERMINED: {exc}", file=sys.stderr)
        return EXIT_UNDETERMINED
    wave = compute_wave(frontier, width=args.width)
    if args.json:
        print(json.dumps({"channels": frontier["channels"],
                          "counts": frontier["counts"], "wave": wave}, indent=2))
    else:
        _print_wave(wave)
    return EXIT_OK if wave["workers"] else EXIT_NOTHING_TO_ASSIGN


def cmd_verify(args) -> int:
    try:
        payload = verify_batch(args.root, args.manifest, want_tracker=not args.no_tracker)
    except Undetermined as exc:
        print(f"UNDETERMINED: {exc}", file=sys.stderr)
        return EXIT_UNDETERMINED
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"campaign close: {payload['campaign_close']['verdict']}")
        if payload["campaign_close"]["output"]:
            print(payload["campaign_close"]["output"])
        print(f"frontier: {payload['counts']['total']} open "
              f"({payload['counts']['roadmap']} roadmap, {payload['counts']['tracker']} tracker)")
    # `campaign`'s own set is 0/1/2/64. Anything OUTSIDE {0,1,2} is this engine failing to ask the
    # question — including the 124 and 127 `_run` manufactures for a timeout and a missing program.
    # Those used to land in 1, which this module's docstring defines as "items unlanded, or new work
    # has appeared": a caller that greps nothing was told a broken invocation was unlanded work.
    close_exit = payload["campaign_close"]["exit"]
    if close_exit == 2:
        return EXIT_UNDETERMINED
    if close_exit not in (0, 1, None):
        print(f"UNDETERMINED: `campaign close` exited {close_exit}, which is outside its own set "
              "(0 closeable, 1 blocked, 2 undetermined) — the question was not answered",
              file=sys.stderr)
        return EXIT_UNDETERMINED
    if close_exit == 1:
        return EXIT_WORK_REMAINS
    return EXIT_OK if payload["frontier_empty"] else EXIT_WORK_REMAINS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gauntlet", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command")

    def common(p):
        p.add_argument("--root", required=True, help="repository root; never defaulted to the cwd")
        p.add_argument("--json", action="store_true")
        p.add_argument("--no-tracker", action="store_true",
                       help="skip the tracker channel; the frontier then says `skipped`, "
                            "never `read`")
        p.add_argument("--issue-limit", type=int, default=500)
        return p

    fr = common(sub.add_parser("frontier", help="open work across every channel, quick-win first"))
    fr.add_argument("--limit", type=int, default=30)
    fr.add_argument("--explain", action="store_true",
                    help="print each ordering factor and the field it was read from")
    fr.add_argument("--metric", choices=sorted(METRICS),
                    help="print ONE number and nothing else, so a work-loop rubric dimension "
                         "can name a command that really produces its value")
    fr.set_defaults(func=cmd_frontier)

    re_ = common(sub.add_parser("rearm", help="the next wave, with colliding surfaces held back"))
    re_.add_argument("--width", type=int, default=4)
    re_.set_defaults(func=cmd_rearm)

    ve = common(sub.add_parser("verify", help="may this batch close, and what appeared since?"))
    ve.add_argument("--manifest", help="a campaign manifest; `campaign close` is called on it")
    ve.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    # Resolve the caller's paths ONCE, here, against the cwd the caller typed them in. Every
    # path below this line travels to a subprocess with a different cwd.
    if getattr(args, "root", None):
        args.root = os.path.abspath(args.root)
    if getattr(args, "manifest", None):
        args.manifest = os.path.abspath(args.manifest)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
