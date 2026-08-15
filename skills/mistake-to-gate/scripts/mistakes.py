#!/usr/bin/env python3
"""The mistake log — parse, count, and report what has now happened often enough to be a rule.

One markdown table per owner, one row per occurrence, recurrence counted by a two-part failure-mode
key. The count is **derived here and never stored**: a stored tally is a correlate of the rows, and
a check keyed on a correlate drifts silently while still passing (`mistake-to-gate` §3).

Fail-closed is the other invariant. An enumeration that finds nothing is an error, never "0 owners,
clean" — a scanner that reports success having examined nothing is the exact defect this system was
built after (audit F10).

Stdlib only. See `.claude/docs/adr/0057-graduated-mistake-system.md`.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import namedtuple
from pathlib import Path

#: Closed set, taken verbatim from `oops` §3 so the key is chosen by a step the procedure already
#: forces — which is what makes two sessions land on the same prefix for the same failure.
CLASSES = ("input", "precondition", "postcondition", "error-path", "ci-gate", "judgment")
STATUSES = ("logged", "guarded", "promoted", "wontfix")
DEFAULT_THRESHOLD = 4
LOG_NAME = "MISTAKES.md"

ID_RE = re.compile(r"^M-\d{4}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")

Row = namedtuple("Row", "id date key cls context artifact fix status line")


class GrammarError(ValueError):
    """A row that cannot be trusted. Never skipped — a skipped row is an uncounted occurrence."""


class EnumerationError(ValueError):
    """The owner enumeration found nothing, or was pointed somewhere that cannot hold owners."""


# --- parsing ---------------------------------------------------------------------------------

def _split_row(line):
    cells = CELL_SPLIT_RE.split(line.strip())
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [c.strip().replace("\\|", "|") for c in cells]


def _is_separator(cells):
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def scan_log(text, path=""):
    """Return `(rows, errors)`. Every malformed row produces an error; none are dropped silently."""
    rows, errors = [], []
    seen_header = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.lstrip().startswith("|"):
            continue
        cells = _split_row(line)
        if _is_separator(cells):
            continue
        if not seen_header:
            seen_header = True          # the column header line
            continue
        where = "%s:%d" % (path or "<log>", lineno)
        if len(cells) != 8:
            errors.append("%s: expected 8 columns, found %d" % (where, len(cells)))
            continue
        rid, date, key, cls, context, artifact, fix, status = cells
        bad = _row_errors(where, rid, date, key, cls, status)
        if bad:
            errors.extend(bad)
            continue
        rows.append(Row(rid, date, key, cls, context, artifact, fix, status, lineno))
    return rows, errors


def _row_errors(where, rid, date, key, cls, status):
    out = []
    if not ID_RE.match(rid):
        out.append("%s: id %r is not M-NNNN" % (where, rid))
    if not DATE_RE.match(date):
        out.append("%s: date %r is not YYYY-MM-DD" % (where, date))
    out.extend(key_errors(key, where))
    if cls not in CLASSES:
        out.append("%s: class %r is not one of %s" % (where, cls, ", ".join(CLASSES)))
    elif "/" in key and cls != key.split("/", 1)[0]:
        out.append("%s: class %r disagrees with the key prefix %r"
                   % (where, cls, key.split("/", 1)[0]))
    if status not in STATUSES:
        out.append("%s: status %r is not one of %s" % (where, status, ", ".join(STATUSES)))
    return out


def key_errors(key, where="key"):
    """The SR-2 grammar: `<class>/<predicate-slug>`, lowercase, exactly one slash."""
    if key.count("/") != 1:
        return ["%s: key %r must be <class>/<slug> with exactly one slash" % (where, key)]
    cls, slug = key.split("/", 1)
    out = []
    if cls not in CLASSES:
        out.append("%s: key class %r is not one of %s" % (where, cls, ", ".join(CLASSES)))
    if not SLUG_RE.match(slug):
        out.append("%s: key slug %r must be lowercase [a-z0-9-]" % (where, slug))
    return out


def parse_log(text, path=""):
    """Strict parse: raises on the first malformed row, reporting `path:line`."""
    rows, errors = scan_log(text, path)
    if errors:
        raise GrammarError(errors[0])
    return rows


# --- counting --------------------------------------------------------------------------------

def counts(rows):
    """Occurrences per key. `wontfix` rows are excluded — they are decisions, not occurrences."""
    out = {}
    for r in rows:
        if r.status == "wontfix":
            continue
        out[r.key] = out.get(r.key, 0) + 1
    return out


def band(count, threshold=DEFAULT_THRESHOLD):
    """The required response for a count — SR-3's ladder, in one place."""
    if count >= threshold:
        return "promoted"
    return "attention" if count >= 2 else "logged"


