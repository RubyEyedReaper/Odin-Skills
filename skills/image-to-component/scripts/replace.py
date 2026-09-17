"""Decide whether a library icon may stand in for a source: the verifier behind `--replace`.

Stdlib only; every buffer is alpha-only, one byte per pixel, at the source's size. The renders are the
driver's (`replace_run.py`): each candidate already fitted to the source and degraded to match it —
blurred, box-resampled — so a clean library vector is never held to a degraded source's bars, and a
degraded source is never cleaned before it is compared (DEC-0179).

The rule (DEC-0178) is adversarial, not a threshold on one score:

1. The named candidate must fit: `soft_iou(source, render) >= bar`.
2. Every adversary — the library icons whose renders fit this source best, minus renders identical to
   the named one at full size (`equivalent`) — is compared with the named render **only where the two
   renders disagree** (`pair_margin`). On those pixels the source must side with the named render by at
   least `margin`, on a scale from -1 (it is the adversary) to +1 (it is the named icon).
3. An adversary whose render differs from the named one by less than `min_weight` opaque pixels cannot
   be told apart at this size. That refuses too: a replacement nobody can verify is not accepted.

A misnamed object therefore cannot force a replacement: the icon it really is sits among the
adversaries, and the source sides with it.
"""
from __future__ import annotations

import json

from .keying import PEAK_PERCENTILE
from .library import LIBRARIES, _ink_box

KNOCKOUT_MIN_SHARE = 0.03    # a second colour must cover this share of the opaque ink to be a knockout (a 2 px "!" in a 32 px disc is 5%)
KNOCKOUT_MIN_DISTANCE = 80   # and sit this far (RGB Euclidean) from the dominant colour
OPAQUE = 200
KNOCKOUT_EDGE_MAX = 0.05     # a second colour on less than this share of the silhouette edge is cut out of the ink
GROUND_NEAR = 40             # RGB distance within which an opaque pixel is the ground showing through
ENCLOSED_MIN_SHARE = 0.02    # this share of the opaque ink being ground makes the ground reading the silhouette
LIBRARY_TRADEMARK = {lib: spec["trademark"] for lib, spec in LIBRARIES.items()}
PARAMS = ("bar", "margin", "auto_margin", "auto_min_px", "min_weight", "equivalent", "shortlist", "sigmas")


def load_params(path: str) -> dict:
    """The calibrated numbers the verifier decides with (`replace.json`); every one must be declared."""
    with open(path, encoding="utf-8") as fh:
        params = json.load(fh)
    missing = [key for key in PARAMS if key not in params]
    if missing:
        raise ValueError(f"{path} declares no {', '.join(missing)}")
    return params


def unblurred_radius(radius: float, sigma: float) -> float:
    """A blurred source's radius of gyration with the blur's variance (sigma² per axis) taken back out.

    Floored at half the measured radius: a blur estimate larger than the shape is a bad estimate, and a
    fit to a vanishing radius would scale the icon to nothing.
    """
    return max(radius * radius - 2 * sigma * sigma, (radius / 2) ** 2) ** 0.5


def normalise_peak(alpha: bytes, gamma: float) -> bytes:
    """A render stretched the way `keying.soft_matte` stretches a keyed glyph: its PEAK_PERCENTILE ink is full
    alpha, then the coverage gamma. A thin stroke's render never reaches full coverage; the keyed source was
    stretched to, so the candidate gets the same treatment rather than the source being un-stretched."""
    ink = sorted(v for v in alpha if v)
    if not ink:
        return bytes(alpha)
    peak = ink[min(int(len(ink) * PEAK_PERCENTILE), len(ink) - 1)]
    return bytes(round(255 * min(1.0, v / peak) ** gamma) for v in alpha)


def choose_sigma(source_ramp: float | None, ramps: dict[float, float]) -> float:
    """The blur whose render has the edge ramp nearest the source's (`edges.edge_ramp`); 0 when unmeasurable."""
    if source_ramp is None:
        return 0.0
    return min(ramps, key=lambda sigma: (abs(ramps[sigma] - source_ramp), sigma))


def soft_iou(a: bytes, b: bytes) -> float:
    """Σ min / Σ max over two alpha buffers: 1 for identical, 0 for disjoint."""
    top = sum(map(max, a, b))
    return sum(map(min, a, b)) / top if top else 0.0


