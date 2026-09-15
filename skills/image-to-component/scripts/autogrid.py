"""The --auto search, minus the toolchain: prep rules, the bounded grid, and the choice of a winner.

Stdlib only, so the gated suite tests every decision `auto.py` makes without vtracer, resvg or SVGO.

Why the grid is trace-side only: QA scores a run against its *own* prepared reference, and every prep
flag (`--matte`, `--sharpen`, `--tolerance`) changes that reference. Candidates that differ in prep are
held to different bars, and "smallest passing" then rewards whichever erased detail — the unsharpened
degraded glyphs pass at IoU 0.98 with their holes closed. So prep is derived once, by rule, from what
the source measurably is, and the grid varies only what the reference does not depend on.
"""
from __future__ import annotations

BLURRED_RAMP = 1.35     # edges.edge_ramp: clean RubyTech glyphs 0.55–1.10, degraded 1.59–2.19
SHARPEN_RADIUS = 0.8    # the soft-source glyph row's --sharpen
GLYPH_TOLERANCE = 25    # global soft keying reads tolerance only as the ground-noise cut
GLYPH_SCALE = 8
# A source this small (longest side, keyed and trimmed) also tries SMALL_GLYPH_SCALE: a 1-2 px stroke is
# 8-16 render px at x8, a spline fit's error is a tenth of that, and IoU fails on strokes the trace has
# right. Measured on the RubyTech glyphs downscaled x0.4-x0.5 (21-27 px): none of computer x0.4, x0.5 or
# controller x0.4 passes at x8 with any smoothing; all three pass at x16.
SMALL_GLYPH_MAX = 40
SMALL_GLYPH_SCALE = 16
COLOUR_SCALE = {"icon": 2, "logo": 2, "illustration": 1}
# Glyph smoothing, as multiples of --scale after "auto": 4.5 / 1.5 / 0.5 at x8.
GLYPH_SMOOTH_PER_SCALE = (0.5625, 0.1875, 0.0625)
COLOUR_COLORS = {"icon": (16, 32, 48), "logo": (32, 48, 64, 96), "illustration": (24, 32, 48)}
COLOUR_SPECKLE = (4, 7, 12)
# Every colour setting is tried with its palette regions voted smooth (regions.vote) at this many px per
# unit of --scale, and without. Smoothing costs bytes, so "smallest passing" alone would never choose it:
# the smoothed candidates are tier 0 and win whenever one passes. On the degraded mark at x2, radius 1
# took jaggedness 7.17 -> 5.99 and edge_f1 0.846 -> 0.866 for mae 11.35 -> 11.66 and +1.2 KB; 1.5 failed
# mae (12.54). layer_difference=12, an axis before, was never chosen by any search measured and is gone.
REGION_RADIUS_PER_SCALE = 0.5
# A colour source this small also tries (scale, colors, filter_speckle) above x2: at x2 a 50-80 px gem's
# anti-aliased facet edges are a large share of its visible pixels, and mae stays over 12 at any palette
# (the RubyTech mark at x0.5 and x0.4: 13.0-18.9 across 64 settings at x2). x0.5 passes at 3/64/7 and
# x0.4 at 4/64/12; a larger scale costs bytes, so the smallest-passing rule still prefers x2 when x2 passes.
SMALL_COLOUR_MAX = 80
SMALL_COLOUR_EXTRA = ((3, 48, 7), (3, 64, 7), (3, 64, 12), (4, 48, 12), (4, 64, 12), (4, 64, 24))
MAX_CANDIDATES = 36


def derive_prep(mono: bool, ramp: float | None) -> dict:
    """Prep flags from the source's measured edge ramp. One rule per flag, each from a SKILL.md row."""
    if mono:
        blurred = ramp is not None and ramp >= BLURRED_RAMP
        return {"key": "global", "matte": "soft", "tolerance": GLYPH_TOLERANCE,
                "sharpen": SHARPEN_RADIUS if blurred else 0}
    return {"key": "flood", "matte": "soft", "tolerance": 40, "sharpen": 0}


def candidates(kind: str, mono: bool, size: tuple[int, int]) -> list[dict]:
    """The grid, in a fixed order, for a keyed source of `size` px.

    Every entry is {"smooth", "scale", "colors", "sets"}; `sets` is a tuple of key=value.
    """
    if mono:
        scales = (GLYPH_SCALE,) + ((SMALL_GLYPH_SCALE,) if max(size) <= SMALL_GLYPH_MAX else ())
        return [{"smooth": s, "scale": scale, "colors": 0, "sets": (), "tier": 0}
                for scale in scales
                for s in ["auto"] + [f"{factor * scale:g}" for factor in GLYPH_SMOOTH_PER_SCALE]]
    settings = [(COLOUR_SCALE[kind], colors, speckle) for colors in COLOUR_COLORS[kind] for speckle in COLOUR_SPECKLE]
    if max(size) <= SMALL_COLOUR_MAX:
        settings += list(SMALL_COLOUR_EXTRA)
    return [{"smooth": smooth, "scale": scale, "colors": colors, "sets": (f"filter_speckle={speckle}",), "tier": tier}
            for scale, colors, speckle in settings
            for smooth, tier in ((f"{REGION_RADIUS_PER_SCALE * scale:g}", 0), ("auto", 1))]


def to_args(prep: dict, candidate: dict) -> list[str]:
    """The i2c.sh flags that reproduce one candidate, defaults left out so the record reads like a row."""
    args = ["--key", prep["key"], "--matte", prep["matte"], "--tolerance", str(prep["tolerance"]),
            "--scale", f"{candidate['scale']:g}"]
    if prep["sharpen"]:
        args += ["--sharpen", f"{prep['sharpen']:g}"]
    if candidate["smooth"] != "auto":
        args += ["--smooth", candidate["smooth"]]
    if candidate["colors"]:
        args += ["--colors", str(candidate["colors"])]
    for item in candidate["sets"]:
        args += ["--set", item]
    return args


def _shortfall(result: dict) -> float:
    """How far a refused candidate is from passing, each failed bar as a fraction of its limit."""
    total = float(len(result["check"]))
    qa = result.get("qa") or {}
    limits = qa.get("thresholds", {})
    for name in qa.get("failures", []):
        score, limit = qa.get(name), limits.get(name)
        if score is None or not limit:
            total += 1.0
        elif name in ("iou", "edge_f1"):
            total += max(limit - score, 0) / limit
        else:
            total += max(score - limit, 0) / limit
    return total


def passes(result: dict) -> bool:
    return not result["check"] and bool((result.get("qa") or {}).get("pass"))


def select(results: list[dict]) -> tuple[int | None, int]:
    """(index of the smallest passing candidate or None, index of the nearest miss).

    Lowest tier first, then smallest by SVG bytes, ties kept in
    grid order. The nearest miss is the one with the fewest failed
    bars, then the smallest shortfall — what a refusal names so the next flag to try is visible.
    """
    if not results:
        raise ValueError("an empty grid has no candidate to choose")
    passing = [i for i, r in enumerate(results) if passes(r)]
    chosen = min(passing, key=lambda i: (results[i]["tier"], results[i]["bytes"], i)) if passing else None
    def miss(i):
        failures = len(results[i]["check"]) + len((results[i].get("qa") or {}).get("failures", []))
        return (failures, _shortfall(results[i]), i)
    nearest = chosen if chosen is not None else min(range(len(results)), key=miss)
    return chosen, nearest