def due(rows, threshold=DEFAULT_THRESHOLD):
    """Keys that have reached the promotion threshold and are not yet fully promoted."""
    tally = counts(rows)
    out = []
    for key, n in sorted(tally.items()):
        if n < threshold:
            continue
        if all(r.status == "promoted" for r in rows if r.key == key and r.status != "wontfix"):
            continue
        out.append(key)
    return out


def siblings(rows, key):
    """Other keys sharing this key's class — printed so a second spelling is visible on sight."""
    cls = key.split("/", 1)[0]
    return sorted({r.key for r in rows if r.key != key and r.key.split("/", 1)[0] == cls})


def _normalise(key):
    return key.replace("-", "")


def near_duplicates(rows, key):
    """Sibling keys that differ from this one only by hyphenation — a likely accidental re-spelling."""
    return sorted({r.key for r in rows
                   if r.key != key and _normalise(r.key) == _normalise(key)})


# --- owners ----------------------------------------------------------------------------------

def owners(root):
    """`(included, skipped_nested)`.

    An owner is the repository root, plus every `projects/*/` carrying its own `CHANGELOG.md` —
    the same "beside the CHANGELOG" locating rule the logs themselves follow, enumerated from disk
    so a new project is covered the day it appears.

    A project that is its own git repository is **excluded and reported**, never silently dropped:
    the harness cannot commit a file into another repository, and a gate whose fix lives elsewhere
    is a gate that gets disabled (`mistake-to-gate` §4).
    """
    root = Path(root)
    if not root.is_dir():
        raise EnumerationError("not a directory: %s" % root)
    included, skipped = [], []
    if (root / "CHANGELOG.md").is_file():
        included.append(root)
    projects = root / "projects"
    if projects.is_dir():
        for child in sorted(p for p in projects.iterdir() if p.is_dir()):
            if not (child / "CHANGELOG.md").is_file():
                continue
            (skipped if (child / ".git").exists() else included).append(child)
    if not included:
        raise EnumerationError(
            "no owners found under %s — expected a CHANGELOG.md at the root "
            "or under projects/*/ (refusing to report a clean scan of nothing)" % root)
    return included, skipped


# --- appending -------------------------------------------------------------------------------

