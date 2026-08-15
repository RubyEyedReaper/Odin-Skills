"""DEC decision-ledger writer (Sprint 4, stdlib only: pathlib, re, datetime).

A "DEC" is a numbered, recorded decision produced by a scoring run: a markdown file with
YAML frontmatter (hand-rolled, not a YAML library — stdlib only) plus a human-readable
recommendation, scored matrix, and sensitivity summary.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

_DEC_FILENAME_RE = re.compile(r"^DEC-(\d{4})-")
_SLUG_MAX_LEN = 40


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

    rows = [header, separator]
    for option in options:
        opt_id = option.get("id")
        opt_label = option.get("label", opt_id)
        cells = []
        for crit in criteria:
            cid = crit.get("id")
            agg = aggregated.get(opt_id, {}).get(cid, {})
            cells.append(f"{agg.get('confidence_adjusted', 0):.1f}" if agg else "—")
        score = score_by_option.get(opt_id)
        score_cell = f"{score:.2f}" if score is not None else "—"
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
        "---\n"
    )

    rationale = recommendation.get("rationale", "")
    winner_label = recommendation.get("winner_label", winner)
    caveats = recommendation.get("caveats", [])
    caveats_md = (
        "\n".join(f"- {c}" for c in caveats) if caveats else "_None._"
    )

    body = f"""
## Recommendation

**Winner:** {winner_label}
**Confidence:** {confidence}

{rationale}

**Caveats:**

{caveats_md}

## Scored Matrix

{_format_scored_matrix(spec, result)}

## Sensitivity

{_format_sensitivity_summary(result)}
"""

    path.write_text(frontmatter + body, encoding="utf-8")
    return path, resolved_dec_id


def update_readme_index(dec_id: str, title: str, path: Path, decisions_dir: Path, winner: str = None) -> None:
    """Upsert a row for dec_id in decisions_dir/README.md (create with header if missing).

    Does not duplicate an existing dec_id row — re-running for the same dec_id is a no-op
    on the table contents (idempotent upsert).
    """
    decisions_dir = Path(decisions_dir)
    decisions_dir.mkdir(parents=True, exist_ok=True)
    readme_path = decisions_dir / "README.md"

    header_lines = [
        "# Decision Ledger",
        "",
        "| DEC | Title | Winner | Record |",
        "|---|---|---|---|",
    ]

    try:
        rel_path = Path(path).relative_to(decisions_dir)
    except ValueError:
        rel_path = Path(path).name
    link = f"[{Path(path).name}]({rel_path})"
    new_row = f"| {dec_id} | {title} | {winner or '—'} | {link} |"

    if readme_path.exists():
        lines = readme_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = list(header_lines)

    # Find existing row for this dec_id (rows look like "| DEC-0001 | ... |").
    row_prefix = f"| {dec_id} |"
    existing_index = None
    for i, line in enumerate(lines):
        if line.startswith(row_prefix):
            existing_index = i
            break

    if existing_index is not None:
        lines[existing_index] = new_row
    else:
        # Insert after the last table row rather than at EOF: the README ends with an
        # explanatory comment, and appending past it drops the row outside the table.
        last_row = max(
            (i for i, line in enumerate(lines) if line.lstrip().startswith("|")),
            default=None,
        )
        if last_row is None:
            lines.append(new_row)
        else:
            lines.insert(last_row + 1, new_row)

    readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def promote_to_adr_hint(result: dict) -> bool:
    """True iff reversibility is one-way AND recommendation.confidence != "low"."""
    reversibility = result.get("reversibility")
    confidence = result.get("recommendation", {}).get("confidence")
    return reversibility == "one-way" and confidence != "low"
