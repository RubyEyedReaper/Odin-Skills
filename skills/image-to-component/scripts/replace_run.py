"""Run the replace route for one source: recognise a library icon, verify it against adversaries, emit it.

Needs resvg-py and Pillow (run through toolchain.sh `i2c_py replace_run`). Every decision is stdlib
(`replace.py`, `library.py`, `scale.py`); this file only reads the libraries, renders and writes.

    replace_run.py <image> --refs auto|<lib>:<slug>[,...] --report replacement.json
                   [--crop x,y,w,h] [--bg auto|none|#rrggbb] [--mono]
                   [--name Pascal --kind icon|logo --out dir]

Steps, each the same for the named candidate and for every adversary (DEC-0178, DEC-0179):

1. Key the source once (`prep.keyed_source`). Its silhouette is read two ways: the keyed alpha, and —
   when its ink holds two flat colours — the knockout (`replace.knockout`), where a white glyph on a tile
   is the tile's hole.
2. Shortlist adversaries from the library index by thumbnail distance (`replace.shortlist`).
3. Fit each candidate onto the source by moments, render it supersampled, box-reduce it to source size and
   blur it by the sigma whose edge ramp matches the source's. The source is never cleaned.
4. `replace.decide`: the named candidate must clear the bar and beat every distinguishable adversary by the
   margin. `auto` names the best-fitting shortlist entry and holds it to `auto_margin`.

With --out, an accepted replacement writes <Name>.svg, <Name>.tsx and <Name>.compare.png. The report is
always written: `i2c.sh` files it into qa.json under `replacement`.

Exit codes: 0 replaced; 4 no candidate accepted (the run continues to the trace route unchanged);
2 usage, unreadable input, a library missing from the cache, or a render failure.
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import subprocess
import sys

import resvg_py
from PIL import Image, ImageFilter

from . import autogrid, edges, keying, library, pathgeom, prep, replace, scale, svg2tsx, svgcheck
from .render_diff import sheet

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SUPERSAMPLE = 4
INDEX_PX = 64
INDEX_VERSION = 2
SCALE_STEPS = (0.88, 0.94, 1.0, 1.06)  # moments fit the size to within a few percent; each candidate gets its best
SHEET_PX = 192  # a compare sheet panel is at least this tall, nearest-neighbour upscaled


def _render_alpha(svg_text: str, width: int, height: int) -> Image.Image:
    png = resvg_py.svg_to_bytes(svg_string=svg_text, width=width, height=height)
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA").getchannel("A")


def _icon_svg(icon: library.Icon, view_box: tuple[float, float, float, float]) -> str:
    return library.to_svg(library.Icon(view_box, icon.paths))


# ---------------------------------------------------------------- libraries

def _index_path(cache: str, pins: dict, lib: str) -> str:
    return f"{library.package_dir(cache, pins, lib)}/i2c-index-v{INDEX_VERSION}.json"


def _load_icon(path: str) -> library.Icon | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return library.normalise(fh.read())
    except (OSError, ValueError):
        return None


def build_index(cache: str, pins: dict, lib: str) -> dict:
    """slug → index row for every icon the library ships, built once per version and cached beside it."""
    path = _index_path(cache, pins, lib)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    folder = os.path.dirname(library.icon_file(cache, pins, lib, "x"))
    if not os.path.isdir(folder):
        raise OSError(f"{lib} {pins[lib]} is not in {cache}: run toolchain.sh i2c_lib_fetch")
    index = {}
    for file in sorted(glob.glob(f"{folder}/*.svg")):
        icon = _load_icon(file)
        if icon is None:
            continue
        side = max(icon.view_box[2], icon.view_box[3])
        vb = (icon.view_box[0], icon.view_box[1], side, side)
        alpha = _render_alpha(_icon_svg(icon, vb), INDEX_PX, INDEX_PX).tobytes()
        entry = library.index_entry(alpha, INDEX_PX, INDEX_PX, vb)
        if entry is not None:
            index[os.path.basename(file)[:-4]] = entry
    tmp = path + ".partial"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(index, fh, separators=(",", ":"))
    os.replace(tmp, path)
    return index


def brand_meta(cache: str, pins: dict, slug: str) -> dict:
    with open(f"{library.package_dir(cache, pins, 'simple-icons')}/package/data/simple-icons.json", encoding="utf-8") as fh:
        for entry in json.load(fh):
            if entry.get("slug") == slug:
                return entry
    return {}


# ---------------------------------------------------------------- source

class Source:
    """One silhouette interpretation of the keyed source, with the measures a fit and a shortlist need."""

    def __init__(self, kind: str, alpha: bytes, width: int, height: int):
        self.kind, self.alpha, self.width, self.height = kind, alpha, width, height
        self.cx, self.cy, self.r, _ = library.moments(alpha, width, height)
        self.aspect = library.descriptors(alpha, width, height)["aspect"]
        self.thumb = library.thumbnail(alpha, width, height, library.THUMB_SIZE)
        rgba = b"".join(bytes((0, 0, 0, a)) for a in alpha)
        self.ramp = edges.edge_ramp(rgba, width, height)


def interpretations(keyed: Image.Image, ground: tuple | None = None) -> tuple[list[Source], tuple | None, tuple | None]:
    """(sources, dominant colour, knockout colour): the alpha reading always, the knockout one when present."""
    width, height = keyed.size
    rgba = keyed.tobytes()
    opaque = [tuple(rgba[i:i + 3]) for i in range(0, len(rgba), 4) if rgba[i + 3] >= replace.OPAQUE]
    dominant = tuple(sorted(p[c] for p in opaque)[len(opaque) // 2] for c in range(3)) if opaque else (0, 0, 0)
    ko = replace.knockout(rgba, width, height, ground)
    share = replace.enclosed_ground_share(rgba, ground, width, height) if ground is not None else 0.0
    edge = replace.edge_share(rgba, width, height, ko[1], ko[2]) if ko else 1.0
    kinds = replace.readings(ko[2] if ko else None, ground, share, edge)
    buffers = {"alpha": keyed.getchannel("A").tobytes(), "knockout": ko[0] if ko else None,
               "ground": replace.ground_alpha(rgba, ground) if "ground" in kinds else None}
    if "ground" in kinds:
        ink = [p for p in opaque if replace._dist(p, ground) >= replace.GROUND_NEAR]
        if ink:
            dominant = tuple(sorted(p[c] for p in ink)[len(ink) // 2] for c in range(3))
        return [Source("ground", buffers["ground"], width, height)] if any(v >= 128 for v in buffers["ground"]) else [], dominant, None
    sources = []
    for kind in kinds:
        try:
            sources.append(Source(kind, buffers[kind], width, height))
        except ValueError:  # a reading with no ink at alpha 128 has nothing to fit
            continue
    return (sources, ko[1], ko[2]) if ko else (sources, dominant, None)


# ---------------------------------------------------------------- rendering

class Renderer:
    def __init__(self, cache: str, pins: dict, indexes: dict, sigmas: list[float], gamma: float):
        self.cache, self.pins, self.indexes, self.sigmas, self.gamma = cache, pins, indexes, sigmas, gamma
        self.icons: dict[str, library.Icon] = {}

    def icon(self, ref: str, weight: int = library.DEFAULT_WEIGHT) -> library.Icon:
        key = f"{ref}@{weight}"
        if key not in self.icons:
            lib, slug = ref.split(":", 1)
            icon = _load_icon(library.icon_file(self.cache, self.pins, lib, slug, weight))
            if icon is None:
                raise OSError(f"{ref} (weight {weight}) is not a library icon in {self.cache}")
            self.icons[key] = icon
        return self.icons[key]

    def transform(self, ref: str, src: Source, sigma: float, step: float = 1.0) -> tuple[float, float, float]:
        lib, slug = ref.split(":", 1)
        return scale.fit(self.indexes[lib][slug], (src.cx, src.cy, replace.unblurred_radius(src.r, sigma) * step))

    def clean(self, ref: str, src: Source, sigma: float, weight: int = library.DEFAULT_WEIGHT,
              step: float = 1.0, supersample: int = SUPERSAMPLE) -> Image.Image:
        """The fitted candidate at `supersample` × source size, unblurred."""
        vb = scale.canvas_view_box(self.transform(ref, src, sigma, step), src.width, src.height)
        return _render_alpha(_icon_svg(self.icon(ref, weight), vb), src.width * supersample, src.height * supersample)

    def best_fit(self, ref: str, src: Source, sigma: float) -> tuple[Image.Image, bytes, float, float]:
        """(clean, degraded, fit, step) at the SCALE_STEPS size that fits the source best."""
        best = None
        for step in SCALE_STEPS:
            clean = self.clean(ref, src, sigma, step=step)
            degraded = self.degrade(clean, src, sigma)
            fit = replace.soft_iou(src.alpha, degraded)
            if best is None or fit > best[2]:
                best = (clean, degraded, fit, step)
        return best

    def degrade(self, clean: Image.Image, src: Source, sigma: float) -> bytes:
        """Box-reduce to source size, blur by sigma, and stretch as the source's keying stretched it."""
        small = clean.resize((src.width, src.height), Image.BOX)
        blurred = small.filter(ImageFilter.GaussianBlur(sigma)) if sigma > 0 else small
        return replace.normalise_peak(blurred.tobytes(), self.gamma)

    def sigma_for(self, ref: str, src: Source) -> float:
        """The blur whose degraded render of `ref` has an edge ramp nearest the source's."""
        ramps = {}
        for sigma in self.sigmas:
            alpha = self.degrade(self.clean(ref, src, sigma), src, sigma)
            ramp = edges.edge_ramp(b"".join(bytes((0, 0, 0, a)) for a in alpha), src.width, src.height)
            if ramp is not None:
                ramps[sigma] = ramp
        return replace.choose_sigma(src.ramp, ramps) if ramps else 0.0


