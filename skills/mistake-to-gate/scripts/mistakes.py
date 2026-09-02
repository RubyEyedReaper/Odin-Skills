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
# `promoted-rule` closes a CROSS-OWNER promotion, and is deliberately distinct from `promoted`.
# A per-owner promotion demands both halves — a check in that owner's gate list and rule text. A
# cross-owner one demands only the rule half, because a check is local (one gate list, one tree)
# while a rule is not, and demanding a check from a count spread across owners points its owner at
# the wrong gate list (harness:RM-0182, DEC-0029).
STATUSES = ("logged", "guarded", "promoted", "promoted-rule", "wontfix")
DEFAULT_THRESHOLD = 4

#: Root ledgers that record incidents WITHOUT participating in the recurrence count (DEC-0092).
#:
#: A second file able to hold a failure-mode key makes every count above an undercount, silently:
#: `counts()` reads one file per owner, so a key split two-and-two across two ledgers stands at two
#: on the ladder while four occurrences sit on disk, and both files look healthy. Reproduced before
#: this declaration existed — `mistakes-check.sh` exited 0 saying "mistake logs clean" over exactly
#: that fixture.
#:
#: The resolution is not a wider sum but a narrower grammar: these ledgers carry block entries, no
#: key, and therefore no arithmetic. `check_block_ledgers` enforces both halves — that no row in one
#: parses as a keyed occurrence, and that every entry carries the two fields that make a caveat a
#: caveat rather than a war story (the condition under which it recurs, and the safeguard that
#: closes it).
#:
#: ADDING A LEDGER IS A DECLARATION HERE, NEVER A SECOND IMPLEMENTATION. A sibling ledger recording
#: a different kind of record adds one entry to this dict; the two passes below are already its gate.
BLOCK_LEDGERS = {
    "CAVEAT.md": {
        "entry_prefix": "C",
        "required": ("Date", "What happened", "Why it happened", "Potential impact",
                     "Recurs when", "Safeguard"),
    },
}

#: `## C-0001 — title`. The id prefix is per-ledger, so the pattern is built per declaration.
_ENTRY_RE_TEMPLATE = r"^##\s+(%s-\d{4})\b"
#: `- **Recurs when:** <value>` — the label is captured so a missing field is named, not counted.
FIELD_RE = re.compile(r"^\s*[-*]\s*\*\*([^:*]+):?\*\*\s*(.*)$")

#: How this script is invoked, for printing runnable commands in its own findings.
_SELF = ".claude/skills/mistake-to-gate/scripts/mistakes.py"
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


# --- block-entry ledgers ---------------------------------------------------------------------

def foreign_keyed_rows(text, path=""):
    """Findings for lines in a NON-counting ledger that parse as a keyed occurrence row.

    Deliberately NOT `scan_log`. That parser treats the first pipe line in a file as the column
    header and skips it, so a lone keyed row pasted into a caveat ledger would be swallowed by the
    very reader whose blindness is the defect — the split would be invisible to the check written
    to find it. Every pipe line is read here, and the header line is excluded by the grammar rather
    than by position: its third cell is the word `key`, which is not `<class>/<slug>`.

    The predicate is the real one — `key_errors`, the same function `_row_errors` uses — so a change
    to the key grammar moves this pass with it instead of leaving a second copy behind.
    """
    out = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.lstrip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) != 8 or _is_separator(cells):
            continue
        if key_errors(cells[2]):
            continue
        out.append(
            "%s:%d: carries a failure-mode key %r — a keyed occurrence outside %s is counted by "
            "nothing, so the promotion ladder stops firing while both files look healthy "
            "(DEC-0092). Append the occurrence with `%s append --key %s`, and keep this ledger's "
            "block entries prose."
            % (path or "<ledger>", lineno, cells[2], LOG_NAME, _SELF, cells[2]))
    return out


