#!/usr/bin/env python3
"""learn — the capture bar and the staleness pass over a durable record.

Two entry points over one record parser, because they are the same predicates applied at
two moments. `check` decides whether a candidate is worth remembering at all. `verify`
decides whether a record that already exists is still true, and at which rung of the
confidence ladder.

The engine adds **no store**. The memory tiers already exist and are described in
`.claude/docs/odin-memory-standards.md`; what this adds to a record in one of them is two
fields — a confidence tier, and a last-verified field whose value names the *command*
that verified it. A date says someone looked. A command says what would have to be re-run
to look again.

Nothing here writes into a memory tier, opens a file for append, or asks a human
anything. Stdout is data, stderr is diagnostics. Every path is taken from an argument;
nothing is inferred from the working directory.

**On refusing a credential: the matched value is never printed.** Not in the refusal, not
in a verbose mode, not in a diagnostic. A refusal that echoes the secret has published it
to every log the caller writes, which is strictly worse than the record it prevented. The
caller is told the *key name* or the *pattern name*, which is what they need in order to
remove it, and nothing more.

Usage:
  capture_bar.py check  --candidate FILE [--root DIR] [--corpus DIR]
                        [--duplicate-threshold F] [--derivable-threshold F]
  capture_bar.py verify --record FILE [--run] [--cwd DIR] [--today YYYY-MM-DD]
                        [--max-age-days N]
  capture_bar.py tiers

Exit:
  0 accepted, or a completed pass that held the tier
  1 malformed record
  2 usage error
  3 refused: credential material
  4 refused: personal data
  5 refused: task chatter
  6 refused: duplicate of an existing record
  7 refused: derivable from the repository
  8 the pass demoted the record one rung
  9 the pass retired the record
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------- exit codes

EXIT_ACCEPT = 0
EXIT_MALFORMED = 1
EXIT_USAGE = 2
EXIT_CREDENTIAL = 3
EXIT_PERSONAL = 4
EXIT_CHATTER = 5
EXIT_DUPLICATE = 6
EXIT_DERIVABLE = 7
EXIT_DEMOTED = 8
EXIT_RETIRED = 9

#: The order the classes are evaluated in: highest harm first. Once secret material is
#: present, nothing else about the record matters — it is refused before any check that
#: would need to read more of it.
CLASS_ORDER = ("credential", "personal", "chatter", "duplicate", "derivable")

CLASS_EXIT = {
    "credential": EXIT_CREDENTIAL,
    "personal": EXIT_PERSONAL,
    "chatter": EXIT_CHATTER,
    "duplicate": EXIT_DUPLICATE,
    "derivable": EXIT_DERIVABLE,
}

# ---------------------------------------------------------------- the ladder

#: Five rungs, floor first. Every rung states the evidence that promotes a record into it
#: and the trigger that demotes it out — a ladder where every rung is a feeling is a
#: vocabulary, not a mechanism.
TIERS = ("asserted", "observed", "reproduced", "gated", "enforced")

#: The rungs whose evidence *is* a command. Below these, a record may carry one; at these
#: and above, a record without one is malformed rather than merely unverified.
COMMAND_REQUIRED = ("reproduced", "gated", "enforced")

LADDER = (
    {
        "tier": "asserted",
        "promoted_by": "somebody stated it and the source is named",
        "demoted_by": "nothing below this rung — a failing pass here retires the record",
        "requires_command": False,
    },
    {
        "tier": "observed",
        "promoted_by": "an artifact exists — a log line, a command's output, a transcript",
        "demoted_by": "the artifact can no longer be resolved",
        "requires_command": False,
    },
    {
        "tier": "reproduced",
        "promoted_by": "a named command re-runs and produces the same result twice, independently",
        "demoted_by": "the command no longer produces that result",
        "requires_command": True,
    },
    {
        "tier": "gated",
        "promoted_by": "a check in the repository FAILS when the fact stops being true, proved by mutating the fact",
        "demoted_by": "the check is removed, or mutation shows it cannot fail",
        "requires_command": True,
    },
    {
        "tier": "enforced",
        "promoted_by": "that check runs unconditionally, so nothing can land while the fact is false",
        "demoted_by": "the check leaves the always-run path and becomes optional",
        "requires_command": True,
    },
)

#: Exactly one per run over a candidate or a record.
OUTCOMES = ("record", "merge", "promote", "refresh", "demote", "retire")

# ---------------------------------------------------------------- detectors

#: Matched against the record's KEYS, normalised. Never against a value — the word
#: "password" inside a sentence about passwords is prose, not a password.
CREDENTIAL_KEYS = (
    "password", "passwd", "passphrase", "secret", "token", "api_key", "apikey",
    "access_key", "secret_key", "private_key", "credential", "authorization",
    "auth_token", "session_key", "client_secret", "refresh_token", "bearer", "ssh_key",
)

#: Matched against VALUES, by shape. The pattern's NAME is what gets reported; the match
#: itself is never touched again after the boolean.
CREDENTIAL_VALUE_PATTERNS = (
    ("aws-access-key-id", re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("vendor-api-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer-header", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("credentials-in-url", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
    ("json-web-token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
)

PERSONAL_PATTERNS = (
    ("email-address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("national-id", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("phone-number", re.compile(r"(?:\+\d{1,3}[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b")),
    (
        "postal-address",
        re.compile(
            r"\b\d{1,5}\s+[A-Z][a-z]+\s+"
            r"(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Boulevard|Blvd|Drive|Dr)\b"
        ),
    ),
)

#: Session deixis: phrases whose referent is the conversation that produced the record.
#: Keyed on the phrase, never on the noun — `session` is harness vocabulary and a record
#: about how a session behaves is durable knowledge.
CHATTER_MARKERS = (
    "this session", "this conversation", "this turn", "this thread", "this run",
    "earlier in this", "the previous message", "as discussed above", "as noted above",
    "just ran", "just now", "right now", "a moment ago", "currently working on",
    "i'm about to", "i am about to", "we just", "let me", "the last command",
    "next i will", "next we will",
)

STOPWORDS = frozenset(
    """
    the and for that with this from into over under but not are was were has have had had
    its their there here when what which while who whom whose than then them they you your
    our out all any can could should would will shall may might must been being does did
    doing done such only just also more most other another same each every both few many
    some own too very how why where because about after before between during against
    """.split()
)

_TOKEN = re.compile(r"[a-z0-9]+")

#: Below this many distinctive tokens a record is too short for a similarity judgement to
#: mean anything, and both corpus checks decline rather than guess.
MIN_TOKENS_FOR_SIMILARITY = 4

DEFAULT_DUPLICATE_THRESHOLD = 0.70
DEFAULT_DERIVABLE_THRESHOLD = 0.85
DEFAULT_MAX_AGE_DAYS = 180

#: A line longer than this is a minified asset or a data blob, not prose somebody could
#: have restated.
MAX_LINE_FOR_DERIVABLE = 600

SKIP_DIRS = frozenset((".git", "node_modules", "__pycache__", ".venv", "dist", "build"))


def tokens(text: str) -> set:
    return {t for t in _TOKEN.findall(text.lower()) if len(t) >= 3 and t not in STOPWORDS}


def jaccard(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def containment(needle: set, haystack: set) -> float:
    """How much of `needle` a single line already carries. Asymmetric on purpose: a long
    line that contains the whole record IS a restatement of it, and Jaccard would score
    that low for the length mismatch alone."""
    if not needle:
        return 0.0
    return len(needle & haystack) / len(needle)


def normalise_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower())


# ---------------------------------------------------------------- the five classes


def find_credential(record: dict):
    """Return a redacted finding, or None. The matched value never leaves this function."""
    for key in record:
        flat = normalise_key(key)
        for marker in CREDENTIAL_KEYS:
            if marker in flat:
                return "field %r is a credential-bearing key name" % str(key)
    for key, value in record.items():
        if not isinstance(value, str):
            continue
        for name, pattern in CREDENTIAL_VALUE_PATTERNS:
            if pattern.search(value):
                # The pattern's name, the field's name. Never the match.
                return "field %r holds a value shaped like %s" % (str(key), name)
    return None


def find_personal(record: dict):
    for key, value in record.items():
        if not isinstance(value, str):
            continue
        for name, pattern in PERSONAL_PATTERNS:
            if pattern.search(value):
                return "field %r holds %s" % (str(key), name)
    return None


def find_chatter(record: dict):
    haystack = " ".join(v for v in record.values() if isinstance(v, str)).lower()
    for marker in CHATTER_MARKERS:
        if marker in haystack:
            return "task chatter: %r is true only inside the conversation that produced it" % marker
    return None


def corpus_files(corpus: str):
    for entry in sorted(os.listdir(corpus)):
        path = os.path.join(corpus, entry)
        if os.path.isfile(path):
            yield path


def find_duplicate(subject: set, corpus: str, threshold: float):
    if len(subject) < MIN_TOKENS_FOR_SIMILARITY:
        return None
    for path in corpus_files(corpus):
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        score = jaccard(subject, tokens(text))
        if score >= threshold:
            return "duplicate of %s (similarity %.2f)" % (os.path.basename(path), score)
    return None


def tracked_files(root: str):
    """Every tracked file under `root`. `git ls-files` when the tree is a repository,
    a walk otherwise — a fixture tree is not a repository and must still be readable."""
    if os.path.isdir(os.path.join(root, ".git")):
        try:
            listing = subprocess.run(
                ["git", "-C", root, "ls-files", "-z"],
                capture_output=True, text=True, check=True,
            ).stdout
            for rel in listing.split("\0"):
                if rel:
                    yield rel, os.path.join(root, rel)
            return
        except (OSError, subprocess.CalledProcessError):
            pass
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, root), full


def find_derivable(subject: set, root: str, threshold: float):
    """A restatement of one line the repository already carries.

    Deliberately narrow. This catches a record that repeats a line; it does NOT catch a
    fact assembled by reading three files, and it is not meant to — that is a finding,
    not a restatement, and a check that refused it would refuse every genuine finding
    about the harness along with it.
    """
    if len(subject) < MIN_TOKENS_FOR_SIMILARITY:
        return None
    for rel, full in tracked_files(root):
        try:
            handle = open(full, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for lineno, line in enumerate(handle, 1):
                if len(line) > MAX_LINE_FOR_DERIVABLE:
                    continue
                score = containment(subject, tokens(line))
                if score >= threshold:
                    return "restates %s:%d (%.0f%% of its terms)" % (rel, lineno, score * 100)
    return None


# ---------------------------------------------------------------- check


def run_check(args) -> int:
    try:
        raw = open(args.candidate, encoding="utf-8").read()
    except OSError as exc:
        print("usage: cannot read --candidate %s (%s)" % (args.candidate, exc.strerror), file=sys.stderr)
        return EXIT_USAGE
    try:
        record = json.loads(raw)
    except ValueError as exc:
        print("malformed: --candidate is not JSON (%s)" % exc, file=sys.stderr)
        return EXIT_MALFORMED
    if not isinstance(record, dict):
        print("malformed: --candidate must be a JSON object", file=sys.stderr)
        return EXIT_MALFORMED
    for field in ("title", "body"):
        if not str(record.get(field, "")).strip():
            print("malformed: --candidate is missing a non-empty %s" % field, file=sys.stderr)
            return EXIT_MALFORMED

    subject = tokens("%s %s" % (record.get("title", ""), record.get("body", "")))
    classes = {}
    finding = None
    refused = None

    for name in CLASS_ORDER:
        if name == "credential":
            classes[name] = "evaluated"
            finding = find_credential(record)
        elif name == "personal":
            classes[name] = "evaluated"
            finding = find_personal(record)
        elif name == "chatter":
            classes[name] = "evaluated"
            finding = find_chatter(record)
        elif name == "duplicate":
            if not args.corpus:
                classes[name] = "skipped"
                print(
                    "note: the duplicate class was not evaluated — no --corpus given, so an "
                    "existing record covering this one would not be seen",
                    file=sys.stderr,
                )
                continue
            classes[name] = "evaluated"
            finding = find_duplicate(subject, args.corpus, args.duplicate_threshold)
        else:
            if not args.root:
                classes[name] = "skipped"
                print(
                    "note: the derivable class was not evaluated — no --root given, so a "
                    "restatement of a tracked line would not be seen",
                    file=sys.stderr,
                )
                continue
            classes[name] = "evaluated"
            finding = find_derivable(subject, args.root, args.derivable_threshold)
        if finding:
            refused = name
            break

    if refused:
        payload = {
            "outcome": "merge" if refused == "duplicate" else None,
            "refused": refused,
            "reason": finding,
            "classes": classes,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("REFUSED (%s): %s" % (refused, finding), file=sys.stderr)
        return CLASS_EXIT[refused]

    print(json.dumps({"outcome": "record", "refused": None, "classes": classes},
                     indent=2, sort_keys=True))
    return EXIT_ACCEPT


# ---------------------------------------------------------------- verify


def parse_day(value: str):
    try:
        return datetime.date(*(int(p) for p in value.split("-")))
    except (TypeError, ValueError):
        return None


def index_marker(tier: str, day) -> str:
    """What the always-loaded memory index carries: the tier and the date, never the
    command. The index has a 300-character-per-line ceiling because it is read whole into
    every session in its scope; the record it links to has none."""
    return "· %s %s" % (tier, day) if day else "· %s" % tier


def run_verify(args) -> int:
    try:
        raw = open(args.record, encoding="utf-8").read()
    except OSError as exc:
        print("usage: cannot read --record %s (%s)" % (args.record, exc.strerror), file=sys.stderr)
        return EXIT_USAGE
    try:
        record = json.loads(raw)
    except ValueError as exc:
        print("malformed: --record is not JSON (%s)" % exc, file=sys.stderr)
        return EXIT_MALFORMED
    if not isinstance(record, dict):
        print("malformed: --record must be a JSON object", file=sys.stderr)
        return EXIT_MALFORMED

    tier = str(record.get("confidence", ""))
    if tier not in TIERS:
        print("malformed: confidence %r is not one of %s" % (tier, ", ".join(TIERS)), file=sys.stderr)
        return EXIT_MALFORMED

    command = record.get("verified_by") or None
    stamp = record.get("verified_on") or None

    if tier in COMMAND_REQUIRED:
        if not command:
            print("malformed: tier %r requires verified_by — the command that re-checks it" % tier,
                  file=sys.stderr)
            return EXIT_MALFORMED
        if not stamp:
            print("malformed: tier %r requires verified_on" % tier, file=sys.stderr)
            return EXIT_MALFORMED

    day = parse_day(stamp) if stamp else None
    if stamp and day is None:
        print("malformed: verified_on %r is not an ISO date (YYYY-MM-DD)" % stamp, file=sys.stderr)
        return EXIT_MALFORMED

    today = parse_day(args.today) if args.today else datetime.date.today()
    if today is None:
        print("usage: --today %r is not an ISO date" % args.today, file=sys.stderr)
        return EXIT_USAGE

    age_days = (today - day).days if day else None
    stale = age_days is not None and age_days > args.max_age_days

    payload = {
        "confidence": tier,
        "verified_by": command,
        "verified_on": stamp,
        "age_days": age_days,
        "stale": stale,
        "outcome": None,
        "reason": None,
        "would_run": command,
        "index_marker": index_marker(tier, stamp),
    }

    if not command:
        print(
            "note: tier %r has no verifying command — nothing to re-run. Promote it by "
            "naming the command that would re-check it." % tier,
            file=sys.stderr,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_ACCEPT

    if not args.run:
        print(
            "note: reading a record never executes the command inside it — pass --run to "
            "execute %r and decide the rung" % command,
            file=sys.stderr,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_ACCEPT

    completed = subprocess.run(
        command, shell=True, cwd=args.cwd or None, capture_output=True, text=True
    )
    code = completed.returncode

    if code == 0:
        payload["outcome"] = "refresh"
        payload["verified_on"] = today.isoformat()
        payload["index_marker"] = index_marker(tier, today.isoformat())
        payload["reason"] = "the verifying command still passes"
        if stale:
            print(
                "note: %d days since the last pass exceeds --max-age-days %d — the record is "
                "flagged stale, and the command, not the date, decided the rung"
                % (age_days, args.max_age_days),
                file=sys.stderr,
            )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_ACCEPT

    rung = TIERS.index(tier)
    if code == 127:
        # The fact may still be true. What is gone is the ability to re-check it, so the
        # record falls to the highest rung that needs no command.
        new_tier = "observed" if rung > TIERS.index("observed") else TIERS[max(rung - 1, 0)]
        reason = "unresolvable"
        detail = "the verifying command could not be resolved (exit 127)"
    else:
        new_tier = TIERS[rung - 1] if rung > 0 else None
        reason = "failed"
        detail = "the verifying command exited %d" % code

    if new_tier is None:
        payload["outcome"] = "retire"
        payload["reason"] = "the floor rung's only evidence no longer holds: %s" % detail
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("RETIRE: %s" % detail, file=sys.stderr)
        return EXIT_RETIRED

    payload["outcome"] = "demote"
    payload["confidence"] = new_tier
    payload["reason"] = reason
    payload["index_marker"] = index_marker(new_tier, stamp)
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("DEMOTE %s -> %s: %s" % (tier, new_tier, detail), file=sys.stderr)
    return EXIT_DEMOTED


def run_tiers(args) -> int:
    print(json.dumps({"tiers": list(LADDER), "outcomes": list(OUTCOMES)},
                     indent=2, sort_keys=True))
    return EXIT_ACCEPT


# ---------------------------------------------------------------- cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capture_bar.py", add_help=True)
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="apply the capture bar to a candidate record")
    check.add_argument("--candidate", required=True)
    check.add_argument("--root", default=None, help="repository root for the derivable class")
    check.add_argument("--corpus", default=None, help="directory of existing records")
    check.add_argument("--duplicate-threshold", type=float, default=DEFAULT_DUPLICATE_THRESHOLD)
    check.add_argument("--derivable-threshold", type=float, default=DEFAULT_DERIVABLE_THRESHOLD)
    check.set_defaults(handler=run_check)

    verify = sub.add_parser("verify", help="re-verify, demote or retire an existing record")
    verify.add_argument("--record", required=True)
    verify.add_argument("--run", action="store_true", help="execute the verifying command")
    verify.add_argument("--cwd", default=None)
    verify.add_argument("--today", default=None)
    verify.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    verify.set_defaults(handler=run_verify)

    tiers = sub.add_parser("tiers", help="print the confidence ladder and the six outcomes")
    tiers.set_defaults(handler=run_tiers)
    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return EXIT_USAGE
    if not getattr(args, "handler", None):
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