def pair_margin(source: bytes, named: bytes, adversary: bytes) -> tuple[float, float]:
    """(t, weight): which render the source sides with, on the pixels where the renders disagree.

    Each pixel counts in proportion to how much the renders disagree there, so shared ink — however
    much of it — says nothing. t = (err_adversary - err_named) / Σ disagreement², in [-1, 1]; weight is
    the disagreement in opaque-pixel units, the evidence available at this size.
    """
    err_named = err_adversary = norm = spread = 0
    for s, n, a in zip(source, named, adversary):
        d = abs(n - a)
        if d:
            err_named += abs(s - n) * d
            err_adversary += abs(s - a) * d
            norm += d * d
            spread += d
    if not norm:
        return 0.0, 0.0
    return (err_adversary - err_named) / norm, spread / 255


def equivalent(a: bytes, b: bytes, threshold: float) -> bool:
    """Two full-size clean renders so alike (`close` and `close-fill`) that neither is an adversary of the other."""
    return soft_iou(a, b) >= threshold


def shortlist(index: dict, thumb: bytes, aspect: float, k: int, exclude=frozenset(),
              aspect_limit: float = 0.35) -> list[str]:
    """The k index slugs whose thumbnails are nearest (L1) to the source's, skipping far aspects and `exclude`.

    An entry with blur levels (`thumbs`) is as near as its nearest level, so a soft 12 px source is compared
    with a soft thumbnail rather than losing to every blob in the library."""
    scored = []
    for slug, entry in index.items():
        if slug in exclude:
            continue
        off = abs(aspect / entry["aspect"] - 1)
        if off > aspect_limit:
            continue
        distance = min(sum(map(lambda x, y: abs(x - y), thumb, bytes.fromhex(level)))
                       for level in entry.get("thumbs") or [entry["thumb"]])
        scored.append((distance / (len(thumb) * 255) + off / 2, slug))
    scored.sort()
    return [slug for _, slug in scored[:k]]