def block_entries(text, prefix):
    """`[(entry_id, start_line, {label: value})]` for every `## <prefix>-NNNN` section."""
    head = re.compile(_ENTRY_RE_TEMPLATE % re.escape(prefix))
    entries = []
    fenced = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = head.match(line)
        if match:
            entries.append((match.group(1), lineno, {}))
            continue
        if not entries:
            continue
        field = FIELD_RE.match(line)
        if field:
            entries[-1][2][field.group(1).strip()] = field.group(2).strip()
    return entries


def block_entry_errors(text, path, spec):
    """Findings for entries missing a required field, or carrying one with an empty value.

    An empty value and an absent label are reported the same way on purpose: both leave the
    obligation unmet, and a ledger that accepted `**Safeguard:**` with nothing after it would let
    the conversion step be skipped by pressing return.
    """
    out = []
    for entry_id, lineno, fields in block_entries(text, spec["entry_prefix"]):
        for label in spec["required"]:
            if fields.get(label):
                continue
            out.append(
                "%s:%d: entry %s has no **%s:** value — %s"
                % (path, lineno, entry_id, label, _WHY_FIELD.get(label, "the entry shape requires it")))
    return out


#: Why a field is required, printed with the finding. A refusal that only names a missing label
#: teaches the author to paste the label; naming the obligation is what makes the next entry right.
_WHY_FIELD = {
    "Recurs when": "a caveat with no recurrence condition is a war story, not a record something "
                   "can be keyed on",
    "Safeguard": "recording without converting is the failure this ledger exists to prevent; name "
                 "the hook, check, rule or stated guidance that now refuses it",
}


def check_block_ledgers(owner_path):
    """Both passes over every declared non-counting ledger this owner actually has."""
    out = []
    for name, spec in sorted(BLOCK_LEDGERS.items()):
        ledger = Path(owner_path) / name
        # Absence is silent, and this is NOT the MISTAKES.md rule one screen up. A missing mistake
        # log hides a count, so opt-in-by-presence there is a check that disables itself; a caveat
        # ledger participates in no count, so its absence hides nothing and demanding one from every
        # project would fail owners who have recorded no caveats.
        if not ledger.is_file():
            continue
        text = ledger.read_text()
        out.extend(foreign_keyed_rows(text, str(ledger)))
        out.extend(block_entry_errors(text, str(ledger), spec))
    return out


# --- counting --------------------------------------------------------------------------------

def counts(rows):
    """Occurrences per key. `wontfix` rows are excluded — they are decisions, not occurrences."""
    out = {}
    for r in rows:
        if r.status == "wontfix":
            continue
        out[r.key] = out.get(r.key, 0) + 1
    return out


PROMOTED_STATUSES = ("promoted", "promoted-rule")


def closure(rows, key):
    """How a key's own rows stand: None (no live rows), or the word they justify.

    THE ONE implementation of "has promotion happened", shared by `band` and `due`. They disagreed
    for as long as there were two of them (harness:RM-0362): `due` read the rows and `band` read
    only the count, so `report` printed `promoted` over rows that were all `logged` while `check`
    on the identical file exited 1 saying promotion was due.

    `wontfix` rows are excluded, exactly as `counts` excludes them — a key whose only unpromoted
    row is a wontfix would otherwise never read closed.
    """
    live = [r for r in rows if r.key == key and r.status != "wontfix"]
    if not live:
        return None
    if not all(r.status in PROMOTED_STATUSES for r in live):
        return "promotion due"
    # `promoted-rule` closes a CROSS-OWNER promotion and carries a different obligation from
    # `promoted`. Collapsing them into one displayed word is this same defect one level down.
    if all(r.status == "promoted-rule" for r in live):
        return "promoted-rule"
    return "promoted"


