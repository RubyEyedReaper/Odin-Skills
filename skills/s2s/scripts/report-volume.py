#!/usr/bin/env python3
"""Re-derive the narration figures the s2s skill quotes, instead of trusting them.

Every number in SKILL.md's report-contract section came from this script. A threshold nobody can
re-measure is a threshold nobody can revise, and this repository has a measured habit of carrying
stated counts that went stale the day after they were written.

WHAT IT MEASURES. For each session transcript, the final turn's assistant prose — the same
`turn_prose()` boundary the Stop hook uses, so the figures describe what the hook would have seen —
reduced to NARRATION: lines that are neither markdown furniture, nor a label line, nor inside a
fence. It reports the distribution and the fraction over each cap.

WHAT IT IS NOT. Not calibration. The delegated population is the defect this bound exists to notice,
so fitting the caps to it would enshrine the defect as the standard. The caps come from the
instruction `odin-relay.sh` already ships ("in four lines") plus headroom; this script measures the
GAP between that contract and current behaviour.

WHY IT IS NOT A MATRIX CASE. It reads the host's own transcript directory, which differs on every
machine — `ci-gate/fixture-reads-ambient-state` is a promoted failure key here. Nothing under
.claude/tests/ may call it. It is a tool a human or an agent runs deliberately, and it prints where
its numbers came from so a reader can tell one host's answer from another's.

Usage:
    python3 .claude/skills/s2s/scripts/report-volume.py [--projects-dir DIR] [--pattern GLOB]

Default corpus: ~/.claude/projects/*/  — every session on this host, grouped into sessions that ran
in a worktree (delegated) and the rest (coordinator), because that split is the one the bound is
about.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", "..", "scripts", "lib"))
sys.path.insert(0, LIB)

try:
    from voice_lint import FURNITURE, LABEL, strip_code_and_quotes, turn_prose
except ImportError:  # pragma: no cover - the honest failure, not a silent zero
    sys.stderr.write(
        "report-volume: cannot import the prose predicate from %s — nothing measured.\n"
        "The figures this script prints come from the same code the Stop hook runs; without it\n"
        "a number here would be a different measurement wearing the same name.\n" % LIB)
    raise SystemExit(2)

DEFAULT_MAX_LINES = 8
DEFAULT_MAX_WORDS = 120


def narration(prose):
    lines = words = 0
    for raw in strip_code_and_quotes(prose).splitlines():
        line = raw.strip()
        if not line or FURNITURE.match(line) or LABEL.match(line):
            continue
        lines += 1
        words += len(line.split())
    return lines, words


def percentile(values, q):
    if not values:
        return 0
    i = min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))
    return values[i]


def measure(paths):
    line_counts, word_counts = [], []
    for path in paths:
        prose = turn_prose(path)
        if not prose or not prose.strip():
            continue
        lines, words = narration(prose)
        line_counts.append(lines)
        word_counts.append(words)
    line_counts.sort()
    word_counts.sort()
    return line_counts, word_counts


def render(label, line_counts, word_counts, max_lines, max_words):
    n = len(line_counts)
    if not n:
        print("%-12s no final turns carrying prose" % label)
        return
    print("%-12s n=%d" % (label, n))
    print("  narration lines   median=%d  p75=%d  p90=%d  max=%d"
          % (percentile(line_counts, .5), percentile(line_counts, .75),
             percentile(line_counts, .90), line_counts[-1]))
    print("  narration words   median=%d  p75=%d  p90=%d  max=%d"
          % (percentile(word_counts, .5), percentile(word_counts, .75),
             percentile(word_counts, .90), word_counts[-1]))
    over_lines = sum(1 for v in line_counts if v > max_lines)
    over_words = sum(1 for v in word_counts if v > max_words)
    print("  over the %d-line cap   %d/%d (%d%%)" % (max_lines, over_lines, n, 100 * over_lines // n))
    print("  over the %d-word cap  %d/%d (%d%%)" % (max_words, over_words, n, 100 * over_words // n))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--projects-dir", default=os.path.expanduser("~/.claude/projects"),
                    help="directory holding one subdirectory of *.jsonl per project")
    # The two buckets must be COMPARABLE or the comparison says nothing. Without --include the
    # coordinator bucket collects every unrelated project on the host — measured once at 7247
    # transcripts against 260 delegated, which is a statement about the machine rather than about
    # this repository's two audiences.
    ap.add_argument("--include", default="Repos-odin",
                    help="case-insensitive substring a project dir must contain to be measured at "
                         "all; keeps the two buckets comparable")
    ap.add_argument("--pattern", default="-wt-",
                    help="'|'-separated substrings marking an included project dir as a DELEGATED "
                         "session's rather than a coordinator's")
    ap.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    ap.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS)
    args = ap.parse_args()

    if not os.path.isdir(args.projects_dir):
        sys.stderr.write("report-volume: %s is not a directory — nothing measured, and that is not "
                         "the same as zero.\n" % args.projects_dir)
        raise SystemExit(2)

    marks = [m.lower() for m in args.pattern.split("|") if m]
    include = args.include.lower()
    delegated, coordinator = [], []
    for d in sorted(glob.glob(os.path.join(args.projects_dir, "*"))):
        if not os.path.isdir(d):
            continue
        base = os.path.basename(d).lower()
        if include and include not in base:
            continue
        bucket = delegated if any(m in base for m in marks) else coordinator
        bucket.extend(glob.glob(os.path.join(d, "*.jsonl")))

    print("corpus: %s" % args.projects_dir)
    print("included: project dirs containing %r" % args.include)
    print("delegated marked by: %s" % args.pattern)
    print("caps under test: %d narration lines / %d narration words\n" % (args.max_lines, args.max_words))

    for label, paths in (("DELEGATED", delegated), ("COORDINATOR", coordinator)):
        lc, wc = measure(paths)
        render(label, lc, wc, args.max_lines, args.max_words)
        print()

    print("A high fraction over the caps is the GAP this bound reports, not evidence the caps are")
    print("wrong. The caps derive from the relay's own 'in four lines' seed, never from this corpus.")


if __name__ == "__main__":
    main()