def _mean(pixels: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return tuple(round(sum(p[i] for p in pixels) / len(pixels)) for i in range(3))


def _dist(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _edge_votes(rgba: bytes, width: int, height: int, centres) -> list[int]:
    """How many silhouette-edge pixels sit nearer each centre."""
    votes = [0, 0]
    for p in _edge_pixels(rgba, width, height):
        votes[_dist(p, centres[1]) < _dist(p, centres[0])] += 1
    return votes


def knockout(rgba: bytes, width: int, height: int, ground: tuple[int, int, int] | None = None):
    """(alpha, dominant colour, knockout colour) when the opaque ink holds two distinct flat colours, else None.

    A white glyph on a blue tile keys to a solid tile; this reads the tile as the icon and the glyph as its
    hole. Two-means over opaque pixels; the alpha is the keyed alpha scaled by how near each pixel sits to
    the dominant colour along the line to the other one. The dominant (ink) colour is the one on the
    silhouette's edge — a tile meets the page, its cut-out does not, whichever covers more or sits farther
    from the ground. Only an edge that does not decide falls back to the colour farther from `ground`, then
    to the colour covering more.
    """
    opaque = [tuple(rgba[i:i + 3]) for i in range(0, len(rgba), 4) if rgba[i + 3] >= OPAQUE]
    if len(opaque) < 4:
        return None
    first = opaque[0]
    second = max(opaque, key=lambda p: _dist(p, first))
    centres = [first, second]
    for _ in range(8):
        groups = ([], [])
        for p in opaque:
            groups[_dist(p, centres[1]) < _dist(p, centres[0])].append(p)
        if not groups[0] or not groups[1]:
            return None
        centres = [_mean(groups[0]), _mean(groups[1])]
    edge = _edge_votes(rgba, width, height, centres)
    if edge[0] != edge[1]:
        big, small = (0, 1) if edge[0] > edge[1] else (1, 0)
    elif ground is not None:
        big, small = (0, 1) if _dist(centres[0], ground) >= _dist(centres[1], ground) else (1, 0)
    else:
        big, small = (0, 1) if len(groups[0]) >= len(groups[1]) else (1, 0)
    dominant = centres[big]
    # The cut-out's own colour, not its mean with the blended border: the purest quarter of its pixels.
    spread = sorted(groups[small], key=lambda p: _dist(p, dominant))
    other = _mean(spread[(3 * len(spread)) // 4:])
    if len(groups[small]) / len(opaque) < KNOCKOUT_MIN_SHARE or _dist(dominant, other) < KNOCKOUT_MIN_DISTANCE:
        return None
    axis = [o - d for o, d in zip(other, dominant)]
    norm = sum(v * v for v in axis)
    alpha = bytearray()
    for i in range(0, len(rgba), 4):
        t = sum((rgba[i + c] - dominant[c]) * axis[c] for c in range(3)) / norm
        alpha.append(round(rgba[i + 3] * min(1.0, max(0.0, 1.0 - t))))
    return bytes(alpha), dominant, other


def ink_extent(alpha: bytes, width: int, height: int) -> int:
    """The longer side, in px, of the box holding every pixel at alpha >= 128."""
    x0, y0, x1, y1 = _ink_box(alpha, width, height)
    return max(x1 - x0, y1 - y0)


def _edge_pixels(rgba: bytes, width: int, height: int) -> list[tuple[int, int, int]]:
    """The colours of opaque pixels on the silhouette's edge: beside a clear pixel or the frame."""
    out = []
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 4
            if rgba[i + 3] < OPAQUE:
                continue
            if not all(0 <= nx < width and 0 <= ny < height and rgba[(ny * width + nx) * 4 + 3] >= OPAQUE
                       for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))):
                out.append(tuple(rgba[i:i + 3]))
    return out


def enclosed_ground_share(rgba: bytes, ground: tuple[int, int, int], width: int, height: int) -> float:
    """The share of opaque pixels nearer the ground's colour than the ink's: page flood keying could not reach.

    Nearer-than rather than within a tolerance, because a thin cut-out is never pure page once it is resampled
    and JPEG-compressed. The ink is the mean colour of the silhouette's edge — what meets the page — so a light
    cut-out on a dark card is ink-side, not page.
    """
    opaque = [tuple(rgba[i:i + 3]) for i in range(0, len(rgba), 4) if rgba[i + 3] >= OPAQUE]
    edge = _edge_pixels(rgba, width, height)
    if not opaque or not edge:
        return 0.0
    ink = _mean(edge)
    return sum(1 for p in opaque if _dist(p, ground) < _dist(p, ink)) / len(opaque)


def ground_alpha(rgba: bytes, ground: tuple[int, int, int]) -> bytes:
    """The keyed alpha scaled by distance from the ground, the ink's PEAK_PERCENTILE distance full: enclosed page
    reads as a hole, thin as it may be, where a two-colour knockout would never register it."""
    dists = [_dist(rgba[i:i + 3], ground) for i in range(0, len(rgba), 4)]
    ink = sorted(d for i, d in enumerate(dists) if rgba[i * 4 + 3] >= OPAQUE and d >= GROUND_NEAR)
    if not ink:
        return bytes(len(dists))
    peak = ink[min(int(len(ink) * PEAK_PERCENTILE), len(ink) - 1)]
    return bytes(round(rgba[i * 4 + 3] * min(1.0, d / peak)) for i, d in enumerate(dists))


def edge_share(rgba: bytes, width: int, height: int, ink, other) -> float:
    """The share of the silhouette's edge pixels nearer `other` than `ink`: 0 for a colour cut out of the ink."""
    votes = _edge_votes(rgba, width, height, (ink, other))
    return votes[1] / sum(votes) if sum(votes) else 0.0


def readings(knockout_colour, ground, enclosed_share: float = 0.0, knockout_edge_share: float = 1.0) -> list[str]:
    """Which silhouettes of a keyed source are judged: `ground`, `alpha`, `knockout`, or alpha and knockout.

    Enough enclosed page (`enclosed_ground_share`) makes the ground reading the only one: the filled alpha
    would let a disc stand in for a mark with bars cut out of it.

    A knockout whose second colour is the ground's, or that never meets the silhouette's edge, is a cut-out, so
    the knockout is the only honest silhouette; judging the filled alpha too lets a filled circle
    stand in for a mark with a play arrow cut out of it.
    """
    if ground is not None and enclosed_share >= ENCLOSED_MIN_SHARE:
        return ["ground"]
    if knockout_colour is None:
        return ["alpha"]
    if ground is not None and _dist(knockout_colour, ground) < KNOCKOUT_MIN_DISTANCE:
        return ["knockout"]
    if knockout_edge_share < KNOCKOUT_EDGE_MAX:  # never meets the page: a cut-out, not a second part of the mark
        return ["knockout"]
    return ["alpha", "knockout"]


def decide(named: str, render: bytes, fit: float, adversaries: dict, source: bytes,
           bar: float, margin: float, min_weight: float) -> dict:
    """The verdict for one named candidate against its adversaries: {accepted, reason, fit, runner_up, margin, weight}.

    `adversaries` maps slug → (render, fit); equivalents are already removed.
    """
    pairs = {slug: pair_margin(source, render, other) for slug, (other, _) in adversaries.items()}
    return decide_pairs(named, fit, pairs, bar, margin, min_weight)


def decide_pairs(named: str, fit: float, pairs: dict, bar: float, margin: float, min_weight: float) -> dict:
    """`decide` over already-measured `pair_margin`s (slug → (t, weight)); the eval re-scores stored pairs with it.

    The runner-up reported is the adversary the source sides with most — the one that decided a refusal, or
    came closest to one.
    """
    verdict = {"named": named, "fit": round(fit, 4), "runner_up": None, "margin": None, "weight": None}
    if fit < bar:
        return {**verdict, "accepted": False, "reason": "bar"}
    worst = None
    for slug, (t, weight) in pairs.items():
        key = (weight >= min_weight, t)  # an indistinguishable adversary is worse than any beaten one
        if worst is None or key < worst[0]:
            worst = (key, slug, t, weight)
    if worst is None:
        return {**verdict, "accepted": False, "reason": "no-adversary"}
    _, slug, t, weight = worst
    verdict.update(runner_up=slug, margin=round(t, 4), weight=round(weight, 2))
    if weight < min_weight:
        return {**verdict, "accepted": False, "reason": "indistinguishable"}
    if t < margin:
        return {**verdict, "accepted": False, "reason": "adversary"}
    return {**verdict, "accepted": True, "reason": None}


def colour_matches(measured: tuple[int, int, int], hex_value: str, tolerance: float) -> bool:
    """Whether a measured flat colour is the brand's own hex, within an RGB distance."""
    brand = tuple(int(hex_value.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return _dist(measured, brand) <= tolerance


def hex_colour(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{v:02X}" for v in rgb)


BRAND_COLOUR_TOLERANCE = 60  # RGB distance within which a measured colour is the brand's own hex


def emission(lib: str, color_mode: str, dominant, knockout_colour, brand_hex: str | None) -> dict:
    """How a verified replacement is painted: {fills, backplate, refused} (DEC-0182).

    `currentColor` paints nothing itself. In original colour a Material glyph takes the measured colour; a
    brand mark only ever takes its own hex, and a source drawn in some other colour is refused rather than
    recoloured. A knockout keeps its second colour as a backplate under the icon.
    """
    if color_mode == "currentColor":
        return {"fills": None, "backplate": None, "refused": None}
    backplate = hex_colour(knockout_colour) if knockout_colour is not None else None
    if LIBRARY_TRADEMARK.get(lib):
        if brand_hex is None or not colour_matches(dominant, brand_hex, BRAND_COLOUR_TOLERANCE):
            return {"fills": None, "backplate": None, "refused": "brand-colour"}
        return {"fills": ["#" + brand_hex.upper()], "backplate": backplate, "refused": None}
    return {"fills": [hex_colour(dominant)], "backplate": backplate, "refused": None}


def header_lines(lib: str, slug: str, version: str, weight: int | None, meta: dict) -> list[str]:
    """The provenance comment a replaced component carries: library, slug, version, licence, and for a brand
    mark the trademark note with its guidelines."""
    if lib == "material":
        return [f"Material Symbols {version} outlined/{slug}, weight {weight} (@material-symbols/svg-{weight}).",
                "Apache-2.0, Copyright Google LLC. Generated by image-to-component --replace."]
    title = meta.get("title", slug)
    guidelines = meta.get("guidelines")
    return [f"simple-icons {version} icons/{slug}.svg ({title}). Icon data CC0-1.0.",
            f"{title} is a trademark of its owner — follow its brand guidelines"
            + (f": {guidelines}" if guidelines else "."),
            "Generated by image-to-component --replace."]