def band(count, threshold=DEFAULT_THRESHOLD, rows=None, key=None):
    """The required response for a count — SR-3's ladder, in one place.

    The threshold decides whether promotion is OWED; only the rows decide whether it HAPPENED, and
    the two must never print the same word. Called without `rows`, the answer at or above the
    threshold is the owed one: an unknown closure is not evidence of closure, and a band that
    assumes it is how `report` said the work was finished over four `logged` rows.
    """
    if count < 2:
        return "logged"
    if count < threshold:
        return "attention"
    if rows is None or key is None:
        return "promotion due"
    return closure(rows, key) or "promotion due"


def due(rows, threshold=DEFAULT_THRESHOLD):
    """Keys that have reached the promotion threshold and are not yet fully promoted."""
    tally = counts(rows)
    return sorted(key for key, n in tally.items()
                  if n >= threshold and closure(rows, key) == "promotion due")


def cross_owner_due(per_owner_rows, threshold=DEFAULT_THRESHOLD, cross_threshold=None):
    """Findings for a key that reaches the threshold ACROSS owners without reaching it in any one.

    The gap this closes: `MISTAKES.md` rows are owned, and the threshold is applied per owner, so one
    failure mode recurring across the harness and three projects is four counts of one, below
    threshold forever. Measured, not supposed — `ci-gate/fixture-reads-ambient-state` stood at four
    in the harness log and one in a project's, and had it been 2+2 it would have been invisible while
    being the most common shape in the repository (#387).

    Three boundaries, each of which was a way to get this wrong:

    * **Only the RULE half is demanded.** A check runs in one gate list against one tree; a rule does
      not. Demanding a check here would point an owner at a gate list that cannot hold it, which is
      `mistake-to-gate` §8's boundary error reached from a new direction (DEC-0029).
    * **Distinct keys never sum.** Two different failure modes at two occurrences each are not one
      failure mode at four. A gate that fired on unrelated work would be disabled, taking its true
      positives with it.
    * **A key already at threshold within a single owner is left alone.** That owner's finding
      already demands both halves; adding a rule-only finding beside it would let the weaker demand
      look like the whole obligation.
    """
    # TWO THRESHOLDS, READ FOR TWO DIFFERENT PURPOSES — and this is the whole reason the
    # flag needed a decision rather than a substitution. `cross_threshold` gates the TOTAL.
    # `threshold` keeps gating the SUPPRESSION rule below, because "is this already some
    # single owner's business?" is a question about the per-owner rung and nothing else.
    # Substituting one number for both makes a lower cross-threshold either double-report a
    # key or suppress both findings.
    if cross_threshold is None:
        cross_threshold = threshold

    totals, holders = {}, {}
    for owner, rows in per_owner_rows.items():
        for key, n in counts(rows).items():
            totals[key] = totals.get(key, 0) + n
            holders.setdefault(key, []).append((owner, n))

    out = []
    for key in sorted(totals):
        if totals[key] < cross_threshold:
            continue
        # Already the per-owner check's business.
        if any(n >= threshold for _, n in holders[key]):
            continue
        # Closed: every non-wontfix row carrying the key is promoted, by either route.
        if all(r.status in ("promoted", "promoted-rule")
               for rows in per_owner_rows.values()
               for r in rows if r.key == key and r.status != "wontfix"):
            continue
        where = ", ".join("%s (%d)" % (o, n) for o, n in sorted(holders[key]))
        out.append(
            "cross-owner promotion due — %r has %d recorded occurrences across %d owners "
            "(cross-threshold %d), and no single owner reaches the per-owner threshold "
            "of %d: %s. "
            "Only the RULE half is due: land rule text in the harness's .claude/rules/ at a "
            "paths:-scoped tier via rules-distill, then mark every row for the key promoted-rule. "
            "Do NOT land a check for this — a check belongs to one owner's gate list, and this "
            "count belongs to none of them.%s"
            % (key, totals[key], len(holders[key]), cross_threshold, threshold, where,
               _closing_commands(key, holders[key])))
    return out