# ---------------------------------------------------------------- verification

COARSE = 400             # thumbnail-nearest entries re-ranked by a real render at source size
COARSE_ASPECT_LIMIT = 0.6  # a blurred thin stroke's alpha-128 box is far from its clean aspect


def _shortlist(renderer: "Renderer", src: Source, k: int) -> tuple[list[str], float]:
    """(the k entries whose quick render fits the source best, the sigma they were rendered at).

    Thumbnails alone rank a soft 12 px source badly — a blob is near everything — and the shortlist is what
    puts the true icon among the adversaries, so it is re-ranked by a fitted, degraded render.
    """
    merged = {f"{lib}:{slug}": entry for lib, index in renderer.indexes.items() for slug, entry in index.items()}
    coarse = replace.shortlist(merged, src.thumb, src.aspect, COARSE, aspect_limit=COARSE_ASPECT_LIMIT)
    if not coarse:
        return [], 0.0
    sigma = renderer.sigma_for(coarse[0], src)
    quick = []
    for ref in coarse:
        try:
            quick.append((-replace.soft_iou(src.alpha, renderer.degrade(renderer.clean(ref, src, sigma, supersample=2), src, sigma)), ref))
        except (OSError, KeyError):
            continue
    quick.sort()
    return [ref for _, ref in quick[:k]], sigma


