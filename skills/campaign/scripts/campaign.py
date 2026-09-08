#!/usr/bin/env python3
"""campaign — a manifest that holds the plan, a status that is computed, a close that refuses.

A campaign is a unit of work larger than one session: an objective, a set of roadmap
items, waves of delegated workers, and a close-out. This engine decides only what a
script can decide about that record.

THE RULE THIS FILE EXISTS TO ENFORCE. **The manifest stores the plan and never a status.**
Waves, per-worker scope and reserved identifiers are decisions someone made, and a file is
the right place for them. A status is a claim that was true when it was written, and it
goes stale silently — the file reads identically whether it is current or six hours old.
So `validate` refuses a manifest carrying one, and `status` recomputes from two channels
every time it is asked (ADR-0113).

WHAT IT DOES NOT DO. Launching, integrating and tearing down a worker belong to
`successor`. The verdict on one delegated session belongs to `successor-manager` — nothing
here opens a daemon socket or reads a session registry. Deleting residue belongs to
`tidy`; close hands residue over as a list and removes nothing.

Landedness is asked of `.claude/scripts/lib/branch-landedness.sh`, which is THE
implementation of that predicate. Never ancestry: this repository lands by rebase merge,
and `git merge-base --is-ancestor` answered "not merged" for 56 of 110 landed branches
(ADR-0093).

Usage:
    python3 -m scripts.campaign validate --root <repo> --manifest <file>
    python3 -m scripts.campaign status   --root <repo> --manifest <file> [--json]
    python3 -m scripts.campaign close    --root <repo> --manifest <file> [--json]

Exit codes are the interface, so a caller greps nothing:
    0   validated / computed / closeable
    1   refused: the manifest is malformed, or a named item is not done
    2   could not determine — a channel could not be read, or the manifest is unreadable
    64  usage

Stdout is data, stderr is diagnostics.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_UNDETERMINED = 2
EXIT_USAGE = 64

#: Verdicts a worker row may carry. `undetermined` is mandatory, not a fallback for
#: laziness: "I looked and found nothing" and "I could not look" are different answers,
#: and a classifier without the second invents the first silently.
LANDED, OPEN, UNDETERMINED = "landed", "open", "undetermined"

#: Keys that assert a state rather than record a decision. Refused wherever they appear —
#: on the campaign and on a worker row alike. `evidence` is in the set because the landed
#: sha is the roadmap's to hold; copied here it is a second source of truth that drifts.
FORBIDDEN_STATE_KEYS = (
    "status", "state", "progress", "completed", "complete",
    "evidence", "landed", "done", "verdict",
)

#: Roadmap content a manifest must reference by id rather than copy.
FORBIDDEN_COPY_KEYS = ("title", "acceptance")

DEFAULT_BASE = "origin/main"
DEFAULT_REMOTE = "origin"

LANDEDNESS_LIB = os.path.join(".claude", "scripts", "lib", "branch-landedness.sh")
ROADMAP_REL = os.path.join(".claude", "docs", "roadmap", "roadmap.json")

#: Where a project under `projects/` keeps its roadmap. No `.claude/` above it — that
#: directory is the harness's, and a project is its own repository (ADR-0001 in each).
PROJECT_ROADMAP_REL = os.path.join("docs", "roadmap", "roadmap.json")

#: The roadmap engine's own identity rule, called rather than copied — for the same reason
#: `bl_classify` is called rather than reimplemented. A roadmap's `scope` field is its
#: MEMORY CLASS ("operational"); the prefix in `harness:RM-0302` is its SLUG, which is the
#: document's `slug` when it declares one and otherwise derived from its path. Comparing an
#: id's prefix against `scope` reads every qualified id in this repository as foreign.
ROADMAP_SCHEMA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "roadmap", "scripts", "schema.py",
)


# ---------------------------------------------------------------------- git

def _check_root(root: str) -> None:
    """A root is validated before every git call, never assumed.

    `git -C ""` means the *current* repository: an empty or mistaken root does not fail,
    it silently runs the command against whatever tree the process happens to be in.
    """
    if not root or not isinstance(root, str) or not os.path.isdir(root):
        raise ValueError(f"refusing git with an unusable root: {root!r}")


def git_out(root: str, *args: str) -> tuple[int, str]:
    """Run git against a validated root; return its exit code and stdout."""
    _check_root(root)
    proc = subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True
    )
    return proc.returncode, proc.stdout.strip()


def have_ref(root: str, ref: str) -> bool:
    return git_out(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")[0] == 0


def classify_landedness(root: str, ref: str, base: str, lib: str) -> str:
    """`bl_classify` from the landedness library — the one implementation of the predicate.

    Shelling out is deliberate. A Python reimplementation would be a second source of
    truth for the question close-out turns on, and would have to re-derive that library's
    residue rules — a partially-paired ref is `undetermined`, a bounded pairing that times
    out is `undetermined`, a channel that could not look is `evidence-unavailable`.
    """
    _check_root(root)
    if not os.path.isfile(lib):
        return "evidence-unavailable"
    script = '. "$1"; bl_classify "$2" "$3" "$4"'
    proc = subprocess.run(
        ["bash", "-c", script, "bash", lib, root, ref, base],
        capture_output=True, text=True,
    )
    verdict = proc.stdout.strip()
    if proc.returncode != 0 or not verdict:
        return "evidence-unavailable"
    return verdict


# ----------------------------------------------------------------- manifest

class ManifestError(Exception):
    """The manifest is malformed — a refusal, exit 1."""


class UnreadableError(Exception):
    """The manifest could not be read at all — undetermined, exit 2."""


def load_manifest(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except OSError as exc:
        raise UnreadableError(f"manifest could not be read: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UnreadableError(f"manifest is not JSON: {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ManifestError("manifest must be a JSON object")
    return doc


def workers_of(doc: dict) -> list[dict]:
    """Every worker row, in wave order. Waves order the work; they do not scope it."""
    rows: list[dict] = []
    waves = doc.get("waves") or []
    if not isinstance(waves, list):
        raise ManifestError("`waves` must be a list")
    for wave in waves:
        if not isinstance(wave, dict):
            raise ManifestError("each wave must be an object")
        members = wave.get("workers") or []
        if not isinstance(members, list):
            raise ManifestError("a wave's `workers` must be a list")
        for member in members:
            if not isinstance(member, dict):
                raise ManifestError("each worker must be an object")
            row = dict(member)
            row.setdefault("wave", wave.get("wave"))
            rows.append(row)
    return rows


def validate(doc: dict) -> list[str]:
    """Return the manifest's findings. Empty means it holds a plan and nothing else."""
    findings: list[str] = []

    for key in ("campaign", "objective"):
        if not doc.get(key):
            findings.append(f"manifest is missing `{key}`")

    for key in FORBIDDEN_STATE_KEYS:
        if key in doc:
            findings.append(
                f"manifest stores `{key}` — a campaign's status is computed at read time, "
                "never recorded (ADR-0113)"
            )

    rows = workers_of(doc)
    if not rows:
        findings.append("campaign declares no workers — nothing would be examined")

    seen: set[str] = set()
    for row in rows:
        label = row.get("branch") or row.get("worker") or row.get("item") or "<unnamed>"
        for key in ("worker", "branch", "item"):
            if not row.get(key):
                findings.append(f"worker {label}: missing `{key}`")
        item = row.get("item") or ""
        if item and ":" not in item:
            findings.append(
                f"worker {label}: item `{item}` is unqualified — use `<roadmap>:<id>`"
            )
        if item:
            if item in seen:
                findings.append(f"item {item} is claimed by more than one worker")
            seen.add(item)
        for key in FORBIDDEN_STATE_KEYS:
            if key in row:
                findings.append(
                    f"worker {label}: stores `{key}` — status is computed, never recorded"
                )
        for key in FORBIDDEN_COPY_KEYS:
            if key in row:
                findings.append(
                    f"worker {label}: copies the roadmap's `{key}` — reference the item id; "
                    "a copy is a second source of truth that drifts"
                )
    return findings


