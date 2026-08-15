"""roadmap CLI — `python3 -m scripts.roadmap <command>`.

Commands
    init        create an empty roadmap for a scope
    validate    schema + graph + render-freshness checks (exit 1 on any error)
    next        the unblocked set, ordered — the only sanctioned "what next" answer
    waves       parallel execution layers computed from deps (wave 0 == next)
    prioritize  export a decision spec for decision-matrix / ingest its result
    add         append an item
    set         mutate an item
    render      regenerate ROADMAP.md, graph.dot and graph.svg
    reconcile   report drift between the roadmap and reality
    due         is a reconcile overdue? — the gate hook's only source for that
    bootstrap   seed items from init/plan docs plus the standard surface sweep

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from . import graph as graph_mod
from . import prioritize as prioritize_mod
from . import render as render_mod
from . import reconcile as reconcile_mod
from . import schema as schema_mod

# Starter surfaces: what a project of a given kind eventually needs, whether or not its own docs
# mention it. A bootstrap that only reads the project's plan will miss all of them — that is exactly
# how a roadmap ends up claiming to be "full" while omitting login and a privacy policy.
#
# Named "starter surfaces", not "sweep": `scripts/sweep.py` is the git-driven finder of directories
# no item claims, and one word for two mechanisms made "the sweep produced nothing" ambiguous in a
# bug report (audit F7). The CLI flag keeps its spelling — it now takes a profile, which reads as a
# starter list rather than a scan.
#
# Profiles exist because the web list is wrong for a library or plugin repository, and there was no
# alternative and no way to decline (audit F5). Adding a profile is adding a key here.
WEB_SURFACES = [
    ("Auth & identity", [
        ("Login page", "page"),
        ("Signup page", "page"),
        ("Password reset flow", "feature"),
        ("Email verification", "feature"),
        ("Social / OAuth sign-in", "integration"),
        ("Session and token handling", "infra"),
        ("Logout", "function"),
    ]),
    ("Account", [
        ("User profile page", "page"),
        ("Account settings page", "page"),
        ("Avatar / image upload", "feature"),
        ("Account deletion and data export", "feature"),
        ("Saved items / favourites", "feature"),
    ]),
    ("Content & marketing", [
        ("Marketing home page", "page"),
        ("Blog index page", "page"),
        ("Blog post page", "page"),
        ("News / changelog page", "page"),
        ("About page", "page"),
        ("Pricing page", "page"),
    ]),
    ("Support", [
        ("FAQ page", "page"),
        ("Help centre / documentation", "docs"),
        ("Contact form", "feature"),
        ("Feedback capture", "feature"),
    ]),
    ("Legal & compliance", [
        ("Terms of service", "docs"),
        ("Privacy policy", "docs"),
        ("Cookie consent", "feature"),
    ]),
    ("Discovery", [
        ("Global search", "feature"),
        ("Sitemap and robots.txt", "infra"),
        ("SEO metadata and share cards", "feature"),
        ("404 and 500 error pages", "page"),
    ]),
    ("Communications", [
        ("Transactional email delivery", "integration"),
        ("Notification preferences", "feature"),
    ]),
    ("Operations", [
        ("Analytics instrumentation", "integration"),
        ("Error monitoring", "integration"),
        ("Rate limiting and abuse controls", "infra"),
        ("Admin dashboard", "page"),
        ("Audit log", "infra"),
    ]),
]

# What a library, plugin or skills repository needs and its own plan rarely lists. Deliberately
# short: a starter list that is wrong is worse than one that is thin, because every item costs a
# reviewer a decision.
LIBRARY_SURFACES = [
    ("Documentation", [
        ("README with install and first example", "docs"),
        ("API reference", "docs"),
        ("Usage examples", "docs"),
        ("Migration / upgrade notes", "docs"),
    ]),
    ("Release", [
        ("CHANGELOG kept per release", "docs"),
        ("Versioning policy", "docs"),
        ("Release process and publishing", "infra"),
        ("Deprecation policy", "docs"),
    ]),
    ("Contribution", [
        ("CONTRIBUTING guide", "docs"),
        ("Issue and PR templates", "infra"),
        ("License and attribution", "docs"),
    ]),
    ("Quality", [
        ("CI on every pull request", "infra"),
        ("Supported-version matrix in CI", "infra"),
        ("Test coverage floor", "infra"),
    ]),
]

#: profile name -> starter surfaces. `web` is the default so every existing bare `--surface-sweep`
#: keeps its meaning.
STARTER_SURFACES = {
    "web": WEB_SURFACES,
    "library": LIBRARY_SURFACES,
}
DEFAULT_STARTER_PROFILE = "web"

_BULLET_RE = re.compile(r"^\s*[-*+]\s+(?:\[[ xX]\]\s*)?(.+?)\s*$")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*?)\s*$")

# Sections that describe *how the project is run* rather than what it must build.
# Mining these produces items like "claude-mem namespace: task:foo", which is noise a
# reviewer then has to delete by hand. Override with --sections-exclude.
DEFAULT_SECTION_EXCLUDE = (
    r"memory|source of truth|stack decision|architecture|definition of|"
    r"current status|glossary|convention|licen[cs]e|contributing"
)


# ----------------------------------------------------------------- path helpers

def _resolve(args, required=True):
    if getattr(args, "path", None):
        return os.path.abspath(args.path)
    found = schema_mod.locate(getattr(args, "root", None) or os.getcwd())
    if found is None and required:
        _die(
            "no roadmap found. Create one with:\n"
            "  python3 -m scripts.roadmap init --root <project> --scope <scope>"
        )
    return found


def _die(message, code=1):
    sys.stderr.write("[roadmap] %s\n" % message)
    raise SystemExit(code)


def _load(args):
    path = _resolve(args)
    return path, schema_mod.load(path)


def refresh(path, args=None):
    """Regenerate ROADMAP.md + graph when they no longer match roadmap.json.

    Read commands call this so a project always looks at fresh content: the
    markdown and graph are generated artifacts, never sources of truth, so the
    only honest response to a stale one is to rewrite it. `validate` deliberately
    does *not* self-heal — it is the gate that reports the drift.

    Suppress with `--no-render` (read-only checkouts, CI).
    """
    if args is not None and getattr(args, "no_render", False):
        return False
    try:
        if not render_mod.md_is_stale(path):
            return False
        render_mod.render_all(path)
    except (OSError, ValueError) as exc:  # read-only fs, bad doc — never block the read
        sys.stderr.write("[roadmap] could not refresh generated files: %s\n" % exc)
        return False
    sys.stderr.write("[roadmap] generated files were stale — re-rendered %s\n" % path)
    return True


def _csv(value):
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


# --------------------------------------------------------------------- commands

def cmd_init(args):
    root = os.path.abspath(args.root or os.getcwd())
    path = args.path or os.path.join(root, "docs", "roadmap", "roadmap.json")
    if os.path.exists(path) and not args.force:
        _die("%s already exists (use --force to overwrite)" % path)
    doc = schema_mod.default_doc(args.scope, today=args.today)
    schema_mod.save(path, doc)
    render_mod.render_all(path)
    print("initialised %s" % path)
    return 0


def cmd_validate(args):
    path, doc = _load(args)
    errors = schema_mod.validate(doc) + graph_mod.graph_errors(doc)
    if not errors and render_mod.md_is_stale(path):
        errors.append(
            "ROADMAP.md is stale or hand-edited — regenerate with `roadmap render`"
        )
    if errors:
        for error in errors:
            sys.stderr.write("[roadmap] %s\n" % error)
        sys.stderr.write("[roadmap] %d problem(s) in %s\n" % (len(errors), path))
        return 1
    print("ok — %s (%s, %d items)"
          % (path, schema_mod.slug_of(doc, path), len(doc.get("items", []))))
    return 0


def _display_path(path):
    """Repo-relative when it can be, so the header is readable and still unambiguous."""
    try:
        root = schema_mod.paths_for(path)["root"]
        return os.path.relpath(os.path.abspath(path), root)
    except (OSError, ValueError):
        return path


def _format_text(doc, items, path):
    slug = schema_mod.slug_of(doc, path)
    if not items:
        # An empty roadmap and a fully-committed one are different states with different next
        # actions, and the second message is false in the first case (audit F6). It is also the
        # message a failed bootstrap produced, so the reader was told a broken inventory was a
        # healthy one — the honest version names the way out instead.
        if not doc.get("items"):
            return (
                "roadmap for %s (%s) is empty — nothing has been captured yet.\n"
                "Seed it: python3 -m scripts.roadmap --root <project> bootstrap "
                "--from INIT.md --surface-sweep"
                % (slug, _display_path(path))
            )
        return (
            "no unblocked roadmap items for %s (%s).\n"
            "Everything is either done, in-progress, or waiting on a dependency."
            % (slug, _display_path(path))
        )
    # Ids are per-roadmap counters, so the header names which roadmap and every row carries the
    # qualified form. A reader copying a row into a handoff then copies something that resolves.
    lines = ["next unblocked — %s  (%s)" % (slug, _display_path(path))]
    for item in items:
        score = graph_mod.score_of(item)
        badge = "" if score is None else "  [%s %.2f]" % (
            (item.get("priority") or {}).get("method", "score"), score,
        )
        lines.append("  %-22s %-12s %s%s" % (
            schema_mod.qualify(slug, item.get("id")), item.get("kind"),
            item.get("title"), badge,
        ))
    lines.append("Run superplan on the chosen item before editing any source.")
    return "\n".join(lines)


def cmd_next(args):
    path, doc = _load(args)
    refresh(path, args)
    items = graph_mod.next_items(doc, limit=args.limit)
    if args.format == "json":
        print(json.dumps({
            # `roadmap` is the identity; `scope` remains the memory class. Both are emitted
            # because they answer different questions and were previously conflated.
            "roadmap": schema_mod.slug_of(doc, path),
            "scope": doc.get("scope"),
            "path": path,
            "items": items,
        }, indent=2))
    else:
        print(_format_text(doc, items, path))
    return 0


def cmd_waves(args):
    """Parallel execution layers — wave 0 is what can start right now."""
    path, doc = _load(args)
    refresh(path, args)
    layers, deferred = graph_mod.waves(doc, limit=args.limit, with_deferred=True)
    slug = schema_mod.slug_of(doc, path)
    if args.format == "json":
        print(json.dumps({
            "roadmap": slug,
            "scope": doc.get("scope"),
            "path": path,
            "waves": layers,
            "deferred": deferred,
        }, indent=2))
        return 0
    if layers:
        print("waves — %s  (%s)\n" % (slug, _display_path(path)))

    if not layers:
        print("no schedulable waves — nothing pickable, or everything waits on "
              "work already in progress.")
    for index, layer in enumerate(layers):
        parallel = "" if len(layer) == 1 else "   (%d in parallel)" % len(layer)
        print("wave %d%s" % (index, parallel))
        for item in layer:
            print("  %-22s %-12s %s" % (schema_mod.qualify(slug, item.get("id")),
                                        item.get("kind"), item.get("title")))
    if deferred:
        print("\nwaiting on in-flight work (not schedulable yet):")
        for item in deferred:
            print("  %-22s %s  <- %s"
                  % (schema_mod.qualify(slug, item.get("id")), item.get("title"),
                     ", ".join(graph_mod.blockers(doc, item))))
    if layers:
        print("\nExecute one wave at a time. Plan every item in a wave before "
              "starting any of it.")
    return 0


def cmd_prioritize(args):
    """Export a decision spec for `decision-matrix`, or ingest its result."""
    path, doc = _load(args)
    refresh(path, args)
    if args.source:
        with open(args.source, encoding="utf-8") as fh:
            result = json.load(fh)
        changed = prioritize_mod.ingest(doc, result, method=args.method)
        errors = schema_mod.validate(doc) + graph_mod.graph_errors(doc)
        if errors:
            for error in errors:
                sys.stderr.write("[roadmap] %s\n" % error)
            return 1
        schema_mod.save(path, doc)
        render_mod.render_all(path)
        print("prioritised %d item(s) from %s" % (len(changed), args.source))
        for item_id in changed:
            priority = schema_mod.find(doc, item_id).get("priority") or {}
            print("  %-8s %s %s%s" % (
                item_id, priority.get("method"), priority.get("score"),
                "  (%s)" % priority["dec"] if priority.get("dec") else "",
            ))
        return 0

    spec = prioritize_mod.export_spec(
        doc, ids=_csv(args.ids) or None, tier=args.tier,
        unblocked_only=args.unblocked, goal=args.goal,
    )
    text = json.dumps(spec, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("wrote %s — fill in every null score, then run decision-matrix:" % args.out)
        print("  python3 -m scripts.score --spec %s --record" % args.out)
        print("  python3 -m scripts.roadmap prioritize --from <result.json>")
    else:
        print(text)
    return 0


def _resolve_ref(doc, path, text):
    """A dep or parent may be written qualified; a foreign one is refused.

    A cross-roadmap dependency is not representable in the graph — `next` and `waves` resolve deps
    against this document's items — so accepting `otherproject:RM-0001` would silently create an
    edge to this roadmap's unrelated RM-0001. Refusing is the honest answer.
    """
    if doc is None or path is None:
        return text
    try:
        return schema_mod.resolve_id(doc, path, text)
    except schema_mod.ForeignRoadmapError as exc:
        _die(str(exc))


def _apply_common(values, args, doc=None, path=None):
    mapping = {
        "title": args.title,
        "kind": args.kind,
        "status": args.status,
        "tier": args.tier,
        "phase": args.phase,
        "owner_skill": args.owner_skill,
        "notes": args.notes,
        "evidence": args.evidence,
    }
    for key, value in mapping.items():
        if value is not None:
            values[key] = value
    if args.parent is not None:
        values["parent"] = _resolve_ref(doc, path, args.parent) if args.parent else None
    if args.deps is not None:
        values["deps"] = [_resolve_ref(doc, path, dep) for dep in _csv(args.deps)]
    if args.acceptance is not None:
        values["acceptance"] = [a for a in args.acceptance if a]
    if args.score is not None:
        values["priority"] = {"method": args.method or "RICE", "score": args.score}
    return values


def _apply_links(item, args):
    links = dict(item.get("links") or schema_mod.empty_links())
    for key in ("prd", "plan", "adr"):
        value = getattr(args, key)
        if value is not None:
            links[key] = value or None
    if args.issues is not None:
        links["issues"] = _csv(args.issues)
    if args.files is not None:
        links["files"] = _csv(args.files)
    return links


def cmd_add(args):
    path, doc = _load(args)
    values = _apply_common({}, args, doc, path)
    values.pop("title", None)
    values.pop("kind", None)
    item = schema_mod.add_item(
        doc, title=args.title, kind=args.kind or "feature",
        today=args.today, **values
    )
    item["links"] = _apply_links(item, args)
    errors = schema_mod.validate(doc) + graph_mod.graph_errors(doc)
    if errors:
        for error in errors:
            sys.stderr.write("[roadmap] %s\n" % error)
        return 1
    schema_mod.save(path, doc)
    render_mod.render_all(path)
    print("added %s  %s  %s" % (schema_mod.qualify(schema_mod.slug_of(doc, path), item["id"]),
                                item["kind"], item["title"]))
    return 0


def cmd_set(args):
    path, doc = _load(args)
    # `set harness:RM-0035 …` must work, because that is the string every other command prints.
    # A *foreign* prefix is refused rather than silently applied to this roadmap's item of the
    # same number — acting on the wrong roadmap is the failure this whole change exists to stop,
    # and here the evidence of the mistake is sitting in the argument.
    try:
        args.id = schema_mod.resolve_id(doc, path, args.id)
    except schema_mod.ForeignRoadmapError as exc:
        _die(str(exc))
    item = schema_mod.find(doc, args.id)
    if item is None:
        _die("no such item: %s" % args.id)
    values = _apply_common({}, args, doc, path)
    values["links"] = _apply_links(item, args)
    previous = item.get("status")
    schema_mod.set_item(doc, args.id, today=args.today, **values)
    errors = schema_mod.validate(doc) + graph_mod.graph_errors(doc)
    if errors:
        for error in errors:
            sys.stderr.write("[roadmap] %s\n" % error)
        return 1
    schema_mod.save(path, doc)
    render_mod.render_all(path)
    slug = schema_mod.slug_of(doc, path)
    print("updated %s" % schema_mod.qualify(slug, args.id))
    if previous != "done" and item.get("status") == "done":
        freed = graph_mod.newly_unblocked(doc, args.id)
        if freed:
            print("newly unblocked:")
            for entry in freed:
                print("  %-22s %s" % (schema_mod.qualify(slug, entry["id"]), entry["title"]))
    return 0


def cmd_render(args):
    path, _ = _load(args)
    written = render_mod.render_all(path)
    print("rendered %s" % written["md"])
    print("         %s" % written["dot"])
    if written["svg"]:
        print("         %s" % written["svg"])
    else:
        sys.stderr.write("[roadmap] graphviz `dot` unavailable — SVG not regenerated\n")
    return 0


def cmd_reconcile(args):
    path, doc = _load(args)
    refresh(path, args)
    report = reconcile_mod.reconcile(
        path, doc, today=args.today,
        run_git=not args.no_git, run_gh=not args.no_gh,
        surface_roots=getattr(args, "surface_roots", None),
    )
    if args.format == "json":
        print(json.dumps(report["findings"], indent=2))
    else:
        findings = report["findings"]
        if not findings:
            print("no drift — %s" % path)
        else:
            print("%d finding(s) for %s" % (len(findings), path))
            for finding in findings:
                flag = "auto" if finding["auto"] else "CONFIRM"
                print("  [%s] %s" % (flag, finding["message"]))
                print("        -> %s" % finding["proposal"])
    # `--apply-auto` answers "should items be mutated", not "did the check run". Stamping only
    # under it meant the one outcome that should clear the staleness notice — no drift, nothing to
    # apply — was the one that never recorded, so the gate's "never been reconciled" line could
    # not clear and became a notice readers learn to skip (the failure ADR-0036 tuned out of the
    # compaction nudge).
    #
    # The render must move with it. `ROADMAP.md`'s banner carries a content hash over the whole
    # canonical doc, `last_reconcile` included, and `validate` fails when the two disagree — so a
    # stamp written without re-rendering turns every clean reconcile into a red CI gate.
    #
    # `--no-render` means a read-only checkout, so nothing is written there at all — stamping the
    # canonical file while refusing to update the rendering it is hashed into would manufacture
    # precisely the drift this fix exists to avoid.
    added = []
    if args.apply_auto and not getattr(args, "no_render", False):
        # `reconcile()` is pure by design, so applying is a separate, explicit step. `--no-render`
        # means a read-only checkout: report only, mutate nothing.
        added = reconcile_mod.apply_auto(doc, report["auto"], today=args.today)
        errors = schema_mod.validate(doc) + graph_mod.graph_errors(doc)
        if errors:
            for error in errors:
                sys.stderr.write("[roadmap] %s\n" % error)
            sys.stderr.write("[roadmap] applied nothing — the result would not validate\n")
            return 1
    if not getattr(args, "no_render", False):
        doc["last_reconcile"] = schema_mod.today_str(args.today)
        schema_mod.save(path, doc)
        render_mod.render_all(path)
    if args.apply_auto:
        for item in added:
            print("  applied: added %s (%s) as proposed" % (item["id"], item["title"]))
        skipped = len(report["auto"]) - len(added)
        print("%d item(s) added; %d auto finding(s) needed no item; "
              "%d item(s) need confirmation"
              % (len(added), skipped, len(report["manual"])))
    return 0


def cmd_due(args):
    """Is a reconcile overdue? Reads only — never renders, never mutates.

    This exists so no consumer has to restate the policy. `--format text` prints **nothing** when
    nothing is due, which collapses a caller's logic to an assignment with no comparison in it:
    bash cannot drift from a threshold it never states.

    Exit is always 0. Due-ness is data on stdout, not a failure class — `1` already means "the
    engine failed" everywhere else in this CLI, and the caller is a hook that must not fail a turn.
    """
    path, doc = _load(args)
    status = reconcile_mod.reconcile_status(doc, today=args.today)
    if args.format == "json":
        print(json.dumps(status, sort_keys=True))
        return 0
    if not status["due"]:
        return 0
    if status["last_reconcile"] is None:
        print("This roadmap has never been reconciled — run /roadmap reconcile to check it "
              "against git, the tracker and disk.")
    else:
        print("Last reconciled %d days ago — run /roadmap reconcile before trusting this list."
              % status["days"])
    return 0


def _parse_bullets(text):
    """Yield (section_heading, bullet_text) pairs from a markdown document."""
    section = ""
    for line in text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            section = heading.group(1).strip()
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            body = bullet.group(1).strip()
            if body and not body.startswith("<!--"):
                yield section, body


def _tier_for_section(section):
    lowered = section.lower()
    if "out of scope" in lowered or "deferred" in lowered or "later" in lowered:
        return "someday"
    if "phase 1" in lowered or "current" in lowered or "in scope" in lowered:
        return "now"
    if "phase 2" in lowered:
        return "next"
    if "phase 3" in lowered or "phase 4" in lowered:
        return "later"
    return "next"


def cmd_bootstrap(args):
    root = os.path.abspath(args.root or os.getcwd())
    path = args.path or os.path.join(root, "docs", "roadmap", "roadmap.json")
    if os.path.exists(path):
        doc = schema_mod.load(path)
    else:
        doc = schema_mod.default_doc(args.scope or os.path.basename(root),
                                     today=args.today)

    existing = {(i.get("title") or "").strip().lower() for i in doc.get("items", [])}
    added = []
    exclude = re.compile(args.sections_exclude or DEFAULT_SECTION_EXCLUDE, re.I)
    skipped_sections = set()

    # Sources resolve against the roadmap's own root, not the working directory. Every documented
    # invocation starts by cd-ing into this skill directory, so a bare `--from INIT.md` used to be
    # looked for among the engine's own files and never in the project being bootstrapped — the
    # hook's bootstrap nudge could not read a single source on any project (audit F2). An absolute
    # path is still taken as given.
    requested = list(args.source or [])
    missing = []
    for source in requested:
        resolved = source if os.path.isabs(source) else os.path.join(root, source)
        if not os.path.exists(resolved):
            sys.stderr.write("[roadmap] skipping missing source %s (looked in %s)\n"
                             % (source, os.path.dirname(resolved) or "."))
            missing.append(source)
            continue
        with open(resolved, encoding="utf-8") as fh:
            text = fh.read()
        for section, bullet in _parse_bullets(text):
            if section and exclude.search(section):
                skipped_sections.add(section)
                continue
            title = bullet.split(" — ")[0].split(". ")[0].strip()
            title = re.sub(r"[`*]", "", title)[:120].strip()
            if not title or title.lower() in existing:
                continue
            existing.add(title.lower())
            item = schema_mod.add_item(
                doc, title=title, kind="feature", today=args.today,
                tier=_tier_for_section(section),
                phase=section or None,
                notes="derived from %s" % os.path.basename(source),
            )
            added.append(item)

    profile = args.surface_sweep
    if profile is not None:
        if profile not in STARTER_SURFACES:
            _die("unknown starter-surface profile %r — known profiles: %s"
                 % (profile, ", ".join(sorted(STARTER_SURFACES))))
        for group, entries in STARTER_SURFACES[profile]:
            for title, kind in entries:
                if title.lower() in existing:
                    continue
                existing.add(title.lower())
                item = schema_mod.add_item(
                    doc, title=title, kind=kind, today=args.today,
                    tier="someday", phase=group,
                    notes="%s starter surface — not yet in project docs; confirm or drop"
                          % profile,
                )
                added.append(item)

    # Every named source unreadable is a failed bootstrap, not a 0-item success. It used to exit 0
    # and print "bootstrapped …" on stdout with the skip lines on stderr, so a project ended up
    # looking bootstrapped with an empty inventory — and `validate` then called that empty roadmap
    # ok. A partial read is not fatal: one source of several missing is a sweep the caller can see.
    if requested and len(missing) == len(requested):
        sys.stderr.write(
            "[roadmap] no source was readable (%s) — nothing to bootstrap from; "
            "check the paths, which resolve against %s\n" % (", ".join(missing), root))
        return 1

    errors = schema_mod.validate(doc) + graph_mod.graph_errors(doc)
    if errors:
        for error in errors:
            sys.stderr.write("[roadmap] %s\n" % error)
        return 1

    schema_mod.save(path, doc)
    render_mod.render_all(path)
    # Name the profile in the summary. A wrong profile is then visible at a glance, rather than
    # after thirty-five items for pages the project will never have have landed in the inventory.
    print("bootstrapped %s — %d new item(s), %d total%s"
          % (path, len(added), len(doc.get("items", [])),
             "" if profile is None else " (starter surfaces: %s)" % profile))
    for item in added:
        print("  %-8s %-12s %-9s %s"
              % (item["id"], item["kind"], item["tier"], item["title"]))
    if skipped_sections:
        print("\nSkipped non-scope sections: %s" % ", ".join(sorted(skipped_sections)))
    print("\nReview every item above: adjust kind/tier, set deps, drop what does "
          "not apply. Nothing here is authoritative until you confirm it.")
    return 0


# ------------------------------------------------------------------------ parser

def build_parser():
    parser = argparse.ArgumentParser(
        prog="roadmap", description="Standing inventory + dependency graph.",
    )
    parser.add_argument("--path", help="path to roadmap.json")
    parser.add_argument("--root", help="project root to search from")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    parser.add_argument(
        "--no-render", dest="no_render", action="store_true",
        help="never rewrite generated files (read-only checkouts, CI)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create an empty roadmap")
    init.add_argument("--scope", required=True, help="e.g. task:MyProject")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    validate = subparsers.add_parser("validate", help="check schema, graph, freshness")
    validate.set_defaults(func=cmd_validate)

    nxt = subparsers.add_parser("next", help="unblocked items, ordered")
    nxt.add_argument("--limit", type=int, default=None)
    nxt.add_argument("--format", choices=("text", "json"), default="text")
    nxt.set_defaults(func=cmd_next)

    wav = subparsers.add_parser(
        "waves", help="parallel execution layers computed from deps")
    wav.add_argument("--limit", type=int, default=None, help="max waves to show")
    wav.add_argument("--format", choices=("text", "json"), default="text")
    wav.set_defaults(func=cmd_waves)

    pri = subparsers.add_parser(
        "prioritize", help="export a decision spec / ingest a decision-matrix result")
    pri.add_argument("--from", dest="source", help="decision-matrix result JSON to ingest")
    # Export is what `prioritize` does when it is not ingesting, so this flag selects nothing. It
    # exists because it was documented in nine places before it was ever implemented (audit F1), and
    # a copy of that command survives in every transcript and memory that quoted it. Accepting the
    # flag makes all of them run; editing the nine documents would not have.
    pri.add_argument("--export", action="store_true",
                     help="accepted for compatibility — exporting is already the default")
    pri.add_argument("--method", help="method key to read from the result (default: RICE)")
    pri.add_argument("--ids", help="comma-separated item ids to compete")
    pri.add_argument("--tier", choices=schema_mod.TIERS)
    pri.add_argument("--unblocked", action="store_true",
                     help="only items with no unmet deps")
    pri.add_argument("--goal", help="override the decision goal line")
    pri.add_argument("--out", help="write the spec here instead of stdout")
    pri.set_defaults(func=cmd_prioritize)

    def add_item_flags(sub, require_title):
        sub.add_argument("--title", required=require_title)
        sub.add_argument("--kind", choices=schema_mod.KINDS)
        sub.add_argument("--status", choices=schema_mod.STATUSES)
        sub.add_argument("--tier", choices=schema_mod.TIERS)
        sub.add_argument("--deps", help="comma-separated item ids")
        sub.add_argument("--parent")
        sub.add_argument("--phase")
        sub.add_argument("--owner-skill", dest="owner_skill")
        sub.add_argument("--acceptance", action="append")
        sub.add_argument("--score", type=float)
        sub.add_argument("--method")
        sub.add_argument("--notes")
        sub.add_argument("--evidence")
        sub.add_argument("--prd")
        sub.add_argument("--plan")
        sub.add_argument("--adr")
        sub.add_argument("--issues", help="comma-separated issue refs")
        sub.add_argument("--files", help="comma-separated globs")

    add = subparsers.add_parser("add", help="append an item")
    add_item_flags(add, require_title=True)
    add.set_defaults(func=cmd_add)

    set_cmd = subparsers.add_parser("set", help="mutate an item")
    set_cmd.add_argument("id")
    add_item_flags(set_cmd, require_title=False)
    set_cmd.set_defaults(func=cmd_set)

    render = subparsers.add_parser("render", help="regenerate ROADMAP.md and the graph")
    render.set_defaults(func=cmd_render)

    rec = subparsers.add_parser("reconcile", help="report drift")
    rec.add_argument("--format", choices=("text", "json"), default="text")
    rec.add_argument("--no-git", action="store_true")
    rec.add_argument("--no-gh", action="store_true")
    rec.add_argument("--apply-auto", action="store_true")
    rec.add_argument("--surface-root", dest="surface_roots", action="append",
                     help="directory to sweep for unclaimed surfaces "
                          "(repeatable; overrides `surface_roots` in the doc)")
    rec.set_defaults(func=cmd_reconcile)

    due = subparsers.add_parser("due", help="is a reconcile overdue?")
    due.add_argument("--format", choices=("text", "json"), default="text")
    due.set_defaults(func=cmd_due)

    boot = subparsers.add_parser("bootstrap", help="seed items from docs")
    boot.add_argument("--scope")
    boot.add_argument("--from", dest="source", action="append",
                      help="markdown file to mine for bullets (repeatable)")
    # nargs="?" so the bare flag every transcript and the roadmap gate's own nudge already spell
    # keeps working and keeps meaning `web`. bootstrap takes no positionals, so the usual hazard of
    # an optional-value flag swallowing the next argument cannot arise here; a test pins it anyway.
    boot.add_argument("--surface-sweep", nargs="?", const=DEFAULT_STARTER_PROFILE, default=None,
                      metavar="PROFILE",
                      help="also add starter surfaces the docs omit: %s (default: %s)"
                           % (", ".join(sorted(STARTER_SURFACES)), DEFAULT_STARTER_PROFILE))
    boot.add_argument("--sections-exclude", dest="sections_exclude",
                      help="regex of headings to skip (default: run/meta sections)")
    boot.set_defaults(func=cmd_bootstrap)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SystemExit:
        raise
    except FileNotFoundError as exc:
        _die(str(exc))
    except (KeyError, ValueError) as exc:
        _die(str(exc))


if __name__ == "__main__":
    sys.exit(main())
