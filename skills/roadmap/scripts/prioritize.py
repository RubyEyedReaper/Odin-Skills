"""Roadmap <-> decision-matrix hand-off: export a decision spec, ingest the result.

The roadmap owns its own file in both directions. `decision-matrix` stays a generic
weighted-decision engine that knows nothing about `roadmap.json`; this module is the
only place the two formats meet.

Export deliberately emits **null scores**. The agent fills them in — the engine
rejects an incomplete spec, which is the point: a prioritisation nobody scored is a
prioritisation nobody made.

Stdlib only.
"""
from __future__ import annotations

import os
import re

from . import graph as graph_mod

_DEC_RE = re.compile(r"^(DEC-\d{4})")

#: RICE, as criteria. Effort is the one dimension where less is better.
RICE_CRITERIA = (
    ("reach", "Reach — how many users or flows this touches", 25, "higher-is-better"),
    ("impact", "Impact — how much it moves the thing we care about", 30, "higher-is-better"),
    ("confidence", "Confidence — how sure we are of reach and impact", 20, "higher-is-better"),
    ("effort", "Effort — build cost including review and rollout", 25, "lower-is-better"),
)


def dec_id_from_path(path):
    """'/…/DEC-0012-pick-a-cache.md' -> 'DEC-0012'. None for anything else."""
    if not path:
        return None
    match = _DEC_RE.match(os.path.basename(str(path)))
    return match.group(1) if match else None


def candidates(doc, ids=None, tier=None, unblocked_only=False):
    """The items a prioritisation run should compete against each other."""
    items = doc.get("items", [])
    if ids:
        wanted = list(ids)
        by_id = {i.get("id"): i for i in items}
        missing = [i for i in wanted if i not in by_id]
        if missing:
            raise ValueError("unknown item(s): %s" % ", ".join(missing))
        return [by_id[i] for i in wanted]

    out = [i for i in items if i.get("status") in graph_mod.PICKABLE]
    if tier:
        out = [i for i in out if i.get("tier") == tier]
    if unblocked_only:
        out = [i for i in out if graph_mod.is_unblocked(doc, i)]
    out.sort(key=graph_mod.sort_key)
    return out


def export_spec(doc, ids=None, tier=None, unblocked_only=False, goal=None):
    """A decision-spec JSON (scores left null) for `decision-matrix` to score."""
    items = candidates(doc, ids=ids, tier=tier, unblocked_only=unblocked_only)
    if len(items) < 2:
        raise ValueError(
            "prioritisation needs at least 2 competing items, found %d — "
            "nothing to decide" % len(items)
        )

    criteria = [
        {"id": cid, "label": label, "weight": weight, "direction": direction}
        for cid, label, weight, direction in RICE_CRITERIA
    ]
    options = [
        {
            "id": item["id"],
            "label": "%s — %s" % (item["id"], item.get("title", "")),
            "description": "; ".join(item.get("acceptance") or []) or None,
        }
        for item in items
    ]
    scores = {
        item["id"]: {cid: {"value": None} for cid, _, _, _ in RICE_CRITERIA}
        for item in items
    }
    return {
        "goal": goal or "Prioritise the competing roadmap items for %s"
        % doc.get("scope", "this project"),
        "reversibility": "two-way",
        "constraints": [],
        "options": options,
        "criteria": criteria,
        "scorers": [{"id": "roadmap", "label": "Roadmap owner", "scores": scores}],
        "methods": ["weighted-sum"],
        "tie_threshold": 5,
    }


def _ranking(result, method=None):
    method_results = result.get("method_results") or {}
    if not method_results:
        raise ValueError("result has no method_results — not a decision-matrix result")
    if method is None:
        method = "RICE" if "RICE" in method_results else sorted(method_results)[0]
    if method not in method_results:
        raise ValueError(
            "method %r not in result (have: %s)" % (method, ", ".join(sorted(method_results)))
        )
    return method, method_results[method].get("ranking") or []


def ingest(doc, result, method=None):
    """Write ranking scores back onto items. Returns the ids that changed.

    An option id that names no roadmap item is an error — a silent skip would let a
    stale spec quietly prioritise nothing.
    """
    method, ranking = _ranking(result, method)
    dec = dec_id_from_path(result.get("dec_record_path"))
    by_id = {i.get("id"): i for i in doc.get("items", [])}

    unknown = [e.get("option") for e in ranking if e.get("option") not in by_id]
    if unknown:
        raise ValueError(
            "result names option(s) with no roadmap item: %s" % ", ".join(unknown)
        )

    changed = []
    for entry in ranking:
        item = by_id[entry["option"]]
        item["priority"] = {"method": method, "score": entry.get("score"), "dec": dec}
        changed.append(item["id"])
    return changed