# ------------------------------------------------------------------ roadmap

def _roadmap_schema():
    """The roadmap engine's `schema` module, or None when it cannot be loaded."""
    import importlib.util

    if not os.path.isfile(ROADMAP_SCHEMA):
        return None
    spec = importlib.util.spec_from_file_location("_roadmap_schema", ROADMAP_SCHEMA)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # a roadmap engine this one cannot load is a channel it cannot read
        return None
    return module


def roadmap_slug(doc: dict, path: str) -> str | None:
    """The roadmap's identity — the half of a qualified id before the colon.

    Declared wins; otherwise the engine that owns the rule derives it. None means the
    identity could not be established, which is `undetermined` and never a match.
    """
    declared = doc.get("slug") if isinstance(doc, dict) else None
    if isinstance(declared, str) and declared:
        return declared
    module = _roadmap_schema()
    if module is None:
        return None
    try:
        return module.slug_of(doc, path)
    except Exception:
        return None


def load_roadmap(path: str) -> tuple[str, dict]:
    """The roadmap's slug and its items by id. Unreadable is undetermined, not empty."""
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise UnreadableError(f"roadmap could not be read: {path}: {exc}") from exc
    items = doc.get("items") if isinstance(doc, dict) else doc
    if not isinstance(items, list):
        raise UnreadableError(f"roadmap has no item list: {path}")
    slug = roadmap_slug(doc if isinstance(doc, dict) else {}, path)
    return slug, {item.get("id"): item for item in items if isinstance(item, dict)}