def gather(renderer: Renderer, src: Source, refs: list[str] | None, params: dict) -> dict:
    """Every candidate this interpretation is judged against, rendered once: the shortlist plus any named refs.

    The blur is estimated from the shortlist's nearest entry, never from the name, so the adversaries a
    source is compared with — and how they are degraded — do not depend on what the agent called it.
    """
    pool, sigma = _shortlist(renderer, src, params["shortlist"])
    if not pool and not refs:
        return {}
    sigma = renderer.sigma_for(pool[0] if pool else refs[0], src)
    out = {"src": src, "sigma": sigma, "pool": pool, "clean": {}, "degraded": {}, "fits": {}, "steps": {}}
    for ref in dict.fromkeys(list(refs or ()) + pool):
        try:
            clean, degraded, fit, step = renderer.best_fit(ref, src, sigma)
        except (OSError, KeyError):
            continue
        out["clean"][ref], out["degraded"][ref], out["fits"][ref], out["steps"][ref] = clean, degraded, fit, step
    return out


def adversaries_of(gathered: dict, ref: str, equivalent: float) -> dict:
    """slug → (degraded render, fit) for every gathered candidate that is not `ref` or a render-equivalent of it."""
    reference = gathered["clean"][ref].tobytes()
    return {other: (gathered["degraded"][other], gathered["fits"][other]) for other in gathered["degraded"]
            if other != ref and not replace.equivalent(reference, gathered["clean"][other].tobytes(), equivalent)}


def judge(gathered: dict, refs: list[str] | None, params: dict) -> dict | None:
    """The verdict for this interpretation: each named ref in turn (the best reported), or the best-fitting under auto."""
    if not gathered:
        return None
    fits = gathered["fits"]
    if refs is None and replace.ink_extent(gathered["src"].alpha, gathered["src"].width, gathered["src"].height) < params["auto_min_px"]:
        return {"named": None, "fit": 0.0, "runner_up": None, "margin": None, "weight": None, "accepted": False,
                "reason": "auto-too-small", "interpretation": gathered["src"].kind, "mode": "auto"}
    if refs is None:
        named, margin = sorted((r for r in gathered["pool"] if r in fits), key=lambda ref: -fits[ref])[:1], params["auto_margin"]
    else:
        named, margin = [ref for ref in refs if ref in fits], params["margin"]
    best = None
    for ref in named:
        verdict = replace.decide(ref, gathered["degraded"][ref], fits[ref], adversaries_of(gathered, ref, params["equivalent"]),
                                 gathered["src"].alpha, params["bar"], margin, params["min_weight"])
        verdict.update(interpretation=gathered["src"].kind, sigma=gathered["sigma"], step=gathered["steps"][ref],
                       mode="auto" if refs is None else "named")
        if best is None or (verdict["accepted"], verdict["fit"]) > (best["accepted"], best["fit"]):
            best = verdict
    return best