def _escape(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def next_id(rows):
    if not rows:
        return "M-0001"
    return "M-%04d" % (max(int(r.id.split("-")[1]) for r in rows) + 1)


def append_row(path, key, context, artifact, fix, date=None, status="logged"):
    """Append exactly one row. Existing lines are never rewritten — the log is canonical, not generated."""
    path = Path(path)
    errs = key_errors(key, str(path))
    if errs:
        raise GrammarError(errs[0])
    if status not in STATUSES:
        raise GrammarError("%s: status %r is not one of %s" % (path, status, ", ".join(STATUSES)))
    text = path.read_text() if path.exists() else ""
    rows = parse_log(text, str(path))
    if date is None:
        from datetime import date as _date
        date = _date.today().isoformat()
    if not DATE_RE.match(date):
        raise GrammarError("%s: date %r is not YYYY-MM-DD" % (path, date))
    line = "| %s |\n" % " | ".join([
        next_id(rows), date, key, key.split("/", 1)[0],
        _escape(context), _escape(artifact), _escape(fix), status])
    with path.open("a") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        fh.write(line)


def set_status(path, key, status, fix=None):
    """Mark every row for a key — the closing step of a promotion. Returns the number changed."""
    path = Path(path)
    if status not in STATUSES:
        raise GrammarError("status %r is not one of %s" % (status, ", ".join(STATUSES)))
    lines = path.read_text().splitlines(keepends=True)
    rows = parse_log("".join(lines), str(path))
    changed = 0
    for r in rows:
        if r.key != key or r.status == status:
            continue
        cells = _split_row(lines[r.line - 1])
        cells[7] = status
        if fix:
            cells[6] = _escape(fix)
        lines[r.line - 1] = "| %s |\n" % " | ".join(cells)
        changed += 1
    path.write_text("".join(lines))
    return changed


# --- CLI -------------------------------------------------------------------------------------

HEADER_TEMPLATE = """# Mistakes — {owner} evidence log

Rows are appended by `oops`, one per occurrence; recurrence is counted by `key`
(`.claude/skills/mistake-to-gate/scripts/mistakes.py`). Never hand-edit a `promoted` row.

| id | date | key | class | context | artifact | fix | status |
|---|---|---|---|---|---|---|---|
"""


def _load(owner_path):
    log = Path(owner_path) / LOG_NAME
    if not log.is_file():
        return None, ["%s: missing %s (an empty table under the header is the legal way to say "
                      "'nothing yet')" % (log, LOG_NAME)]
    rows, errors = scan_log(log.read_text(), str(log))
    return rows, errors


def cmd_check(args):
    try:
        included, skipped = owners(args.root)
    except EnumerationError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    for s in skipped:
        print("note: %s is its own repository — it keeps its own %s and its own gate"
              % (s, LOG_NAME), file=sys.stderr)
    findings = []
    for owner in included:
        rows, errors = _load(owner)
        findings.extend(errors)
        if rows is None:
            continue
        for key in due(rows, args.threshold):
            n = counts(rows)[key]
            findings.append(
                "%s/%s: promotion due — %r has %d recorded occurrences (threshold %d). "
                "Run mistake-to-gate: land a mechanical check in this owner's gate list, rule text "
                "in its CLAUDE.md, then mark every row for the key promoted."
                % (owner, LOG_NAME, key, n, args.threshold))
    for f in findings:
        print("FAIL: %s" % f, file=sys.stderr)
    if findings:
        print("%d finding(s) across %d owner(s)" % (len(findings), len(included)), file=sys.stderr)
        return 1
    print("mistake logs clean: %d owner(s), threshold %d" % (len(included), args.threshold))
    return 0


def cmd_report(args):
    try:
        included, skipped = owners(args.root)
    except EnumerationError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    rc = 0
    for owner in included:
        rows, errors = _load(owner)
        print("\n== %s" % owner)
        for e in errors:
            print("  ! %s" % e)
            rc = 1
        if not rows:
            print("  (no occurrences recorded)")
            continue
        tally = counts(rows)
        for key in sorted(tally, key=lambda k: (-tally[k], k)):
            if args.key and key != args.key:
                continue
            n = tally[key]
            print("  %-44s %d  %s" % (key, n, band(n, args.threshold)))
            for other in near_duplicates(rows, key):
                print("      near-duplicate spelling: %s" % other)
            if args.key:
                for s in siblings(rows, key):
                    print("      sibling in class: %s" % s)
                for r in rows:
                    if r.key == key:
                        print("      %s %s [%s] %s — %s" % (r.id, r.date, r.status,
                                                            r.context, r.artifact))
    for s in skipped:
        print("\nnote: %s is its own repository (own log, own gate)" % s)
    return rc


def cmd_append(args):
    log = Path(args.root) / LOG_NAME
    if not log.is_file():
        log.write_text(HEADER_TEMPLATE.format(owner=Path(args.root).resolve().name))
    append_row(log, key=args.key, context=args.context, artifact=args.artifact,
               fix=args.fix, date=args.date, status=args.status)
    rows = parse_log(log.read_text(), str(log))
    n = counts(rows).get(args.key, 0)
    print("%s: %s now has %d occurrence(s) — band %s" % (log, args.key, n,
                                                         band(n, args.threshold)))
    for other in near_duplicates(rows, args.key):
        print("warning: near-duplicate spelling already in this log: %s" % other, file=sys.stderr)
    return 0


def cmd_promote(args):
    log = Path(args.root) / LOG_NAME
    if not log.is_file():
        print("FAIL: %s does not exist" % log, file=sys.stderr)
        return 1
    n = set_status(log, args.key, "promoted", fix=args.fix)
    print("%s: marked %d row(s) for %s promoted" % (log, n, args.key))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="mistakes.py", description=__doc__.splitlines()[0])
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                   help="occurrences that promote a key (default %d)" % DEFAULT_THRESHOLD)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="gate: grammar, owner coverage, promotion-due keys")
    c.add_argument("root", nargs="?", default=".")
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("report", help="human/agent view of counts and bands")
    r.add_argument("root", nargs="?", default=".")
    r.add_argument("--key")
    r.set_defaults(func=cmd_report)

    a = sub.add_parser("append", help="append one occurrence to an owner's log")
    a.add_argument("root", nargs="?", default=".")
    for flag in ("key", "context", "artifact", "fix"):
        a.add_argument("--" + flag, required=True)
    a.add_argument("--date")
    a.add_argument("--status", default="logged", choices=STATUSES)
    a.set_defaults(func=cmd_append)

    m = sub.add_parser("promote", help="mark every row for a key promoted (closes the loop)")
    m.add_argument("root", nargs="?", default=".")
    m.add_argument("--key", required=True)
    m.add_argument("--fix", help="replacement fix text, e.g. the gate path")
    m.set_defaults(func=cmd_promote)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (GrammarError, EnumerationError) as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
