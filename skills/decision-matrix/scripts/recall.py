"""Prior-decision recall for the DEC ledger (Sprint 4, stdlib only: pathlib, re).

Greps recorded DEC-*.md files for keyword overlap with the current decision's goal and
option labels, so the agent can surface "you decided something similar before."
"""
import re
from pathlib import Path

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "for", "to", "of", "in", "on", "at",
    "is", "are", "was", "were", "be", "been", "being", "with", "by", "from",
    "this", "that", "these", "those", "it", "its", "as", "about", "into",
    "i", "we",
}

# Generic decision-framing verbs/adjectives that recur in nearly every DEC goal line
# ("Pick a...", "Choose the best...") and would otherwise produce meaningless keyword
# overlap between unrelated decisions. Excluded only from *match scoring*, not from
# extract_keywords()'s general output.
_GENERIC_MATCH_WORDS = {
    "pick", "choose", "select", "best", "which", "should", "decide",
    "option", "provider", "tool", "layer", "good", "right",
}

_DEC_GOAL_RE = re.compile(r"^goal:\s*(.+)$", re.MULTILINE)
_DEC_ID_RE = re.compile(r"^dec_id:\s*(.+)$", re.MULTILINE)


def extract_keywords(text: str) -> list:
    """Lowercase tokens minus a small stopword set, unique (order-preserving)."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    seen: set = set()
    keywords: list = []
    for token in tokens:
        if token in _STOPWORDS or not token:
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)
    return keywords


def _build_snippet(content: str, matched_keywords: set, max_len: int = 160) -> str:
    """Return a short excerpt from content around the first matched keyword, else the goal line."""
    goal_match = _DEC_GOAL_RE.search(content)
    base = goal_match.group(1).strip() if goal_match else content.strip().splitlines()[0] if content.strip() else ""
    if len(base) > max_len:
        base = base[:max_len].rstrip() + "…"
    return base


def search_prior_decisions(goal: str, options: list, decisions_dir: Path) -> list:
    """Grep DEC files under decisions_dir for keyword overlap with goal + option labels.

    Returns [{"dec_id", "title", "path", "relevance_snippet"}, ...]. Empty list if
    decisions_dir is absent, empty, or no DEC file shares a keyword.
    """
    decisions_dir = Path(decisions_dir)
    if not decisions_dir.is_dir():
        return []

    query_text = goal + " " + " ".join(str(o) for o in options)
    query_keywords = set(extract_keywords(query_text)) - _GENERIC_MATCH_WORDS
    if not query_keywords:
        return []

    results: list = []
    for path in sorted(decisions_dir.glob("DEC-*.md")):
        content = path.read_text(encoding="utf-8")
        doc_keywords = set(extract_keywords(content)) - _GENERIC_MATCH_WORDS
        overlap = query_keywords & doc_keywords
        if not overlap:
            continue

        dec_id_match = _DEC_ID_RE.search(content)
        dec_id = dec_id_match.group(1).strip() if dec_id_match else path.stem

        goal_match = _DEC_GOAL_RE.search(content)
        title = goal_match.group(1).strip() if goal_match else path.stem

        results.append({
            "dec_id": dec_id,
            "title": title,
            "path": str(path),
            "relevance_snippet": _build_snippet(content, overlap),
        })

    return results
