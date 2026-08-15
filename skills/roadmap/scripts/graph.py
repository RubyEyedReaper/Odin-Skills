"""Dependency graph maths: cycles, topological order, and the unblocked set.

Every "what is next" answer comes from here, never from a model's judgement.
Stdlib only.
"""
from __future__ import annotations

import heapq

TIER_RANK = {"now": 0, "next": 1, "later": 2, "someday": 3}

#: statuses that satisfy a dependency
SATISFIED = ("done", "dropped")
#: statuses eligible to be picked up next
PICKABLE = ("proposed", "ready")

_WHITE, _GREY, _BLACK = 0, 1, 2


def _edges(doc, field="deps"):
    """node -> sorted list of prerequisite nodes (known ids only)."""
    items = doc.get("items", [])
    ids = {i.get("id") for i in items}
    edges = {}
    for item in items:
        if field == "deps":
            targets = [d for d in (item.get("deps") or []) if d in ids]
        else:
            parent = item.get("parent")
            targets = [parent] if parent in ids and parent is not None else []
        edges[item.get("id")] = sorted(set(targets))
    return edges


def find_cycle(doc, field="deps"):
    """Three-colour DFS. Returns a closed path [a, b, c, a] or None."""
    edges = _edges(doc, field)
    color = dict.fromkeys(edges, _WHITE)
    stack = []

    def visit(node):
        color[node] = _GREY
        stack.append(node)
        for nxt in edges.get(node, []):
            state = color.get(nxt, _BLACK)
            if state == _GREY:
                return stack[stack.index(nxt):] + [nxt]
            if state == _WHITE:
                found = visit(nxt)
                if found:
                    return found
        color[node] = _BLACK
        stack.pop()
        return None

    for node in sorted(edges):
        if color[node] == _WHITE:
            found = visit(node)
            if found:
                return found
    return None


def graph_errors(doc):
    errors = []
    cycle = find_cycle(doc, "deps")
    if cycle:
        errors.append("dependency cycle: " + " -> ".join(cycle))
    parent_cycle = find_cycle(doc, "parent")
    if parent_cycle:
        errors.append("parent cycle: " + " -> ".join(parent_cycle))
    return errors


def topo(doc):
    """Deterministic topological order (Kahn, smallest id first)."""
    cycle = find_cycle(doc, "deps")
    if cycle:
        raise ValueError("cannot order a cyclic graph: " + " -> ".join(cycle))
    edges = _edges(doc, "deps")
    indegree = {node: len(deps) for node, deps in edges.items()}
    dependents = {}
    for node, deps in edges.items():
        for dep in deps:
            dependents.setdefault(dep, []).append(node)

    ready = [n for n, d in indegree.items() if d == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for child in sorted(dependents.get(node, [])):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    return order


def blockers(doc, item):
    """Dep ids that are not yet satisfied. Unknown deps count as blocking."""
    by_id = {i.get("id"): i for i in doc.get("items", [])}
    out = []
    for dep in item.get("deps") or []:
        dep_item = by_id.get(dep)
        if dep_item is None or dep_item.get("status") not in SATISFIED:
            out.append(dep)
    return sorted(set(out))


def is_unblocked(doc, item):
    return not blockers(doc, item)


def score_of(item):
    priority = item.get("priority") or {}
    score = priority.get("score")
    return score if isinstance(score, (int, float)) else None


def sort_key(item):
    score = score_of(item)
    return (
        TIER_RANK.get(item.get("tier"), len(TIER_RANK)),
        -score if score is not None else float("inf"),
        item.get("id", ""),
    )


def next_items(doc, limit=None):
    """Pickable, unblocked items ordered tier -> score -> id."""
    candidates = [
        item for item in doc.get("items", [])
        if item.get("status") in PICKABLE and is_unblocked(doc, item)
    ]
    candidates.sort(key=sort_key)
    return candidates[:limit] if limit else candidates


def blocked_items(doc):
    """Pickable items that are waiting on something, ordered by id."""
    out = [
        item for item in doc.get("items", [])
        if item.get("status") in PICKABLE and not is_unblocked(doc, item)
    ]
    out.sort(key=lambda i: i.get("id", ""))
    return out


def waves(doc, limit=None, with_deferred=False):
    """Parallel execution layers over the pickable set.

    Wave 0 is exactly `next_items(doc)` — what can start right now. Wave k holds
    items whose every unmet dep sits in an earlier wave, so a wave is a batch that
    can be executed in parallel once the previous one lands.

    Waves are **computed, never stored** (DEC-0001): a stored `wave` field would be
    a second source of truth that goes stale the moment a dep changes.

    An item whose unmet deps include something outside the pickable set — work
    already `in-progress`, or an unknown id — cannot be placed, because nothing in
    the graph says which wave that dep will land in. Those items are *deferred*:
    excluded from the layers and reported by `blocked_items` (or by this function
    when `with_deferred=True`).

    Returns a list of layers, or `(layers, deferred)` when `with_deferred` is set.
    Raises ValueError on a cyclic graph, as `topo` does.
    """
    cycle = find_cycle(doc, "deps")
    if cycle:
        raise ValueError("cannot layer a cyclic graph: " + " -> ".join(cycle))

    pickable = {
        item.get("id"): item
        for item in doc.get("items", [])
        if item.get("status") in PICKABLE
    }
    unmet = {node: blockers(doc, item) for node, item in pickable.items()}

    depth = {}
    deferred = []
    remaining = dict(pickable)
    while remaining:
        placed = False
        for node in sorted(remaining):
            deps = unmet[node]
            if any(dep not in pickable for dep in deps):
                continue  # waits on work outside the schedulable set
            if all(dep in depth for dep in deps):
                depth[node] = 1 + max((depth[d] for d in deps), default=-1)
                del remaining[node]
                placed = True
        if not placed:
            deferred = [remaining[node] for node in sorted(remaining)]
            break

    layers = []
    for node, level in depth.items():
        while len(layers) <= level:
            layers.append([])
        layers[level].append(pickable[node])
    for layer in layers:
        layer.sort(key=sort_key)
    if limit is not None:
        layers = layers[:limit]
    return (layers, deferred) if with_deferred else layers


def newly_unblocked(doc, completed_id):
    """Items that became pickable because `completed_id` finished."""
    out = []
    for item in doc.get("items", []):
        if item.get("status") not in PICKABLE:
            continue
        if completed_id in (item.get("deps") or []) and is_unblocked(doc, item):
            out.append(item)
    out.sort(key=sort_key)
    return out