def _closing_commands(key, holders):
    """The exact commands that close this finding, one per owner root.

    Printed because closure spans several roots: a reader who is told to "mark every row"
    still has to work out that it means N invocations in N directories, and a closing step
    somebody has to reconstruct is one they get wrong or skip.
    """
    lines = ["\n  Close it with, one per owner:"]
    for owner, _ in sorted(holders):
        root = "." if owner in ("", ".", LOG_NAME) else owner
        lines.append(
            "    python3 %s promote %s --key %s --status promoted-rule "
            "--fix 'rule: <path to the rule text>'" % (_SELF, root, key))
    return "\n".join(lines)


def is_post_promotion(rows, key):
    """True when a key's live rows are a MIX: some already `promoted`/`promoted-rule`, some not.

    A key that has never been promoted is all-unpromoted; a key that is fully closed is
    all-promoted and `closure()` already reports it as such, so it never reaches `due()`. A mix
    can only happen when promotion landed once and a later occurrence was appended after it —
    `append_row` never rewrites an existing row, so the promoted rows stay promoted while the new
    one starts `logged`. That is `mistake-to-gate` section 11's case: the rule already exists and
    this occurrence is evidence the check meant to catch it missed, not a fresh promotion demand.
    """
    live = [r for r in rows if r.key == key and r.status != "wontfix"]
    return any(r.status in PROMOTED_STATUSES for r in live)


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
        # Re-escape on write. `_split_row` turns `\|` into a literal pipe, so emitting the cells raw
        # gives the row one column per escaped pipe it contained and MISTAKES.md stops parsing —
        # caused by the command the promotion procedure mandates, on the log that command maintains,
        # and silent at write time (M-0115). Not `_escape`, which also collapses whitespace: this
        # writer is rewriting a status, and a rewrite that reformats cells it was not asked to touch
        # is a second, quieter corruption of the same rows.
        cells = [c.replace("|", "\\|") for c in cells]
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
    per_owner_rows = {}
    for owner in included:
        # Run BEFORE the mistake log is loaded, and independently of whether it loads. A
        # keyed row sitting in a sibling ledger is an occurrence nothing counts, and an owner
        # whose MISTAKES.md is missing is exactly the owner most likely to have put it there.
        findings.extend(check_block_ledgers(owner))
        rows, errors = _load(owner)
        findings.extend(errors)
        if rows is None:
            continue
        per_owner_rows[owner] = rows
        for key in due(rows, args.threshold):
            n = counts(rows)[key]
            if is_post_promotion(rows, key):
                findings.append(
                    "%s/%s: post-promotion occurrence — %r already has promoted row(s), and a "
                    "later row landed after them (now %d recorded occurrences, threshold %d). "
                    "The rule already exists; this is a new incident about the CHECK that missed "
                    "it (mistake-to-gate section 11), not a repeat promotion demand. Re-key the "
                    "row if it is actually a different failure mode, or file a finding against "
                    "the gate that should have caught it."
                    % (owner, LOG_NAME, key, n, args.threshold))
            else:
                findings.append(
                    "%s/%s: promotion due — %r has %d recorded occurrences (threshold %d). "
                    "Run mistake-to-gate: land a mechanical check in this owner's gate list, rule "
                    "text in its CLAUDE.md, then mark every row for the key promoted."
                    % (owner, LOG_NAME, key, n, args.threshold))

    findings.extend(cross_owner_due(per_owner_rows, args.threshold,
                                    getattr(args, "cross_threshold", None)))

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
    cross = getattr(args, "cross_threshold", None) or args.threshold

    # Every owner's rows are collected BEFORE anything is printed. The cross-owner total
    # does not exist while the loop is still walking owners one at a time, which is why the
    # unfiltered report could not name it: the number was not computable at print time.
    #
    # This is the visibility half of harness:RM-0182. `report --key K` already showed a
    # per-owner section, so a reader who ALREADY suspected a key could see both counts —
    # and the ladder exists precisely because nobody suspects the key. A count that is only
    # visible to someone who already knows what to look for is not a signal.
    all_rows = {}
    for owner in included:
        rows, _ = _load(owner)
        if rows is not None:
            all_rows[owner] = rows
    totals = {}
    for owner, rows in all_rows.items():
        for key, n in counts(rows).items():
            totals.setdefault(key, []).append((owner, n))

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
            # The rows travel with the count, or the band is a function of the threshold alone —
            # which is how this line printed `promoted` over rows that were all `logged` while
            # `check` on the same file exited 1 saying promotion was due (harness:RM-0362).
            print("  %-44s %d  %s" % (key, n, band(n, args.threshold, rows, key)))
            holders = totals.get(key, [])
            if len(holders) > 1:
                total = sum(count for _, count in holders)
                elsewhere = ", ".join(
                    "%s (%d)" % (o, c) for o, c in sorted(holders) if o != owner)
                line = "      also in %s — total %d across %d owners" % (
                    elsewhere, total, len(holders))
                # The cross rung's verdict travels with the key rather than only at the
                # bottom of the run, and `band()` stays the single source of what a count
                # demands — a second band computed inline is how one gate starts giving two
                # answers.
                if total >= cross and not any(c >= args.threshold for _, c in holders):
                    # Every owner's rows for this key, so the cross rung reads its own closure
                    # rather than inferring it from the total — the same correction as the
                    # per-owner line above, one level up (harness:RM-0362).
                    cross_rows = [r for rs in all_rows.values() for r in rs]
                    line += " — %s on the cross-owner rung (rule half only)" % band(
                        total, cross, cross_rows, key)
                print(line)
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
    """Close a promotion by marking every row for the key.

    `--status` exists because the cross-owner rung closes with `promoted-rule`, not
    `promoted`, and this command hardcoded the latter. The finding printed by
    `cross_owner_due` told the reader to "mark every row for the key promoted-rule" while
    no command could write it, so the only route was hand-editing markdown rows — the
    unclearable gate ADR-0057 names as the thing that gets a gate deleted.

    The default stays `promoted`, so every existing invocation keeps its meaning.
    """
    log = Path(args.root) / LOG_NAME
    if not log.is_file():
        print("FAIL: %s does not exist" % log, file=sys.stderr)
        return 1
    n = set_status(log, args.key, args.status, fix=args.fix)
    print("%s: marked %d row(s) for %s %s" % (log, n, args.key, args.status))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="mistakes.py", description=__doc__.splitlines()[0])
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                   help="occurrences that promote a key within ONE owner "
                        "(default %d)" % DEFAULT_THRESHOLD)
    # Default None, not DEFAULT_THRESHOLD. A flag's absence and its zero value are
    # different things: absent means "follow --threshold", which reproduces today's verdict
    # exactly, while a hardcoded 4 here silently decouples the two the day --threshold is
    # retuned. The separability is the point — the two rungs answer different questions and
    # a repository may want them at different numbers — but the default must not move.
    p.add_argument("--cross-threshold", type=int, default=None,
                   help="occurrences that promote a key ACROSS owners, demanding the rule "
                        "half only (default: follow --threshold)")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="gate: grammar, owner coverage, promotion-due keys")
    c.add_argument("root", nargs="?", default=".")
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("report", help="human/agent view of counts and bands")
    r.add_argument("root", nargs="?", default=".")
    r.add_argument("--key")
    # No --cross-threshold here. It is a top-level flag, like --threshold, and defining it
    # on a subparser as well would silently overwrite a top-level value with the
    # subparser's default — argparse applies subparser defaults after the top-level parse.
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
    m.add_argument("--status", default="promoted", choices=("promoted", "promoted-rule"),
                   help="promoted closes a per-owner promotion (a check AND rule text); "
                        "promoted-rule closes a cross-owner one (rule text only)")
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
