"""What the documented surface claims about the engine, checked against the engine.

`roadmap-check.sh` carried the argparse-introspection preamble three times, verbatim, and this
change set would have taken it to five. A heredoc inside a bash gate is the same problem as logic
in YAML (`.claude/rules/ci/patterns.md`): nothing imports it, so nothing tests it, and the copies
drift from each other silently. One module, imported by the gate and by the suite.

Every check here resolves a citation **by execution** — it reads the real
`argparse` registry, imports the real symbol, or consults the real finding-kind set. None of them
greps a heading, because a heading grep asserts the author's assumption rather than the tool's
behaviour (ADR-0068, DEC-0011).

Stdlib only.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import re
import shlex

from .roadmap import build_parser

# A documented invocation may legitimately carry a placeholder. Substituted with a literal token
# before parsing, so `<slug>` is checked for *shape* rather than rejected for not being a value.
_PLACEHOLDER_RE = re.compile(r"<[^>]+>")
_PLACEHOLDER = "PLACEHOLDER"

# A line inside a fenced block that instructs a reader to run the engine. The four spellings the
# documentation actually uses; a line that merely mentions a command in prose is not an
# instruction and is deliberately not matched.
_INVOCATION_RE = re.compile(
    r"^\s*(?:cd\s+\S+\s*&&\s*)?"
    r"(?:python3?\s+-m\s+scripts\.roadmap|/?roadmap)\s+(?P<argv>.+?)\s*$"
)


def parser_surface():
    """`(subcommands, global_flags)` — what the CLI accepts, read from the registry.

    From `_SubParsersAction.choices`, never from `--help`: the registry is what the parser accepts,
    and the help text is a rendering of it that argparse may wrap or reorder. Asserting the
    rendering would go red for reasons that have nothing to do with which commands exist.
    """
    parser = build_parser()
    subcommands, global_flags = {}, set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                subcommands[name] = {opt for a in sub._actions for opt in a.option_strings}
        else:
            global_flags.update(action.option_strings)
    return subcommands, global_flags


def _usage_block_lines(path):
    """Lines inside the fenced block under `## Usage` — prose cannot document a command."""
    out, in_usage, fence = [], False, 0
    with open(path, encoding="utf-8") as fh:
        for number, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if line.startswith("## Usage"):
                in_usage = True
                continue
            if in_usage and line.startswith("```"):
                fence += 1
                if fence == 2:
                    break
                continue
            if in_usage and fence == 1:
                out.append((number, line))
    return out


def _fenced_lines(path):
    """Every line inside any fenced code block, with its 1-based line number.

    The fence is matched after stripping indentation. A fence nested in a list item is indented,
    and `projects/README.md` — the document whose broken invocation motivated this check — puts its
    command in exactly that shape. Anchoring on column zero made the gate report `checked=0` for
    that file: a gate silently excluding its own failing case, which is worse than no gate.
    """
    out, fence = [], False
    with open(path, encoding="utf-8") as fh:
        for number, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if line.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence:
                out.append((number, line))
    return out


def check_usage_block(path):
    """`.claude/commands/roadmap.md` — subcommand names and flags against the engine."""
    subcommands, global_flags = parser_surface()
    problems = []
    documented = set()
    for _number, line in _usage_block_lines(path):
        match = re.match(r"^/roadmap ([a-z][a-z0-9-]*)\b(.*)$", line)
        if not match:
            continue
        name, rest = match.group(1), match.group(2).split("#")[0]
        if name not in subcommands:
            problems.append(("unknown", name, ""))
            continue
        documented.add(name)
        known = subcommands[name] | global_flags
        for flag in re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", rest):
            if flag not in known:
                problems.append(("badflag", name, flag))
    for name in sorted(set(subcommands) - documented):
        problems.append(("missing", name, ""))
    return problems


def check_engine_table(path):
    """The `## Engine` table in `SKILL.md` — every subcommand present, every flag real."""
    subcommands, global_flags = parser_surface()
    problems, documented = [], set()
    in_engine = False
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("## "):
                in_engine = line.strip().lower() == "## engine"
                continue
            if not in_engine or not line.startswith("|"):
                continue
            cell = line.split("|")[1].strip()
            match = re.match(r"^`([a-z][a-z0-9-]*)\b([^`]*)`", cell)
            if not match:
                continue
            name, rest = match.group(1), match.group(2)
            if name not in subcommands:
                problems.append(("unknown", name, ""))
                continue
            documented.add(name)
            known = subcommands[name] | global_flags
            for flag in re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", rest):
                if flag not in known:
                    problems.append(("badflag", name, flag))
    for name in sorted(set(subcommands) - documented):
        problems.append(("missing", name, ""))
    return problems


def _joined_fenced_lines(path):
    """Fenced lines, with backslash continuations folded into the line that started them.

    A multi-line invocation is one instruction. Read line-by-line it becomes a fragment ending in
    `\\` plus an orphaned tail, and both parse as nonsense — a gate reporting two defects where the
    document has none is a gate someone switches off.
    """
    out = []
    pending, start = None, None
    for number, line in _fenced_lines(path):
        text = line.rstrip()
        if pending is not None:
            pending += " " + text.lstrip()
            if not pending.endswith("\\"):
                out.append((start, pending))
                pending, start = None, None
                continue
            pending = pending[:-1].rstrip()
            continue
        if text.endswith("\\"):
            pending, start = text[:-1].rstrip(), number
            continue
        out.append((number, text))
    if pending is not None:
        out.append((start, pending))
    return out


def check_invocations(path):
    """Every fenced invocation in `path` must parse. Returns `(problems, checked_count)`.

    **Parsed, never executed.** These are mutating commands; a gate that ran what a document
    instructs would write. `parse_args` inside a `SystemExit` guard is the whole check — argparse
    exits 2 on an unrecognised flag or a missing required argument, which is exactly the failure a
    reader following the document hits (harness:RM-0102).

    Three things a document legitimately does, which a naive reader of these lines would report as
    defects, and which are handled rather than excused:

    * **Quoting** — `--title "Signup page"` is one argument. `shlex.split`, not `str.split`.
    * **Continuations** — folded by `_joined_fenced_lines` before we get here.
    * **Placeholders** — `--kind <K>` cannot satisfy a `choices=` argument, and never could. The
      substituted token is looked for in argparse's own message, so a failure *about the
      placeholder* is not a finding while an unrecognised flag on the same line still is.

    The count is returned so the caller can refuse a silent zero: extracting nothing from a
    non-empty corpus means the extraction rule stopped matching, not that the corpus is clean.
    """
    subcommands, _ = parser_surface()
    parser = build_parser()
    problems, checked = [], 0
    for number, line in _joined_fenced_lines(path):
        match = _INVOCATION_RE.match(line)
        if not match:
            continue
        text = match.group("argv")
        # `#` and `<-` both introduce an annotation a reader is not meant to type.
        for delimiter in ("#", "<-"):
            text = text.split(delimiter)[0]
        text = _PLACEHOLDER_RE.sub(_PLACEHOLDER, text)
        try:
            argv = shlex.split(text)
        except ValueError:
            continue
        if not argv or not any(word in subcommands for word in argv):
            continue
        checked += 1
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                parser.parse_args(argv)
        except SystemExit:
            if _PLACEHOLDER in stderr.getvalue():
                continue
            problems.append((number, " ".join(argv), stderr.getvalue().strip().splitlines()[-1:]))
        except Exception as exc:  # noqa: BLE001 — a parser crash is a finding, not a gate failure
            problems.append((number, " ".join(argv), [str(exc)]))
    return problems, checked


def check_vocabulary():
    """harness:RM-0109 — two mechanisms, two names, asserted on the rendered help.

    The artifact a reader actually sees is the help text, so that is what this asserts rather than
    the source (`.claude/rules/ci/testing.md` § Assert Outcomes, Not Intent). A forbidden-identifier
    grep was rejected: it fires on the ten files that legitimately *record* the rename, `CHANGELOG.md`
    and the campaign audits among them, and a gate that reddens history is a gate someone deletes.

    `--surface-sweep` and `surface_roots` are allowlisted spellings: the flag keeps its name for
    back-compat, so the check is about the words *around* it.
    """
    parser = build_parser()
    problems = []

    def _help_for(name):
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action.choices[name].format_help()
        return ""

    boot, rec = _help_for("bootstrap"), _help_for("reconcile")
    if "starter" not in boot.lower():
        problems.append("bootstrap --help no longer names starter surfaces")
    if "unclaimed" in boot.lower():
        problems.append("bootstrap --help describes its list as unclaimed — that is the sweep")
    if "unclaimed" not in rec.lower():
        problems.append("reconcile --help no longer names unclaimed surfaces")
    if "starter" in rec.lower():
        problems.append("reconcile --help calls its sweep a starter list")

    # Each glossary term cites a symbol; resolve the citation by importing it.
    from . import roadmap as roadmap_mod
    from . import reconcile as reconcile_mod
    from . import sweep as sweep_mod

    if not getattr(roadmap_mod, "STARTER_SURFACES", None):
        problems.append("STARTER_SURFACES is not importable from scripts.roadmap")
    if not callable(getattr(sweep_mod, "untracked_surfaces", None)):
        problems.append("untracked_surfaces is not importable from scripts.sweep")
    if "untracked-surface" not in reconcile_mod.FINDING_KINDS:
        problems.append("untracked-surface is not a finding kind")
    if "starter" in (sweep_mod.__doc__ or "").lower():
        problems.append("scripts/sweep.py describes itself as a starter list")
    return problems