def verify(renderer: Renderer, sources: list[Source], refs: list[str] | None, params: dict) -> tuple[dict, Source | None]:
    """The best verdict over the source's interpretations, each judged independently against its own adversaries."""
    best = None
    for src in sources:
        verdict = judge(gather(renderer, src, refs, params), refs, params)
        if verdict is not None and (best is None or (verdict["accepted"], verdict["fit"]) > (best[0]["accepted"], best[0]["fit"])):
            best = (verdict, src)
    if best is None:
        return {"accepted": False, "reason": "no-candidate"}, None
    return best


# ---------------------------------------------------------------- emission

def choose_weight(renderer: Renderer, ref: str, src: Source, sigma: float, step: float) -> dict:
    """Material weight from the source's measured stroke ratio against each weight's own render at source size."""
    lib, slug = ref.split(":", 1)
    if lib != "material":
        return {"material_weight": None}
    subprocess.run(["bash", "-c", f'. "{SCRIPTS}/toolchain.sh" && i2c_lib_fetch {" ".join(map(str, library.MATERIAL_WEIGHTS))}'],
                   check=True, stdout=subprocess.DEVNULL)
    ratios = {}
    for weight in library.MATERIAL_WEIGHTS:
        alpha = renderer.degrade(renderer.clean(ref, src, sigma, weight, step), src, sigma)
        try:
            ratios[weight] = scale.stroke_ratio(alpha, src.width, src.height)
        except ValueError:
            continue
    measured = scale.stroke_ratio(src.alpha, src.width, src.height)
    return {"material_weight": scale.nearest_weight(measured, ratios), "stroke_ratio": round(measured, 4),
            "weight_ratios": {str(w): round(r, 4) for w, r in ratios.items()}}


def emit(renderer: Renderer, verdict: dict, src: Source, colours: tuple, args: argparse.Namespace,
         scales: dict) -> dict:
    """Write the replacement's SVG, TSX and compare sheet; returns what the record adds."""
    ref, sigma, step = verdict["named"], verdict["sigma"], verdict["step"]
    lib, slug = ref.split(":", 1)
    version = renderer.pins[lib]
    color_mode = "currentColor" if args.mono else "original"
    meta = brand_meta(renderer.cache, renderer.pins, slug) if lib == "simple-icons" else {}
    dominant, knockout_colour = colours
    painted = replace.emission(lib, color_mode, dominant, knockout_colour if src.kind == "knockout" else None,
                               meta.get("hex"))
    record = {"library": lib, "slug": slug, "version": version, "licence": library.LIBRARIES[lib]["licence"],
              "emission": painted}
    if painted["refused"]:
        return {**record, "refused": painted["refused"]}
    record.update(choose_weight(renderer, ref, src, sigma, step))
    icon = renderer.icon(ref, record["material_weight"] or library.DEFAULT_WEIGHT)
    px = scale.rendered_px(renderer.transform(ref, src, sigma, step), icon.view_box)
    size = scale.snap(px, scales["icon_px"], scales["snap_tolerance"])
    record["size"] = {k: round(v, 3) if isinstance(v, float) else v for k, v in size.items()}
    backplate = (pathgeom.outer(" ".join(icon.paths)), painted["backplate"]) if painted["backplate"] else None
    svg = library.to_svg(icon, painted["fills"], backplate)
    findings = [f.code for f in svgcheck.check(svg, args.kind)]
    if findings:
        return {**record, "refused": "check:" + ",".join(findings)}
    header = replace.header_lines(lib, slug, version, record["material_weight"], meta)
    tsx = svg2tsx.convert(svg, args.name, color_mode, header=header, size=size["value"])
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, f"{args.name}.svg"), "w", encoding="utf-8") as fh:
        fh.write(svg + "\n")
    with open(os.path.join(args.out, f"{args.name}.tsx"), "w", encoding="utf-8") as fh:
        fh.write(tsx)
    _compare_sheet(renderer, ref, src, sigma, step, record["material_weight"] or library.DEFAULT_WEIGHT).save(
        os.path.join(args.out, f"{args.name}.compare.png"))
    return record


