"""Roadmap document schema: load, save, validate, mutate, hash.

`roadmap.json` is the canonical store. `ROADMAP.md`, `graph.dot` and `graph.svg` are
generated from it and must never be hand-edited. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date

SCHEMA_VERSION = 1

KINDS = (
    "feature", "page", "function", "integration",
    "infra", "data", "ops", "docs", "research",
)
STATUSES = ("proposed", "ready", "in-progress", "done", "dropped")
TIERS = ("now", "next", "later", "someday")

ID_RE = re.compile(r"^RM-\d{4}$")

ITEM_FIELDS = (
    "id", "title", "kind", "status", "tier", "deps", "parent", "phase",
    "priority", "owner_skill", "acceptance", "links", "created", "updated",
    "completed", "evidence", "notes",
)
LINK_FIELDS = ("prd", "plan", "adr", "issues", "files")


def today_str(today=None):
    return today or date.today().isoformat()


def pattern_escapes_root(pattern):
    """True when a `links.files` pattern would resolve outside the repository.

    Lives here rather than in `reconcile` so `validate()` — which imports nothing from it — can
    refuse the value at the gate. `reconcile.escapes_root` delegates to this.
    """
    text = str(pattern)
    if os.path.isabs(text) or text.startswith("~"):
        return True
    return ".." in text.replace("\\", "/").split("/")


def empty_links():
    return {"prd": None, "plan": None, "adr": None, "issues": [], "files": []}


def default_doc(scope, today=None):
    return {
        "schema": SCHEMA_VERSION,
        "scope": scope,
        "updated": today_str(today),
        "last_reconcile": None,
        "items": [],
    }


def new_item(item_id, title, kind, today=None, **kw):
    stamp = today_str(today)
    item = {
        "id": item_id,
        "title": title,
        "kind": kind,
        "status": "proposed",
        "tier": "next",
        "deps": [],
        "parent": None,
        "phase": None,
        "priority": None,
        "owner_skill": None,
        "acceptance": [],
        "links": empty_links(),
        "created": stamp,
        "updated": stamp,
        "completed": None,
        "evidence": None,
        "notes": "",
    }
    for key, value in kw.items():
        if key not in ITEM_FIELDS:
            raise ValueError("unknown item field: %s" % key)
        item[key] = value
    return item


# --------------------------------------------------------------------------- io

def canonical_json(doc):
    """The exact bytes `save` writes — hashing this keeps the banner honest."""
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def content_hash(doc):
    return hashlib.sha256(canonical_json(doc).encode("utf-8")).hexdigest()


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, doc):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(canonical_json(doc))


def paths_for(json_path):
    """Derive every generated path from the canonical json location.

    Project layout  <root>/docs/roadmap/roadmap.json -> <root>/ROADMAP.md
    Harness layout  <repo>/.claude/docs/roadmap/...  -> beside the json
    """
    json_abs = os.path.abspath(json_path)
    graph_dir = os.path.dirname(json_abs)
    root = os.path.dirname(os.path.dirname(graph_dir))
    # A harness roadmap lives one level deeper, under `.claude/`. Its ROADMAP.md stays beside
    # the json, but `root` must still be the repository — every other consumer resolves
    # repo-relative paths against it (file globs, CHANGELOG.md, git). Leaving root at
    # `<repo>/.claude` made `reconcile` glob `.claude/.claude/**` and report every finished
    # item as missing its files, while the CHANGELOG check looked for a file that never exists.
    if os.path.basename(root) == ".claude":
        md = os.path.join(graph_dir, "ROADMAP.md")
        root = os.path.dirname(root)
    else:
        md = os.path.join(root, "ROADMAP.md")
    return {
        "json": json_abs,
        "graph_dir": graph_dir,
        "root": root,
        "dot": os.path.join(graph_dir, "graph.dot"),
        "svg": os.path.join(graph_dir, "graph.svg"),
        "md": md,
    }


#: A roadmap's identity, which is *not* its `scope`. `scope` is the memory class — `operational`
#: for the harness, `task:<slug>` for a project — and two roadmaps may legitimately share one.
#: `slug` answers "which roadmap is this", so `RM-0034` can be written down in a form that resolves.
HARNESS_SLUG = "harness"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
QUALIFIED_RE = re.compile(r"^(?:([a-z0-9][a-z0-9._-]{0,31}):)?(RM-\d{4})$")


def _slugify(text):
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(text)).strip("-").lower()
    return text or "roadmap"


def derive_slug(json_path):
    """The roadmap's identity when the document does not declare one.

    Deliberately blind to the checkout: a harness roadmap is always `harness`, whatever directory
    the repository happens to be cloned or worktree'd into. Keying this on the enclosing directory
    name would give one roadmap two identities — `Odin` in the main checkout and something like
    `harness+some-branch` inside `.claude/worktrees/` — which is the bug this field exists to fix,
    reintroduced one level up.

    A project roadmap takes the basename of its own root, which sits *below* any worktree name and
    is therefore stable.
    """
    paths = paths_for(json_path)
    graph_dir = paths["graph_dir"]
    # `<repo>/.claude/docs/roadmap` — the harness layout paths_for() already recognises.
    if os.path.basename(os.path.dirname(os.path.dirname(graph_dir))) == ".claude":
        return HARNESS_SLUG
    return _slugify(os.path.basename(paths["root"]))


def slug_of(doc, json_path):
    """Declared wins; derived otherwise.

    Absence is valid and must stay valid: a roadmap living in a submodule cannot be edited from the
    repository that reads it, and that is exactly the roadmap whose ids collided.
    """
    declared = (doc or {}).get("slug")
    if isinstance(declared, str) and SLUG_RE.match(declared):
        return declared
    return derive_slug(json_path)


def qualify(slug, item_id):
    """`harness:RM-0035` — the form every surface prints, so the string a reader copies resolves."""
    return "%s:%s" % (slug, item_id)


def split_qualified(text):
    """(slug_or_None, id) for a bare or qualified id; (None, None) when it is neither."""
    match = QUALIFIED_RE.match((text or "").strip())
    if not match:
        return (None, None)
    return (match.group(1), match.group(2))


class ForeignRoadmapError(ValueError):
    """A qualified id naming a roadmap other than the one being operated on."""


def resolve_id(doc, json_path, text):
    """Strip a matching slug prefix; refuse a foreign one rather than acting on the wrong roadmap.

    Accepting `otherproject:RM-0001` here and silently treating it as this roadmap's `RM-0001` is
    the same failure as the bare id, with the evidence of the mistake sitting right in the argument.
    """
    slug, item_id = split_qualified(text)
    if item_id is None:
        return text
    if slug is None:
        return item_id
    mine = slug_of(doc, json_path)
    if slug != mine:
        raise ForeignRoadmapError(
            "%s is a `%s` item; this roadmap is `%s` (%s). Nothing was changed."
            % (item_id, slug, mine, json_path)
        )
    return item_id


def locate(start=None):
    """Walk up from `start` looking for a roadmap, project layout first."""
    current = os.path.abspath(start or os.getcwd())
    while True:
        for candidate in (
            os.path.join(current, "docs", "roadmap", "roadmap.json"),
            os.path.join(current, ".claude", "docs", "roadmap", "roadmap.json"),
        ):
            if os.path.exists(candidate):
                return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


# --------------------------------------------------------------------- mutation

def find(doc, item_id):
    for item in doc.get("items", []):
        if item.get("id") == item_id:
            return item
    return None


def alloc_id(doc):
    highest = 0
    for item in doc.get("items", []):
        item_id = item.get("id", "")
        if ID_RE.match(item_id):
            highest = max(highest, int(item_id[3:]))
    return "RM-%04d" % (highest + 1)


def add_item(doc, title, kind, today=None, **kw):
    item = new_item(alloc_id(doc), title, kind, today=today, **kw)
    doc.setdefault("items", []).append(item)
    doc["updated"] = today_str(today)
    return item


def set_item(doc, item_id, today=None, **kw):
    item = find(doc, item_id)
    if item is None:
        raise KeyError("no such roadmap item: %s" % item_id)
    for key in kw:
        if key not in ITEM_FIELDS:
            raise ValueError("unknown item field: %s" % key)
    stamp = today_str(today)
    item.update(kw)
    item["updated"] = stamp
    if item.get("status") == "done" and not item.get("completed"):
        item["completed"] = stamp
    if item.get("status") != "done":
        item["completed"] = None
    doc["updated"] = stamp
    return item


# ------------------------------------------------------------------- validation

def validate(doc):
    """Structural + referential errors. Graph cycles live in graph.graph_errors."""
    errors = []
    if doc.get("schema") != SCHEMA_VERSION:
        errors.append(
            "schema version %r is not supported (expected %d)"
            % (doc.get("schema"), SCHEMA_VERSION)
        )
    declared_slug = doc.get("slug")
    if declared_slug is not None and (
        not isinstance(declared_slug, str) or not SLUG_RE.match(declared_slug)
    ):
        errors.append(
            "slug %r is malformed — lowercase letters, digits, dot, dash or underscore, "
            "32 characters or fewer" % (declared_slug,)
        )

    items = doc.get("items")
    if not isinstance(items, list):
        errors.append("items must be a list")
        return errors

    roots = doc.get("surface_roots")
    if roots is not None:
        # Doc data that becomes a directory to walk. `["/"]` would sweep the filesystem from a code
        # path automation can reach, so the same boundary rule as links.files applies.
        if not isinstance(roots, list):
            errors.append("surface_roots must be a list")
        else:
            for root in roots:
                if not isinstance(root, str) or not root.strip():
                    errors.append("surface_roots entries must be non-empty strings")
                elif pattern_escapes_root(root):
                    errors.append(
                        "surface_roots entry %r resolves outside the repository — "
                        "roots are repo-relative" % root
                    )

    seen = set()
    ids = set()
    for item in items:
        item_id = item.get("id", "")
        if not ID_RE.match(item_id or ""):
            errors.append("invalid id %r — expected RM-NNNN" % item_id)
            continue
        if item_id in seen:
            errors.append("duplicate id %s" % item_id)
        seen.add(item_id)
        ids.add(item_id)

    for item in items:
        item_id = item.get("id", "?")
        if not ID_RE.match(item_id or ""):
            continue
        if not item.get("title"):
            errors.append("%s: title is required" % item_id)
        if item.get("kind") not in KINDS:
            errors.append(
                "%s: unknown kind %r (expected one of %s)"
                % (item_id, item.get("kind"), ", ".join(KINDS))
            )
        status = item.get("status")
        if status == "blocked":
            errors.append(
                "%s: status 'blocked' is never stored — blocked is computed "
                "from unmet deps; use 'proposed' or 'ready'" % item_id
            )
        elif status not in STATUSES:
            errors.append(
                "%s: unknown status %r (expected one of %s)"
                % (item_id, status, ", ".join(STATUSES))
            )
        if item.get("tier") not in TIERS:
            errors.append(
                "%s: unknown tier %r (expected one of %s)"
                % (item_id, item.get("tier"), ", ".join(TIERS))
            )

        deps = item.get("deps") or []
        if not isinstance(deps, list):
            errors.append("%s: deps must be a list" % item_id)
            deps = []
        for dep in deps:
            if dep == item_id:
                errors.append("%s: depends on itself" % item_id)
            elif dep not in ids:
                errors.append("%s: unknown dep %s" % (item_id, dep))

        parent = item.get("parent")
        if parent is not None:
            if parent == item_id:
                errors.append("%s: parent cannot be itself" % item_id)
            elif parent not in ids:
                errors.append("%s: unknown parent %s" % (item_id, parent))

        links = item.get("links")
        if not isinstance(links, dict):
            errors.append("%s: links must be an object" % item_id)
        else:
            for key in links:
                if key not in LINK_FIELDS:
                    errors.append("%s: unknown link field %r" % (item_id, key))
            # `links.files` patterns are joined onto the repo root and handed to `glob` by
            # reconcile. An absolute or traversing pattern reaches the filesystem outside the
            # repository, so it is refused here — at the CI gate — rather than at sweep time.
            for pattern in links.get("files") or []:
                if not isinstance(pattern, str) or not pattern.strip():
                    errors.append("%s: links.files entries must be non-empty strings" % item_id)
                elif pattern_escapes_root(pattern):
                    errors.append(
                        "%s: links.files pattern %r resolves outside the repository — "
                        "patterns are repo-relative" % (item_id, pattern)
                    )

    by_id = {i.get("id"): i for i in items}
    for item in items:
        if item.get("status") != "done":
            continue
        for dep in item.get("deps") or []:
            dep_item = by_id.get(dep)
            if dep_item is not None and dep_item.get("status") not in ("done", "dropped"):
                errors.append(
                    "%s is done but its dep %s is %s"
                    % (item.get("id"), dep, dep_item.get("status"))
                )
    return errors
