"""workflow — the lifecycle engine for the repository's reusable workflow chains.

A *manifest* is a markdown document carrying exactly one fenced JSON block. The prose is
for the human reading it beside the chain it describes; the block is the versioned,
owned record this engine acts on. `json.loads` does the parsing, so what the engine reads
is what a reader reads — a hand-rolled parser would only assert what its author assumed.

What this engine decides is what a script can decide: is a manifest well-formed, is it
retired, and did the set it was pointed at contain anything at all. It does **not**
execute a workflow's steps — `run` resolves and emits them for the agent to follow, and
opens a run record. There is no general workflow runtime here, deliberately: see
ADR-0102.

Usage:
    python3 -m scripts.workflow validate [--root R] [--id ID] [--json]
    python3 -m scripts.workflow run ID [--root R] [--json] [--dry-run]
    python3 -m scripts.workflow status [--root R] [--json]
    python3 -m scripts.workflow record ID --outcome {ok,failed} [--note T] [--root R]
    python3 -m scripts.workflow retire ID (--superseded-by ID | --reason T) [--dry-run]

Exit codes are one per failure class, so a caller branches without parsing text:

    0  success
    1  validation findings — a manifest is malformed
    2  usage error, or an input that cannot be read
    3  refused: the manifest is retired
    4  refused: the manifest set is empty, so nothing was examined

Stdout is data, stderr is diagnostics. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_RETIRED = 3
EXIT_EMPTY = 4

MANIFEST_SUFFIX = ".workflow.md"
MANIFEST_DIR = os.path.join(".claude", "docs", "workflows")
RUN_CLASS = os.path.join(".claude", ".runtime", "workflow-run")

STATUSES = ("draft", "active", "retired")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

#: The ten lifecycle fields the schema requires, plus `steps` — the body those ten
#: describe. `dependencies` is the one list allowed to be empty: a chain that depends on
#: nothing is ordinary, whereas one that produces nothing is a finding.
LIST_FIELDS = ("inputs", "outputs", "dependencies", "decision_points",
               "failure_handling", "completion_criteria", "steps")
REQUIRED = ("id", "version", "status", "owner", "supersedes") + LIST_FIELDS
MAY_BE_EMPTY = ("dependencies",)

JSON_BLOCK_RE = re.compile(r"^```json\s*$(.*?)^```\s*$", re.M | re.S)


class ManifestError(Exception):
    """A manifest file that cannot be turned into an object at all."""


# ---------------------------------------------------------------- reading


def repo_root(explicit: str | None) -> str:
    """Resolve the root: flag, then environment, then the engine's own location.

    Never the working directory. A tool inherits whatever directory a prior command left
    behind, which is not reliably where its data lives (`.claude/rules/cli/patterns.md`).
    """
    if explicit:
        return os.path.abspath(explicit)
    if os.environ.get("ODIN_ROOT"):
        return os.path.abspath(os.environ["ODIN_ROOT"])
    here = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(here, ".claude")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return os.getcwd()
        here = parent


def manifest_dir(root: str) -> str:
    return os.path.join(root, MANIFEST_DIR)


def manifest_paths(root: str) -> list[str]:
    directory = manifest_dir(root)
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.endswith(MANIFEST_SUFFIX)
    )


def stem_of(path: str) -> str:
    return os.path.basename(path)[: -len(MANIFEST_SUFFIX)]


def find_block(text: str, path: str):
    """Return the match for the single fenced JSON block.

    Two blocks is refused rather than resolved by taking the first: an ambiguity a tool
    silently picks a side of is a defect that surfaces months later, in the half nobody
    was editing.
    """
    matches = list(JSON_BLOCK_RE.finditer(text))
    if len(matches) != 1:
        raise ManifestError(
            f"{os.path.basename(path)}: expected exactly one fenced json block, found {len(matches)}"
        )
    return matches[0]


def replace_block(text: str, path: str, manifest: dict) -> str:
    r"""Rewrite only the fenced block, leaving every byte of prose around it alone.

    The whole fence is replaced rather than the captured group: `\s*$` after the opening
    fence leaves the newline on either side of the boundary depending on the file, so
    splicing on group spans silently produced ```` ```json{ ```` — a file the engine that
    wrote it could no longer read.
    """
    match = find_block(text, path)
    block = "```json\n" + json.dumps(manifest, indent=2) + "\n```"
    return text[: match.start()] + block + text[match.end():]


def read_manifest(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ManifestError(f"{os.path.basename(path)}: {exc.strerror}") from exc
    block = find_block(text, path).group(1)
    try:
        manifest = json.loads(block)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{os.path.basename(path)}: unparseable json — {exc.msg}") from exc
    if not isinstance(manifest, dict):
        raise ManifestError(f"{os.path.basename(path)}: manifest block is not an object")
    return manifest


# ---------------------------------------------------------------- validation


def validate_manifest(manifest: dict, path: str) -> list[str]:
    """Every rule that fails, not the first — one pass should list the whole repair."""
    findings: list[str] = []
    name = os.path.basename(path)

    for field in REQUIRED:
        if field not in manifest:
            findings.append(f"{name}: missing required field `{field}`")

    if manifest.get("id") is not None and manifest.get("id") != stem_of(path):
        findings.append(
            f"{name}: `id` is {manifest['id']!r} but the filename stem is {stem_of(path)!r}"
        )

    version = manifest.get("version")
    if version is not None and not (isinstance(version, str) and VERSION_RE.match(version)):
        findings.append(f"{name}: `version` must be three numeric parts, got {version!r}")

    status = manifest.get("status")
    if status is not None and status not in STATUSES:
        findings.append(f"{name}: `status` must be one of {'/'.join(STATUSES)}, got {status!r}")

    if "supersedes" in manifest and not isinstance(manifest["supersedes"], (str, type(None))):
        findings.append(f"{name}: `supersedes` must be a workflow id or null")

    if "owner" in manifest and not (isinstance(manifest["owner"], str) and manifest["owner"].strip()):
        findings.append(f"{name}: `owner` must name someone accountable")

    for field in LIST_FIELDS:
        if field not in manifest:
            continue
        value = manifest[field]
        if not isinstance(value, list):
            findings.append(f"{name}: `{field}` must be a list")
        elif not value and field not in MAY_BE_EMPTY:
            findings.append(f"{name}: `{field}` is empty")

    findings.extend(_validate_steps(manifest, name))
    findings.extend(_validate_shapes(manifest, name))

    if status == "retired":
        evidence = manifest.get("retired")
        if not isinstance(evidence, dict) or not (
            evidence.get("reason") or evidence.get("superseded_by")
        ):
            findings.append(
                f"{name}: a retired workflow needs a `retired` block naming a reason or a successor"
            )
    return findings


def _validate_steps(manifest: dict, name: str) -> list[str]:
    steps = manifest.get("steps")
    if not isinstance(steps, list) or not steps:
        return []
    findings = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            findings.append(f"{name}: step {index} is not an object")
            continue
        if step.get("step") != index:
            findings.append(
                f"{name}: steps must be numbered from 1 without gaps — "
                f"position {index} declares step {step.get('step')!r}"
            )
        for key in ("skill", "gates"):
            if not (isinstance(step.get(key), str) and step[key].strip()):
                findings.append(f"{name}: step {index} is missing `{key}`")
    return findings


def _validate_shapes(manifest: dict, name: str) -> list[str]:
    """`decision_points` and `failure_handling` carry structure, not free prose."""
    findings = []
    step_count = len(manifest["steps"]) if isinstance(manifest.get("steps"), list) else 0

    points = manifest.get("decision_points")
    if isinstance(points, list):
        for index, point in enumerate(points, start=1):
            if not isinstance(point, dict) or "at" not in point or "question" not in point:
                findings.append(
                    f"{name}: decision_points[{index}] needs `at` and `question`"
                )
                continue
            at = point["at"]
            if not isinstance(at, int) or not 1 <= at <= step_count:
                findings.append(
                    f"{name}: decision_points[{index}] names step {at!r}, which does not exist"
                )

    handling = manifest.get("failure_handling")
    if isinstance(handling, list):
        for index, entry in enumerate(handling, start=1):
            if not isinstance(entry, dict) or "when" not in entry or "action" not in entry:
                findings.append(
                    f"{name}: failure_handling[{index}] needs `when` and `action`"
                )
    return findings


def load_all(root: str) -> tuple[list[tuple[str, dict]], list[str]]:
    """Read every manifest; unreadable ones become findings rather than tracebacks."""
    loaded, findings = [], []
    for path in manifest_paths(root):
        try:
            loaded.append((path, read_manifest(path)))
        except ManifestError as exc:
            findings.append(str(exc))
    return loaded, findings


# ---------------------------------------------------------------- run records


def session_id() -> str:
    return os.environ.get("CLAUDE_SESSION_ID") or "unattributed"


def run_dir(root: str) -> str:
    return os.path.join(root, RUN_CLASS, session_id())


def read_records(root: str) -> list[tuple[str, dict]]:
    directory = run_dir(root)
    if not os.path.isdir(directory):
        return []
    records = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as handle:
                records.append((os.path.join(directory, name), json.load(handle)))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def write_json(path: str, payload: dict) -> None:
    """Atomic: a half-written record at the real path is worse than no record."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(temp, path)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------- output


def emit(args, payload: dict, lines: list[str]) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        for line in lines:
            print(line)


def report(findings: list[str]) -> None:
    for finding in findings:
        print(finding, file=sys.stderr)


# ---------------------------------------------------------------- subcommands


def resolve_one(root: str, workflow_id: str):
    """Return (path, manifest) or raise ManifestError; unknown id is a usage error."""
    path = os.path.join(manifest_dir(root), workflow_id + MANIFEST_SUFFIX)
    if not os.path.isfile(path):
        return None, None
    return path, read_manifest(path)


def cmd_validate(args) -> int:
    root = repo_root(args.root)
    loaded, findings = load_all(root)

    if args.id:
        loaded = [(p, m) for p, m in loaded if stem_of(p) == args.id]
        findings = [f for f in findings if f.startswith(args.id + MANIFEST_SUFFIX)]

    if not loaded and not findings:
        message = f"no manifests found under {os.path.relpath(manifest_dir(root), root)}"
        if args.json:
            print(json.dumps({"examined": 0, "findings": [], "error": message}, indent=2))
        print(message, file=sys.stderr)
        return EXIT_EMPTY

    for path, manifest in loaded:
        findings.extend(validate_manifest(manifest, path))

    payload = {
        "examined": len(loaded) + len([f for f in findings if ": unparseable" in f]),
        "findings": [{"finding": f} for f in findings],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    if findings:
        report(findings)
        return EXIT_FINDINGS
    if not args.json:
        print(f"{len(loaded)} manifest(s) valid")
    return EXIT_OK


def cmd_status(args) -> int:
    root = repo_root(args.root)
    loaded, findings = load_all(root)
    if not loaded and not findings:
        print(f"no manifests found under {os.path.relpath(manifest_dir(root), root)}", file=sys.stderr)
        return EXIT_EMPTY

    rows = [
        {
            "id": manifest.get("id", stem_of(path)),
            "version": manifest.get("version"),
            "status": manifest.get("status"),
            "owner": manifest.get("owner"),
            "supersedes": manifest.get("supersedes"),
        }
        for path, manifest in loaded
    ]
    # A manifest that could not be read is listed as `unreadable` rather than omitted:
    # a status table that silently drops what it could not parse reports a healthy set.
    for finding in findings:
        rows.append({"id": finding.split(":")[0][: -len(MANIFEST_SUFFIX)],
                     "version": None, "status": "unreadable",
                     "owner": None, "supersedes": None})

    emit(
        args,
        {"workflows": rows},
        [f"{r['id']:<32} {str(r['version'] or '-'):<8} {r['status']}" for r in rows],
    )
    return EXIT_FINDINGS if findings else EXIT_OK


def cmd_run(args) -> int:
    root = repo_root(args.root)
    try:
        path, manifest = resolve_one(root, args.id)
    except ManifestError as exc:
        report([str(exc)])
        return EXIT_FINDINGS
    if path is None:
        print(f"no workflow named {args.id!r} under {MANIFEST_DIR}", file=sys.stderr)
        return EXIT_USAGE

    findings = validate_manifest(manifest, path)
    if findings:
        report(findings)
        return EXIT_FINDINGS

    # Before anything is emitted or written. The refusal is the point of the lifecycle:
    # a status nothing enforces is a comment.
    if manifest["status"] == "retired":
        evidence = manifest.get("retired", {})
        detail = evidence.get("superseded_by") or evidence.get("reason")
        print(f"{args.id} is retired ({detail}) — refusing to run", file=sys.stderr)
        return EXIT_RETIRED

    record_path = os.path.join(run_dir(root), f"{now().replace(':', '-')}-{args.id}.json")
    if not args.dry_run:
        write_json(record_path, {
            "workflow": args.id,
            "version": manifest["version"],
            "started": now(),
            "session": session_id(),
            "outcome": None,
            "note": None,
        })

    steps = manifest["steps"]
    emit(
        args,
        {
            "workflow": args.id,
            "version": manifest["version"],
            "steps": steps,
            "decision_points": manifest["decision_points"],
            "completion_criteria": manifest["completion_criteria"],
            "record": None if args.dry_run else record_path,
        },
        [f"{args.id} v{manifest['version']}"]
        + [f"  {s['step']}. {s['skill']} — {s['gates']}" for s in steps]
        + ["", "complete when:"]
        + [f"  - {c}" for c in manifest["completion_criteria"]],
    )
    return EXIT_OK


def cmd_record(args) -> int:
    root = repo_root(args.root)
    open_runs = [
        (path, record) for path, record in read_records(root)
        if record.get("workflow") == args.id and record.get("outcome") is None
    ]
    if not open_runs:
        print(f"no open run for {args.id!r} in this session", file=sys.stderr)
        return EXIT_USAGE

    path, record = open_runs[-1]
    record["outcome"] = args.outcome
    record["note"] = args.note
    record["closed"] = now()
    write_json(path, record)
    emit(args, {"record": path, "outcome": args.outcome}, [f"{args.id}: {args.outcome}"])
    return EXIT_OK


def bump_minor(version: str) -> str:
    major, minor, _patch = version.split(".")
    return f"{major}.{int(minor) + 1}.0"


def cmd_retire(args) -> int:
    root = repo_root(args.root)
    try:
        path, manifest = resolve_one(root, args.id)
    except ManifestError as exc:
        report([str(exc)])
        return EXIT_FINDINGS
    if path is None:
        print(f"no workflow named {args.id!r} under {MANIFEST_DIR}", file=sys.stderr)
        return EXIT_USAGE

    if manifest.get("status") == "retired":
        print(f"{args.id} is already retired — refusing to overwrite its evidence", file=sys.stderr)
        return EXIT_RETIRED

    if args.superseded_by:
        try:
            successor_path, successor = resolve_one(root, args.superseded_by)
        except ManifestError as exc:
            report([str(exc)])
            return EXIT_FINDINGS
        if successor_path is None:
            print(f"named successor {args.superseded_by!r} does not exist", file=sys.stderr)
            return EXIT_USAGE
        if successor.get("status") == "retired":
            print(
                f"named successor {args.superseded_by!r} is itself retired — "
                "a supersede must point at something runnable",
                file=sys.stderr,
            )
            return EXIT_USAGE
        evidence = {"superseded_by": args.superseded_by}
    else:
        evidence = {"reason": args.reason}

    updated = dict(manifest)
    updated["status"] = "retired"
    updated["version"] = bump_minor(manifest["version"])
    updated["retired"] = dict(evidence, at=now())

    if not args.dry_run:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        rewritten = replace_block(text, path, updated)
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            handle.write(rewritten)
        os.replace(temp, path)

    emit(
        args,
        {"workflow": args.id, "status": "retired", "version": updated["version"],
         "retired": updated["retired"], "dry_run": args.dry_run},
        [f"{args.id} retired at v{updated['version']} "
         f"({evidence.get('superseded_by') or evidence.get('reason')})"
         + (" [dry-run]" if args.dry_run else "")],
    )
    return EXIT_OK


# ---------------------------------------------------------------- entry point


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workflow", description="Lifecycle engine for reusable workflow chains."
    )
    subparsers = parser.add_subparsers(dest="command")

    def common(sub):
        sub.add_argument("--root", help="repository root; never inferred from the cwd")
        sub.add_argument("--json", action="store_true", help="machine-readable output on stdout")
        return sub

    validate = common(subparsers.add_parser("validate", help="check every manifest"))
    validate.add_argument("--id", help="check only this workflow")
    validate.set_defaults(func=cmd_validate)

    common(subparsers.add_parser("status", help="list workflows and their lifecycle state")
           ).set_defaults(func=cmd_status)

    run = common(subparsers.add_parser("run", help="emit a workflow's steps and open a run record"))
    run.add_argument("id")
    run.add_argument("--dry-run", action="store_true", help="emit the steps, write no record")
    run.set_defaults(func=cmd_run)

    record = common(subparsers.add_parser("record", help="close the open run with its outcome"))
    record.add_argument("id")
    record.add_argument("--outcome", required=True, choices=("ok", "failed"))
    record.add_argument("--note")
    record.set_defaults(func=cmd_record)

    retire = common(subparsers.add_parser("retire", help="retire a workflow, with evidence"))
    retire.add_argument("id")
    evidence = retire.add_mutually_exclusive_group()
    evidence.add_argument("--superseded-by", help="the workflow id that replaces this one")
    evidence.add_argument("--reason", help="why this workflow is being abandoned")
    retire.add_argument("--dry-run", action="store_true", help="report the transition, write nothing")
    retire.set_defaults(func=cmd_retire)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK

    if args.command == "retire" and not (args.superseded_by or args.reason):
        print(
            "retire needs evidence: --superseded-by <id> or --reason <text>. "
            "An abandoned workflow and a replaced one are different facts.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    try:
        return args.func(args)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FINDINGS


if __name__ == "__main__":
    sys.exit(main())