def _compare_sheet(renderer: Renderer, ref: str, src: Source, sigma: float, step: float, weight: int) -> Image.Image:
    def panel(alpha: bytes) -> Image.Image:
        img = Image.new("RGBA", (src.width, src.height), (255, 255, 255, 255))
        img.putalpha(Image.frombytes("L", (src.width, src.height), alpha))
        k = max(1, -(-SHEET_PX // src.height))
        return img.resize((src.width * k, src.height * k), Image.NEAREST)
    degraded = renderer.degrade(renderer.clean(ref, src, sigma, weight, step), src, sigma)
    return sheet(panel(src.alpha), panel(degraded))


# ---------------------------------------------------------------- main

def gamma_for(mono: bool) -> float:
    """A glyph is keyed globally with the coverage gamma; a colour source's matte is linear."""
    return keying.COVERAGE_GAMMA if mono else 1.0


def load_sources(image: str, crop: str | None, bg: str, mono: bool) -> tuple[list[Source], tuple, tuple | None]:
    """Key the source the way `--auto` keys it for this colour mode, and read its interpretations."""
    shape = autogrid.derive_prep(mono, None)
    keyed, _ = prep.keyed_source(image, crop, bg, shape["key"], shape["matte"], shape["tolerance"])
    raw = prep._open(image, crop)
    ground = keying.border_background(raw.tobytes(), *raw.size) if bg == "auto" else prep._background(bg, raw)
    return interpretations(keyed, ground)


def open_libraries(refs) -> tuple[str, dict, dict]:
    """(cache, pins, indexes) for every library, built into the cache on first use."""
    pins = library.pins(os.environ)
    cache = os.environ["I2C_LIB_CACHE"]
    return cache, pins, {lib: build_index(cache, pins, lib) for lib in sorted(library.LIBRARIES)}


def run(args: argparse.Namespace) -> tuple[int, dict]:
    refs = library.parse_refs(args.refs)
    params = replace.load_params(os.path.join(SCRIPTS, "replace.json"))
    scales = scale.load(os.path.join(SCRIPTS, "scales.json"))
    cache, pins, indexes = open_libraries(refs)
    wanted = sorted(indexes)
    sources, dominant, knockout_colour = load_sources(args.image, args.crop, args.bg, args.mono)
    renderer = Renderer(cache, pins, indexes, params["sigmas"], gamma_for(args.mono))
    ref_names = [f"{lib}:{slug}" for lib, slug in refs] if refs else None
    for ref in ref_names or ():
        lib, slug = ref.split(":", 1)
        if slug not in indexes[lib]:
            raise ValueError(f"--replace {ref}: {lib} {pins[lib]} has no icon '{slug}'")
    verdict, src = verify(renderer, sources, ref_names, params)
    report = {**verdict, "libraries": {lib: f"{lib}@{pins[lib]}" for lib in wanted}}
    if not verdict["accepted"]:
        return 4, report
    if args.out:
        record = emit(renderer, verdict, src, (dominant, knockout_colour), args, scales)
        report.update(record)
        if record.get("refused"):
            return 4, {**report, "accepted": False, "reason": record["refused"]}
    return 0, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="replace_run", description=__doc__.splitlines()[0])
    parser.add_argument("image")
    parser.add_argument("--refs", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--crop")
    parser.add_argument("--bg", default="auto")
    parser.add_argument("--mono", action="store_true")
    parser.add_argument("--name")
    parser.add_argument("--kind", default="icon", choices=sorted(svgcheck.BUDGETS))
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if args.out and not args.name:
        print("replace_run: --out needs --name", file=sys.stderr)
        return 2
    try:
        rc, report = run(args)
    except prep.NothingLeft:
        rc, report = 4, {"accepted": False, "reason": "nothing-left-after-keying"}
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"replace_run: {exc}", file=sys.stderr)
        return 2
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    if rc == 0:
        print(f"replace_run: replaced by {report['named']} (fit {report['fit']}, runner-up {report['runner_up']} "
              f"at margin {report['margin']})", file=sys.stderr)
    else:
        print(f"replace_run: no replacement ({report.get('reason')}; nearest {report.get('named')}, "
              f"runner-up {report.get('runner_up')})", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