# -------------------------------------------------------------------- rows

def row_verdict(
    root: str, row: dict, slug: str | None, items: dict, base: str, remote: str, lib: str
) -> dict:
    """One worker's verdict, from channels the worker does not control.

    Order matters. The remote is consulted first because the other channels cannot report
    their own absence: a roadmap read from a stale checkout and a landedness computed
    against a base nobody fetched both answer confidently.
    """
    item = row.get("item", "")
    branch = row.get("branch", "")
    out = {
        "item": item,
        "branch": branch,
        "worker": row.get("worker", ""),
        "wave": row.get("wave"),
        "published": None,
        "landedness": None,
    }

    def settle(verdict: str, reason: str) -> dict:
        out["verdict"] = verdict
        out["reason"] = reason
        return out

    rc, published = git_out(root, "ls-remote", "--heads", remote, branch)
    if rc != 0:
        return settle(
            UNDETERMINED,
            f"remote `{remote}` could not be consulted — landedness was not established",
        )
    out["published"] = published.split()[0] if published else None

    item_slug, _, item_id = item.partition(":")
    if item_slug and slug is None:
        return settle(
            UNDETERMINED,
            f"item names roadmap `{item_slug}` and this roadmap's identity could not be "
            "established",
        )
    if item_slug and item_slug != slug:
        return settle(
            UNDETERMINED,
            f"item names roadmap `{item_slug}`, but this is roadmap `{slug}` — "
            "resolving it here would answer about the wrong roadmap",
        )
    entry = items.get(item_id)
    if entry is None:
        return settle(UNDETERMINED, f"no roadmap item `{item}` — its status is unknown")

    status = entry.get("status")
    if status != "done":
        return settle(OPEN, f"roadmap status is `{status}`, not `done`")
    evidence = (entry.get("evidence") or "").strip()
    if not evidence:
        return settle(OPEN, "roadmap says `done` with no landed sha")
    out["evidence"] = evidence

    # A branch deleted after landing is the ordinary end state, so fall back to the
    # recorded sha rather than reporting the missing ref as a failure to look.
    ref = branch if have_ref(root, branch) else evidence
    landedness = classify_landedness(root, ref, base, lib)
    out["landedness"] = landedness
    if landedness in ("evidence-unavailable", "undetermined"):
        return settle(
            UNDETERMINED, f"landedness of `{ref}` against `{base}` is {landedness}"
        )
    if landedness == "unlanded":
        return settle(
            UNDETERMINED,
            f"channels disagree: roadmap says `done` at {evidence[:8]}, "
            f"content of `{ref}` is not in `{base}`",
        )
    return settle(LANDED, f"content of `{ref}` is in `{base}`")


