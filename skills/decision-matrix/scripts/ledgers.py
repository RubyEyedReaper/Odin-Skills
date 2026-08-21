"""DEC ledger discovery and integrity checking (stdlib only).

THE INCIDENT (2026-08-19, issue #244). Three records — DEC-0020, DEC-0021, DEC-0022 —
sat in `.claude/docs/decisions/` with no row in the sibling README, while every gate in
`ci-local.sh` was green. A blank line after the DEC-0015 row had also ended the index
table under GFM, so three further rows rendered as a paragraph of pipes rather than as
rows. Nothing in the repository could see either fact.

Root cause is systemic rather than careless: `ledger.py::update_readme_index` maintains
the index, and a record written by hand never invokes it. Hand-writing records is exactly
what the harness asks parallel workers to do, because DEC numbers are allocated by reading
the ledger and collide across worktrees. So the index will keep drifting, and the only
thing that closes it is a check.

WHY THIS LIVES WITH THE PRODUCER. A DEC ledger is the output format of
`decision-matrix`'s own `ledger.py`, wherever that writer deposited it. The invariant that
a record and its index row agree therefore belongs beside the writer, not in a general
harness script — one invariant, one owner. `.claude/tests/decision-ledger.test.sh` is the
harness half: it proves this checker bites.

BOUNDARY (ADR-0026, and DEC-0003's exclude-and-report precedent). The scan covers the
harness ledger plus every `projects/<slug>/docs/decisions/`, because the same writer
produces all of them. A `projects/<slug>/` that is **its own git repository** is skipped
and named — the harness cannot commit a fix into another repo, so a failure there is one
its owner cannot clear.

WHAT IS DELIBERATELY NOT CHECKED:

- *No harness record may mention a `projects/*` path.* Issue #244 proposed it; it is a
  false-positive generator. DEC-0003's own goal line is about `projects/*` subtrees and
  DEC-0005's body discusses `projects/<name>/docs/decisions` — both legitimate harness
  decisions about the project boundary. The tight version of that invariant already has an
  owner in `odin-project-doc-guard.sh`, which enumerates real slugs from disk.
- *No gaps in the numbering.* `next_dec_number` is max+1 and workers reserve id blocks in
  advance, so gaps (0010, 0013, 0016 today) are the expected residue of normal operation.
  A contiguity predicate would be red forever on a healthy ledger.

Usage:  python3 -m scripts.ledgers [--root ROOT] [--json]
Exit:   0 every ledger consistent
        1 at least one violation, one FAIL line each
        2 no ledger found at all — "could not look" is not "found nothing"
"""
import argparse
import json
import re
import sys
from pathlib import Path

_RECORD_RE = re.compile(r"^DEC-(\d{4})-.*\.md$")
_ROW_RE = re.compile(r"^\|\s*(DEC-\d{4})\s*\|")
_DEC_ID_RE = re.compile(r"^dec_id:\s*(\S+)\s*$", re.MULTILINE)
_LINK_RE = re.compile(r"\]\(([^)]+)\)")

# scripts/ -> decision-matrix/ -> skills/ -> .claude/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]


def discover_ledgers(root: Path) -> tuple:
    """Find every DEC ledger under root.

    Returns ``(ledgers, skipped)``: a sorted list of directories, and a list of
    ``(path, reason)`` pairs for subtrees deliberately not checked. Both are reported —
    a skip nobody prints is indistinguishable from a directory nobody found.
    """
    root = Path(root)
    ledgers = []
    skipped = []

    harness = root / ".claude" / "docs" / "decisions"
    if harness.is_dir():
        ledgers.append(harness)

    projects = root / "projects"
    if projects.is_dir():
        for project in sorted(p for p in projects.iterdir() if p.is_dir()):
            ledger = project / "docs" / "decisions"
            if not ledger.is_dir():
                continue
            if (project / ".git").exists():
                skipped.append((ledger, "nested repository — its ledger is its own repo's business"))
                continue
            ledgers.append(ledger)

    return ledgers, skipped


