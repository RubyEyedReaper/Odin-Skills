"""DEC decision-ledger writer (Sprint 4, stdlib only: pathlib, re, datetime).

A "DEC" is a numbered, recorded decision produced by a scoring run: a markdown file with
YAML frontmatter (hand-rolled, not a YAML library — stdlib only) plus a human-readable
recommendation, scored matrix, and sensitivity summary.
"""
import hashlib
import importlib.util
import json
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from scripts.ledgers import render_to
from scripts.validate import constraint_violations

_DEC_FILENAME_RE = re.compile(r"^DEC-(\d{4})-")
_DEC_ID_FORMAT_RE = re.compile(r"^DEC-(\d{4})$")
_SLUG_MAX_LEN = 40

# scripts/ -> decision-matrix/ -> skills/ -> .claude/
_ID_ALLOC = Path(__file__).resolve().parents[3] / "scripts" / "lib" / "id_alloc.py"


def _load_id_alloc():
    """Load the shared allocator by path.

    By path rather than by import, because this skill's `scripts/` package is not on the
    path that reaches `.claude/scripts/lib/`, and a `sys.path` mutation at import time
    changes resolution for every module the process later loads. The allocator is stdlib
    only, so this costs nothing but the file read.
    """
    spec = importlib.util.spec_from_file_location("odin_id_alloc", _ID_ALLOC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    _id_alloc = _load_id_alloc()
    IdCollision = _id_alloc.IdCollision
except (OSError, AttributeError):  # pragma: no cover - the allocator is shipped beside us
    _id_alloc = None

    class IdCollision(RuntimeError):
        """Placeholder so callers can catch it even where the allocator is absent."""


@contextmanager
def allocate_dec_id(decisions_dir, want=None):
    """Yield a DEC id reserved against the counter every worktree of this clone shares.

    THE DEFECT THIS CLOSES (harness:RM-0165). `next_dec_number` scans one working copy,
    and each git worktree holds its own. On 2026-08-20 two sessions each read this ledger's
    high-water mark in their own worktree and both minted DEC-0028 for unrelated decisions.
    A third worker the same day held a reservation of 0036-0038 *in writing*, minted
    0029/0038/0038 anyway, and renamed the files and repaired the index rows by hand —
    because nothing here could be told an id. That third instance is the cleanest statement
    of the defect: a reservation that lives only in prose binds nothing.

    `next_dec_number` keeps its meaning and becomes the FLOOR. The counter cannot be behind
    a record somebody wrote by hand, which is what the harness asks parallel workers to do.

    `want` is the reservation made binding: `"DEC-0042"` is honoured when free and raises
    `IdCollision` when taken. It is never quietly turned into a different number.
    """
    floor = next_dec_number(Path(decisions_dir)) - 1

    wanted = None
    if want is not None:
        match = _DEC_ID_FORMAT_RE.match(str(want))
        if match is None:
            raise ValueError(
                "a requested DEC id must read DEC-NNNN, got %r — refusing rather than "
                "guessing which number was meant" % (want,)
            )
        wanted = int(match.group(1))

    if _id_alloc is None:  # pragma: no cover - shipped together
        yield "DEC-%04d" % (wanted or floor + 1)
        return

    with _id_alloc.reserve("dec", floor, start=Path(decisions_dir), want=wanted) as number:
        yield "DEC-%04d" % number


def next_dec_number(decisions_dir: Path) -> int:
    """Return the next available DEC number for decisions_dir.

    Scans for files matching DEC-NNNN-*.md and returns max(N) + 1, or 1 if the
    directory is absent or contains no DEC files.
    """
    decisions_dir = Path(decisions_dir)
    if not decisions_dir.is_dir():
        return 1

    numbers = []
    for path in decisions_dir.glob("DEC-*.md"):
        match = _DEC_FILENAME_RE.match(path.name)
        if match:
            numbers.append(int(match.group(1)))

    return (max(numbers) + 1) if numbers else 1


def slugify(title: str) -> str:
    """Lowercase, non-alphanumeric runs -> single hyphen, collapse repeats, strip, max 40 chars."""
    lowered = title.lower()
    # Replace any run of non-alphanumeric characters with a single hyphen.
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = slug.strip("-")
    if len(slug) > _SLUG_MAX_LEN:
        slug = slug[:_SLUG_MAX_LEN].rstrip("-")
    return slug


def _unique_dec_filename(decisions_dir: Path, dec_id: str, slug: str) -> tuple[Path, str]:
    """Resolve a free filename for dec_id-slug, incrementing the *number* on collision.

    dec_id is e.g. "DEC-0001". If DEC-0001-<slug>.md (or any DEC-0001-*.md) already
    exists, increment the number until a free DEC-NNNN-*.md slot is found, per spec:
    "If DEC-{n:04d}-* already exists, increment until free."

    Returns ``(path, resolved_dec_id)``. The second element is the point: on collision
    the number moves, and a caller still holding the id it asked for will label the
    ledger row with an id that names somebody else's record.
    """
    match = re.match(r"^DEC-(\d{4})$", dec_id)
    n = int(match.group(1)) if match else next_dec_number(decisions_dir)

    while True:
        candidate_id = f"DEC-{n:04d}"
        existing = list(decisions_dir.glob(f"{candidate_id}-*.md"))
        if not existing:
            filename = f"{candidate_id}-{slug}.md" if slug else f"{candidate_id}.md"
            return decisions_dir / filename, candidate_id
        n += 1


def _md_cell(text: str) -> str:
    """Make free-form spec text safe to interpolate into markdown.

    Constraint descriptions are user input and land in a document whose only gate parses
    frontmatter and index rows — a pipe that breaks a table row, or a newline that opens a
    second frontmatter block, passes CI silently and is discovered by reading a record.
    Escaping belongs here, at the render boundary, and not in `validate_spec`: a description
    containing a pipe is a perfectly valid decision spec.
    """
    return " ".join(str(text).split()).replace("|", "\\|")


def _format_veto_section(spec: dict, result: dict) -> str:
    """Render the constraints that eliminated each vetoed option.

    Reads `result["veto_reasons"]` and falls back to recomputing from the spec, which this
    module already receives: hand-built result dicts exist in the test suite, and result
    JSON written before harness:RM-0228 has no such key. A missing key degrades; it never
    raises.
    """
    reasons = result.get("veto_reasons")
    if reasons is None:
        reasons = constraint_violations(spec)
    if not reasons:
        return ""

    lines = ["## Vetoed by Constraint", ""]
    lines.append(
        "These options were eliminated before scoring, so the winner above beat a smaller "
        "field. Each entry names the constraint that bound and what would lift it — without "
        "that, the decision cannot be re-run."
    )
    lines.append("")

    for entry in reasons:
        label = entry.get("option_label") or entry.get("option")
        lines.append(f"- **{_md_cell(label)}** (`{entry.get('option')}`)")
        for constraint in entry.get("constraints", []):
            cid = constraint.get("id")
            description = constraint.get("description")
            if description:
                lines.append(f"  - fails `{cid}` — {_md_cell(description)}")
            else:
                lines.append(
                    f"  - fails `{cid}` — no description declared in `spec.constraints`"
                )
            lifted_by = constraint.get("lifted_by")
            if lifted_by:
                lines.append(f"    - Lifted by: {_md_cell(lifted_by)}")
            else:
                lines.append(
                    "    - No expiry condition declared. What lifts this veto is an event "
                    "outside the decision, so it cannot be derived from the spec — declare "
                    "`lifted_by` on the constraint to record it."
                )

    return "\n".join(lines)


def _format_scored_matrix(spec: dict, result: dict) -> str:
    """Build a markdown table: options x criteria with weighted-sum scores."""
    options = spec.get("options", [])
    criteria = spec.get("criteria", [])
    aggregated = result.get("aggregated_scores", {})

    ws_ranking = result.get("method_results", {}).get("weighted-sum", {}).get("ranking", [])
    score_by_option = {r["option"]: r["score"] for r in ws_ranking}

    crit_labels = [c.get("label", c.get("id")) for c in criteria]
    header = "| Option | " + " | ".join(crit_labels) + " | Weighted-Sum Score |"
    separator = "|---" * (len(criteria) + 2) + "|"

    vetoed = set(result.get("vetoed_options", []))

    rows = [header, separator]
    for option in options:
        opt_id = option.get("id")
        opt_label = option.get("label", opt_id)
        # The table is what a reader scans first, and an em-dash there means "no data" —
        # indistinguishable from an option that simply was not scored. The tag is the same
        # word the HTML companion already uses, so the two files of one DEC read alike.
        if opt_id in vetoed:
            opt_label = f"{opt_label} (vetoed)"
        cells = []
        for crit in criteria:
            cid = crit.get("id")
            agg = aggregated.get(opt_id, {}).get(cid, {})
            cells.append(f"{agg.get('confidence_adjusted', 0):.1f}" if agg else "—")
        score = score_by_option.get(opt_id)
        # Veto takes precedence over any score present. An eliminated option is excluded,
        # not ranked, so printing a number next to it invites the reading this item exists
        # to stop — and the engine's own ranking never contains a vetoed option anyway.
        if opt_id in vetoed:
            score_cell = "vetoed"
        elif score is not None:
            score_cell = f"{score:.2f}"
        else:
            score_cell = "—"
        rows.append(f"| {opt_label} | " + " | ".join(cells) + f" | {score_cell} |")

    return "\n".join(rows)


def _format_sensitivity_summary(result: dict) -> str:
    sensitivity = result.get("sensitivity", {})
    if not sensitivity:
        return "No sensitivity data (no active options to analyze)."

    lines = [
        f"Winner analyzed: `{sensitivity.get('winner_analyzed')}`",
        f"Fragile: **{sensitivity.get('fragile')}**"
        + (f" — {sensitivity.get('fragile_reason')}" if sensitivity.get("fragile_reason") else ""),
        "",
        "Break-even (weight shift to flip winner):",
    ]
    for cid, entry in sensitivity.get("break_even", {}).items():
        shift = entry.get("weight_shift_to_flip_pct")
        favors = entry.get("favors_if_flipped")
        if shift is None:
            lines.append(f"- `{cid}`: no flip found")
        else:
            lines.append(f"- `{cid}`: flips at +{shift:.1f}pp, favors `{favors}`")

    return "\n".join(lines)


def spec_fingerprint(spec: dict) -> str:
    """A stable digest of the decision a spec describes.

    THE INCIDENT (KinNest ledger, 2026-09-07): `--record` wrote DEC-0050 and
    DEC-0051 and exited 0, the shell pipe reading its stdout errored, the
    operator read that as a failed run, and the retry allocated DEC-0052 and
    DEC-0053 for the same two decisions. The engine could not see the broken
    pipe. It can see that this spec has already been recorded, which is the
    condition that actually matters, and it is the only one a retry preserves.

    Over the whole spec minus its routing keys, so the sensitivity of the
    fingerprint matches what a decision *is*: change a weight, a score, an
    option or a constraint and it is a different decision that must record;
    re-run the same spec after a transport failure and it is the same one.
    `decisions_dir` and `dec_id` name where a record goes rather than what it
    decides, so both are excluded — recording one spec into two ledgers is two
    records by construction, and the fingerprint is only ever compared within
    one ledger.
    """
    material = {k: v for k, v in spec.items() if k not in ("decisions_dir", "dec_id")}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def find_record_by_fingerprint(decisions_dir, fingerprint: str):
    """The `(dec_id, path)` already recording this spec in this ledger, or None.

    Reads frontmatter only, and only the `.md` records — an `.html` twin sits
    beside each one and a walk without the filter would double every hit.

    A record written before the fingerprint field existed carries none, and is
    therefore never matched. That is the honest behaviour: the field is evidence
    that a specific spec produced this record, and its absence is not evidence
    of anything. Older records are not retrofitted.
    """
    decisions_dir = Path(decisions_dir)
    if not decisions_dir.is_dir():
        return None

    for record in sorted(decisions_dir.glob("DEC-*.md")):
        if not _DEC_FILENAME_RE.match(record.name):
            continue
        head = record.read_text(encoding="utf-8", errors="replace")[:4000]
        if not head.startswith("---"):
            continue
        for line in head.splitlines()[1:]:
            if line.startswith("---"):
                break
            key, sep, value = line.partition(":")
            if sep and key.strip() == "spec_fingerprint" and value.strip() == fingerprint:
                number = _DEC_FILENAME_RE.match(record.name).group(1)
                return "DEC-%s" % number, record
    return None


def write_dec_record(dec_id: str, spec: dict, result: dict, decisions_dir: Path) -> tuple[Path, str]:
    """Write a DEC-NNNN-<slug>.md record under decisions_dir.

    dec_id: e.g. "DEC-0001" (number portion drives the filename and frontmatter).

    Returns ``(path, resolved_dec_id)``. ``resolved_dec_id`` is not always ``dec_id`` —
    a concurrent session can claim the slot between the caller's read and this write,
    and the number is bumped. Index the row with the returned id, never the requested
    one: ``update_readme_index`` upserts on the id prefix, so a stale id overwrites the
    row of whoever actually holds it.
    """
    decisions_dir = Path(decisions_dir)
    decisions_dir.mkdir(parents=True, exist_ok=True)

    goal = spec.get("goal", "")
    slug = slugify(goal)
    path, resolved_dec_id = _unique_dec_filename(decisions_dir, dec_id, slug)

    recommendation = result.get("recommendation", {})
    winner = recommendation.get("winner")
    confidence = recommendation.get("confidence")
    reversibility = spec.get("reversibility", result.get("reversibility", ""))
    fragile = result.get("sensitivity", {}).get("fragile", False)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    frontmatter = (
        "---\n"
        f"dec_id: {resolved_dec_id}\n"
        f"date: {date_str}\n"
        f"goal: {goal}\n"
        f"reversibility: {reversibility}\n"
        f"winner: {winner}\n"
        f"confidence: {confidence}\n"
        f"fragile: {str(fragile).lower()}\n"
        f"spec_fingerprint: {spec_fingerprint(spec)}\n"
        "---\n"
    )

    rationale = recommendation.get("rationale", "")
    winner_label = recommendation.get("winner_label", winner)
    caveats = recommendation.get("caveats", [])
    caveats_md = (
        "\n".join(f"- {c}" for c in caveats) if caveats else "_None._"
    )

    veto_section = _format_veto_section(spec, result)
    _veto_section = f"\n{veto_section}\n" if veto_section else ""

    body = f"""
## Recommendation

**Winner:** {winner_label}
**Confidence:** {confidence}

{rationale}

**Caveats:**

{caveats_md}

## Scored Matrix

{_format_scored_matrix(spec, result)}
{_veto_section}
## Sensitivity

{_format_sensitivity_summary(result)}
"""

    path.write_text(frontmatter + body, encoding="utf-8")
    return path, resolved_dec_id


def update_readme_index(dec_id: str, title: str, path: Path, decisions_dir: Path, winner: str = None) -> None:
    """Rewrite the ledger's index from every record in it. The arguments are ignored.

    WHY THE ARGUMENTS ARE IGNORED (harness:RM-0224). This function used to append one row at
    the end of the index table, which is where every other branch's row also went — so two
    campaign branches each recording a decision conflicted on rebase, by construction, on
    every pair. The index is now derived from the records: `ledgers.render_to` reads each
    `DEC-*.md`'s frontmatter, which already carries `dec_id`, `goal` and `winner`, so there
    is nothing a caller can tell it that the ledger does not already say.

    The signature survives because callers and their tests spell it, and because being told
    a row is exactly what let the index disagree with the records in the first place (issue
    #244): a record written by hand never called this, and the row it should have added was
    never noticed missing. A renderer cannot have that failure.

    Kept and not deleted: `projects/Odin-Skills/skills/decision-matrix/` mirrors this file and
    is checked for drift by a gate this change must not break.
    """
    render_to(Path(decisions_dir))


def promote_to_adr_hint(result: dict) -> bool:
    """True iff reversibility is one-way AND recommendation.confidence != "low"."""
    reversibility = result.get("reversibility")
    confidence = result.get("recommendation", {}).get("confidence")
    return reversibility == "one-way" and confidence != "low"