def project_root_of(doc: dict, root: str) -> str | None:
    """The repository this campaign's WORK lives in, or None when it is `root` itself.

    `--root` names the repository the manifest and the harness live in; a campaign's work
    may be somewhere else entirely — `projects/<slug>`, its own git repository with its
    own remote and its own roadmap. Two things depend on getting this right, and both
    fail the same silent way when it is wrong: the roadmap is read from the wrong file,
    and branch landedness is computed in a repository that does not have the branches, so
    every row comes back `absent` and absent is indistinguishable from a real negative.

    A declared `project` that does not resolve is `undetermined`, never a fall back to the
    default: reporting on the harness roadmap while the operator believes it read the
    project's is a confident wrong answer.
    """
    declared = doc.get("project")
    if declared in (None, ""):
        return None
    if not isinstance(declared, str):
        raise ManifestError("manifest `project` must be a path")
    path = declared if os.path.isabs(declared) else os.path.join(root, declared)
    path = os.path.normpath(path)
    if not os.path.isdir(path):
        raise UnreadableError(
            f"manifest declares project `{declared}`, which does not resolve: {path}"
        )
    return path


def roadmap_path_for(args, doc: dict, project_root: str | None) -> str:
    """Flag, then the manifest's project, then the harness default."""
    if args.roadmap:
        return args.roadmap
    if project_root:
        return os.path.join(project_root, PROJECT_ROADMAP_REL)
    return os.path.join(args.root, ROADMAP_REL)


def compute(args, doc: dict) -> tuple[list[dict], str]:
    """Every row, and the campaign's overall verdict. Nothing is written."""
    project_root = project_root_of(doc, args.root)
    slug, items = load_roadmap(roadmap_path_for(args, doc, project_root))
    work_root = project_root or args.root
    base = args.base or doc.get("base") or DEFAULT_BASE
    remote = args.remote or doc.get("remote") or DEFAULT_REMOTE
    rows = [
        row_verdict(work_root, row, slug, items, base, remote, args.landedness_lib)
        for row in workers_of(doc)
    ]
    verdicts = {row["verdict"] for row in rows}
    if UNDETERMINED in verdicts:
        overall = UNDETERMINED
    elif OPEN in verdicts:
        overall = OPEN
    else:
        overall = LANDED
    return rows, overall


def residue_of(rows: list[dict]) -> list[dict]:
    """What a closed campaign leaves behind, for `tidy` to decide about.

    Listed, never removed. The skill that diagnoses is not the skill that deletes
    (the division `leek` holds, ADR-0088).
    """
    return [
        {
            "branch": row["branch"],
            "worker": row["worker"],
            "published": row.get("published"),
            "worktree": os.path.join(".claude", "worktrees", row["worker"] or ""),
        }
        for row in rows
    ]


# -------------------------------------------------------------- subcommands

def _prepare(args) -> dict:
    doc = load_manifest(args.manifest)
    findings = validate(doc)
    if findings:
        for finding in findings:
            print(f"refused: {finding}", file=sys.stderr)
        raise ManifestError("manifest is not a plan-only campaign record")
    return doc


def cmd_validate(args) -> int:
    _prepare(args)
    print(f"validated: {args.manifest}")
    return EXIT_OK


def cmd_status(args) -> int:
    doc = _prepare(args)
    rows, overall = compute(args, doc)
    if args.json:
        print(json.dumps(
            {"campaign": doc.get("campaign"), "verdict": overall, "rows": rows},
            indent=1, sort_keys=True,
        ))
    else:
        print(f"campaign: {doc.get('campaign')}  verdict: {overall}")
        for row in rows:
            print(
                f"  [{row['verdict']:<12}] {row['item']:<18} {row['branch']:<28} "
                f"{row['reason']}"
            )
    # A row nobody could determine is a finding, never a silence.
    return EXIT_UNDETERMINED if overall == UNDETERMINED else EXIT_OK