def _index_rows(readme: Path) -> dict:
    """Map DEC id -> list of (line number, link target) for rows inside the index table.

    Only rows in the contiguous block a header separator opens count. A row after a blank
    line is not a table row under GFM, and treating it as one is how the split index went
    unnoticed: the naive scan reports a healthy table that renders as a paragraph.
    """
    rows = {}
    if not readme.is_file():
        return rows

    lines = readme.read_text(encoding="utf-8").splitlines()
    in_table = False
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("|--"):
            in_table = True
            continue
        if in_table and not stripped.startswith("|"):
            in_table = False
            continue
        if not in_table:
            continue
        match = _ROW_RE.match(stripped)
        if match:
            link = _LINK_RE.search(stripped)
            rows.setdefault(match.group(1), []).append((i, link.group(1) if link else None))
    return rows


def check_ledger(ledger: Path) -> list:
    """Return a list of human-readable failure strings for one ledger directory."""
    failures = []
    records = sorted(p for p in ledger.glob("DEC-*.md") if _RECORD_RE.match(p.name))
    readme = ledger / "README.md"

    if records and not readme.is_file():
        failures.append(f"{ledger}: {len(records)} record(s) and no README.md to index them")
        return failures

    rows = _index_rows(readme)

    for record in records:
        number = _RECORD_RE.match(record.name).group(1)
        expected = f"DEC-{number}"

        head = record.read_text(encoding="utf-8")[:2000]
        declared = _DEC_ID_RE.search(head)
        if declared is None:
            failures.append(f"{record}: no dec_id in the frontmatter")
        elif declared.group(1) != expected:
            failures.append(
                f"{record}: dec_id is {declared.group(1)} but the filename says {expected} — "
                "a record and its own id disagree"
            )

        found = rows.get(expected, [])
        if not found:
            failures.append(
                f"{record.name}: no row in {readme.name}. A hand-written record does not "
                "invoke update_readme_index; add the row or write the record through the engine."
            )
        elif len(found) > 1:
            lines = ", ".join(str(n) for n, _ in found)
            failures.append(f"{expected}: {len(found)} rows in {readme.name} (lines {lines}) — exactly one expected")

    known = {_RECORD_RE.match(p.name).group(1) for p in records}
    for dec_id, entries in sorted(rows.items()):
        if dec_id[4:] not in known:
            failures.append(f"{readme}: row {dec_id} (line {entries[0][0]}) names no record on disk")
        for line_no, target in entries:
            if target and not (ledger / target).exists():
                failures.append(f"{readme}:{line_no}: row {dec_id} links {target}, which does not exist")

    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check every DEC ledger's records against its index.")
    parser.add_argument("--root", default=str(_REPO_ROOT), help="repository root to scan")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report on stdout")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"FAIL: root is not a directory: {root}", file=sys.stderr)
        return 2

    ledgers, skipped = discover_ledgers(root)

    if not ledgers:
        # Not exit 0. A scanner that finds no corpus has not looked; reporting that as
        # clean is the failure mode that let 76 uncaptured issues read as "no drift".
        print(f"FAIL: no DEC ledger found under {root} — this gate could not look", file=sys.stderr)
        return 2

    failures = []
    per_ledger = []
    for ledger in ledgers:
        found = check_ledger(ledger)
        failures.extend(found)
        records = sum(1 for p in ledger.glob("DEC-*.md") if _RECORD_RE.match(p.name))
        rows = len(_index_rows(ledger / "README.md"))
        per_ledger.append(
            {"ledger": str(ledger.relative_to(root)), "records": records, "rows": rows, "failures": found}
        )

    if args.json:
        print(json.dumps({
            "root": str(root),
            "ledgers": per_ledger,
            "skipped": [{"ledger": str(p.relative_to(root)), "reason": r} for p, r in skipped],
            "ok": not failures,
        }, indent=2))
    else:
        for ledger, reason in skipped:
            print(f"SKIP {ledger.relative_to(root)} — {reason}")
        for entry in per_ledger:
            status = "OK  " if not entry["failures"] else "FAIL"
            print(f"{status} {entry['ledger']}: {entry['records']} records, {entry['rows']} rows")
        for failure in failures:
            print(f"FAIL: {failure}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