def cmd_close(args) -> int:
    doc = _prepare(args)
    rows, overall = compute(args, doc)
    blockers = [row for row in rows if row["verdict"] == OPEN]
    unknown = [row for row in rows if row["verdict"] == UNDETERMINED]
    residue = residue_of(rows)

    if args.json:
        print(json.dumps({
            "campaign": doc.get("campaign"),
            "verdict": "closeable" if overall == LANDED else "refused",
            "rows": rows,
            "blockers": [row["item"] for row in blockers],
            "undetermined": [row["item"] for row in unknown],
            "residue": residue,
            "close_out": doc.get("close_out", []),
        }, indent=1, sort_keys=True))

    for row in blockers:
        print(
            f"blocked: {row['item']} on {row['branch']} — {row['reason']}",
            file=sys.stderr,
        )
    for row in unknown:
        print(
            f"undetermined: {row['item']} on {row['branch']} — {row['reason']}",
            file=sys.stderr,
        )

    # Precedence, and it is the point: a run that names blockers *and* failed to look has
    # an incomplete blocker list. Reporting exit 1 there would present a partial list as
    # the whole of what stands in the way.
    if unknown:
        print(
            f"REFUSED: {len(unknown)} item(s) undetermined — a check that could not look "
            "is never a clear close",
            file=sys.stderr,
        )
        return EXIT_UNDETERMINED
    if blockers:
        print(f"REFUSED: {len(blockers)} item(s) not landed", file=sys.stderr)
        return EXIT_BLOCKED

    if not args.json:
        print(f"closeable: every item in `{doc.get('campaign')}` has landed")
        for entry in doc.get("close_out", []):
            print(f"  close-out: {entry}")
        print("  residue for `tidy` (nothing removed here):")
        for entry in residue:
            print(f"    {entry['branch']}  {entry['worktree']}")
    return EXIT_OK


# --------------------------------------------------------------------- CLI

class _Parser(argparse.ArgumentParser):
    """Usage errors exit 64. argparse's own 2 is this engine's `undetermined`."""

    def error(self, message: str):  # pragma: no cover - argparse plumbing
        self.print_usage(sys.stderr)
        print(f"usage error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="campaign", description=__doc__.splitlines()[0])
    subs = parser.add_subparsers(dest="command", required=True)
    default_lib = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))),
        "scripts", "lib", "branch-landedness.sh",
    )
    for name, handler, help_text in (
        ("validate", cmd_validate, "refuse a manifest that stores anything but the plan"),
        ("status", cmd_status, "compute one verdict per worker; write nothing"),
        ("close", cmd_close, "refuse the close while any item is unlanded or unknown"),
    ):
        sub = subs.add_parser(name, help=help_text)
        sub.add_argument("--root", required=True, help="repository root; never inferred")
        sub.add_argument("--manifest", required=True, help="path to the campaign record")
        sub.add_argument("--roadmap", default=None,
                         help="this flag, else <project>/" + PROJECT_ROADMAP_REL
                              + " when the manifest declares one, else <root>/" + ROADMAP_REL)
        sub.add_argument("--base", default=None, help=f"comparison ref (default {DEFAULT_BASE})")
        sub.add_argument("--remote", default=None, help=f"remote (default {DEFAULT_REMOTE})")
        sub.add_argument("--landedness-lib", default=default_lib, help=f"default <repo>/{LANDEDNESS_LIB}")
        sub.add_argument("--json", action="store_true", help="one document on stdout")
        sub.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or EXIT_USAGE)
    try:
        _check_root(args.root)
    except ValueError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        return args.handler(args)
    except ManifestError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    except UnreadableError as exc:
        print(f"undetermined: {exc}", file=sys.stderr)
        return EXIT_UNDETERMINED


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
