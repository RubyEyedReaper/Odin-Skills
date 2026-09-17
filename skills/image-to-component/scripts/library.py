"""Pinned icon libraries for the replace route: references, cache layout, normalised markup, silhouette geometry.

Stdlib only. Two libraries, both fill-only single-path icons, so a replacement stays inside the dialect
`svg2tsx` transcribes (#1352) without widening it:

| Library | Package | Licence | What it covers |
|---|---|---|---|
| `simple-icons` | `simple-icons` | CC0-1.0 data; the marks are trademarks of their owners | brand marks |
| `material` | `@material-symbols/svg-<weight>`, outlined | Apache-2.0 | generic glyphs, weights 100–700 |

Versions are pinned once, in `toolchain.sh`, and reach this module through the environment
(`I2C_SIMPLE_ICONS`, `I2C_MATERIAL`); a missing pin is refused, never defaulted, so there is no second
copy of a version here to drift. `toolchain.sh` `i2c_lib_fetch` unpacks each package into
`<cache>/<package>@<version>/package/` with `npm pack`. Nothing is vendored.

The geometry helpers (`moments`, `descriptors`, `thumbnail`) read an alpha-only byte buffer, one byte per
pixel, and are shared by the index a library is searched through and the source being matched against it.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .svgcheck import parse_view_box

LIBRARIES = {
    "simple-icons": {"env": "I2C_SIMPLE_ICONS", "licence": "CC0-1.0", "trademark": True},
    "material": {"env": "I2C_MATERIAL", "licence": "Apache-2.0", "trademark": False},
}
MATERIAL_WEIGHTS = (100, 200, 300, 400, 500, 600, 700)
DEFAULT_WEIGHT = 400
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SVG_NS = "http://www.w3.org/2000/svg"
VISIBLE = 128
THUMB_SPREAD = 2.5  # a thumbnail window spans the ink's centroid ± this many radii of gyration
THUMB_SIZE = 16     # an index thumbnail is THUMB_SIZE × THUMB_SIZE
THUMB_BLURS = (0.0, 0.6, 1.2, 1.8)  # thumbnail-cell sigmas an index row is stored at: a small source's thumbnail is soft


@dataclass(frozen=True)
class Icon:
    view_box: tuple[float, float, float, float]
    paths: tuple[str, ...]


def parse_refs(text: str) -> list[tuple[str, str]] | None:
    """`lib:slug[,lib:slug...]` → pairs; `auto` → None (search every library). Anything else is refused."""
    if text == "auto":
        return None
    refs = []
    for part in text.split(","):
        lib, sep, slug = part.partition(":")
        if not sep or lib not in LIBRARIES or not SLUG.match(slug):
            raise ValueError(f"--replace wants auto or <library>:<slug> with library in {sorted(LIBRARIES)} "
                             f"and a lower-case slug, got {part!r}")
        refs.append((lib, slug))
    return refs


def pins(environ) -> dict[str, str]:
    """Library → version, from the pins toolchain.sh exports. A missing pin is an error, not a default."""
    out = {}
    for lib, spec in LIBRARIES.items():
        value = environ.get(spec["env"])
        if not value:
            raise ValueError(f"{spec['env']} is not set: library versions are pinned in scripts/toolchain.sh")
        out[lib] = value.rpartition("@")[2]
    return out


def package_dir(cache: str, pins_: dict[str, str], lib: str, weight: int = DEFAULT_WEIGHT) -> str:
    if lib == "simple-icons":
        return f"{cache}/simple-icons@{pins_[lib]}"
    if weight not in MATERIAL_WEIGHTS:
        raise ValueError(f"Material Symbols publishes weights {MATERIAL_WEIGHTS}, not {weight}")
    return f"{cache}/material-symbols-svg-{weight}@{pins_[lib]}"


def icon_file(cache: str, pins_: dict[str, str], lib: str, slug: str, weight: int = DEFAULT_WEIGHT) -> str:
    folder = "icons" if lib == "simple-icons" else "outlined"
    return f"{package_dir(cache, pins_, lib, weight)}/package/{folder}/{slug}.svg"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalise(svg_text: str) -> Icon:
    """A library icon as its viewBox and path data. Refuses anything but `svg` > `path d` (+ `title`)."""
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise ValueError(f"library icon does not parse: {exc}") from exc
    view_box = parse_view_box(root.get("viewBox") or "")
    if _local(root.tag) != "svg" or view_box is None:
        raise ValueError("library icon has no <svg viewBox> of four numbers")
    paths = []
    for child in root:
        tag = _local(child.tag)
        if tag == "title":
            continue
        if tag != "path" or set(child.attrib) != {"d"} or len(child):
            raise ValueError(f"library icon carries <{tag} {' '.join(sorted(child.attrib))}>, "
                             "outside the single-path shape the replace route emits")
        paths.append(child.get("d"))
    if not paths:
        raise ValueError("library icon has no path")
    return Icon(view_box, tuple(paths))


def _num(v: float) -> str:
    return f"{v:g}"


def to_svg(icon: Icon, fills: list[str] | None = None, backplate: tuple[str, str] | None = None) -> str:
    """Dialect markup: optional backplate path first, then the icon's paths, each with its fill if given."""
    parts = [f'<svg xmlns="{SVG_NS}" viewBox="{" ".join(_num(v) for v in icon.view_box)}">']
    if backplate is not None:
        parts.append(f'<path d="{backplate[0]}" fill="{backplate[1]}"/>')
    for i, d in enumerate(icon.paths):
        fill = f' fill="{fills[min(i, len(fills) - 1)]}"' if fills else ""
        parts.append(f'<path d="{d}"{fill}/>')
    parts.append("</svg>")
    return "".join(parts)


def moments(alpha: bytes, width: int, height: int) -> tuple[float, float, float, float]:
    """(centroid x, centroid y, radius of gyration, mass in opaque pixels), alpha-weighted.

    Each pixel is a unit box, not a point: its own variance, 1/12 per axis, is added, so a shape and the
    same shape drawn at twice the size have radii exactly 2:1 rather than drifting with pixel count.
    """
    rows = [sum(alpha[y * width:(y + 1) * width]) for y in range(height)]
    cols = [sum(alpha[x::width]) for x in range(width)]
    total = sum(rows)
    if total == 0:
        raise ValueError("no ink: the alpha buffer is empty")
    cx = sum((x + 0.5) * v for x, v in enumerate(cols)) / total
    cy = sum((y + 0.5) * v for y, v in enumerate(rows)) / total
    var = (sum((x + 0.5 - cx) ** 2 * v for x, v in enumerate(cols))
           + sum((y + 0.5 - cy) ** 2 * v for y, v in enumerate(rows))) / total + 2 / 12
    return cx, cy, var ** 0.5, total / 255


def _ink_box(alpha: bytes, width: int, height: int) -> tuple[int, int, int, int]:
    xs = [i % width for i, v in enumerate(alpha) if v >= VISIBLE]
    ys = [i // width for i, v in enumerate(alpha) if v >= VISIBLE]
    if not xs:
        raise ValueError("no ink: nothing reaches alpha 128")
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def descriptors(alpha: bytes, width: int, height: int) -> dict:
    """Aspect (w/h) and fill ratio of the alpha >= 128 ink box, and how many holes the ink encloses."""
    x0, y0, x1, y1 = _ink_box(alpha, width, height)
    w, h = x1 - x0, y1 - y0
    ink = [[alpha[y * width + x] >= VISIBLE for x in range(x0, x1)] for y in range(y0, y1)]
    # Ground connected to the frame around the ink box is open; every other clear component is a hole.
    grid = [[False] * (w + 2)] + [[False] + row + [False] for row in ink] + [[False] * (w + 2)]
    seen = [[False] * (w + 2) for _ in range(h + 2)]
    holes = 0
    for sy in range(h + 2):
        for sx in range(w + 2):
            if grid[sy][sx] or seen[sy][sx]:
                continue
            stack, border = [(sx, sy)], False
            seen[sy][sx] = True
            while stack:
                x, y = stack.pop()
                border |= x in (0, w + 1) or y in (0, h + 1)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w + 2 and 0 <= ny < h + 2 and not grid[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            holes += not border
    return {"aspect": w / h, "fill": sum(map(sum, ink)) / (w * h), "holes": holes}


def _overlaps(lo: float, cell: float, count: int, limit: int) -> list[list[tuple[int, float]]]:
    """For each of `count` cells of width `cell` from `lo`: the (pixel index, overlap length) pairs inside [0, limit)."""
    out = []
    for i in range(count):
        a, b = lo + i * cell, lo + (i + 1) * cell
        out.append([(p, min(b, p + 1) - max(a, p)) for p in range(max(0, int(a // 1)), min(limit, int(-(-b // 1))))
                    if min(b, p + 1) > max(a, p)])
    return out


def thumbnail(alpha: bytes, width: int, height: int, size: int) -> bytes:
    """A size×size area-averaged alpha map of the ink, windowed on its centroid ± THUMB_SPREAD radii.

    Normalising on moments rather than on a thresholded box is what lets a blurred 12 px source and a
    crisp library render land in the same frame: blur moves an alpha-128 edge, not a centroid.
    """
    cx, cy, r, _ = moments(alpha, width, height)
    half = max(r * THUMB_SPREAD, 0.5)
    cell = 2 * half / size
    xs, ys = _overlaps(cx - half, cell, size, width), _overlaps(cy - half, cell, size, height)
    area = cell * cell
    out = bytearray()
    for row in ys:
        for col in xs:
            acc = sum(alpha[py * width + px] * wy * wx for py, wy in row for px, wx in col)
            out.append(min(255, round(acc / area)))
    return bytes(out)


def blur_thumb(thumb: bytes, size: int, sigma: float) -> bytes:
    """A size×size thumbnail under a separable Gaussian of `sigma` cells (ink outside is clear), rescaled so its
    peak stays where the crisp thumbnail's was — a blurred source is keyed to full ink, not to a lower peak."""
    if sigma <= 0:
        return bytes(thumb)
    radius = max(1, int(3 * sigma + 0.999))
    kernel = [2.718281828459045 ** (-(i * i) / (2 * sigma * sigma)) for i in range(-radius, radius + 1)]
    total = sum(kernel)
    kernel = [k / total for k in kernel]

    def run(values: list[float], step_x: int, step_y: int) -> list[float]:
        out = [0.0] * (size * size)
        for y in range(size):
            for x in range(size):
                acc = 0.0
                for i, k in enumerate(kernel):
                    nx, ny = x + (i - radius) * step_x, y + (i - radius) * step_y
                    if 0 <= nx < size and 0 <= ny < size:
                        acc += values[ny * size + nx] * k
                out[y * size + x] = acc
        return out

    blurred = run(run([float(v) for v in thumb], 1, 0), 0, 1)
    peak, top = max(blurred), max(thumb)
    if peak <= 0:
        return bytes(len(thumb))
    return bytes(min(255, round(v * top / peak)) for v in blurred)


def index_entry(alpha: bytes, width: int, height: int, view_box: tuple[float, float, float, float]) -> dict | None:
    """One icon's index row, from its alpha rendered to fill `view_box` at width × height px.

    Centroid and radius are in viewBox units, so a fit can place the icon on any source without
    rendering it first; descriptors and thumbnail describe the silhouette. None when nothing is inked.
    """
    if not any(alpha):
        return None
    cx, cy, r, _ = moments(alpha, width, height)
    unit = view_box[2] / width
    entry = {"cx": round(view_box[0] + cx * unit, 4), "cy": round(view_box[1] + cy * unit, 4),
             "r": round(r * unit, 4)}
    try:
        entry.update({k: (round(v, 4) if isinstance(v, float) else v)
                      for k, v in descriptors(alpha, width, height).items()})
    except ValueError:  # faint ink that never reaches alpha 128 has moments but no box
        return None
    thumb = thumbnail(alpha, width, height, THUMB_SIZE)
    entry["thumbs"] = [blur_thumb(thumb, THUMB_SIZE, sigma).hex() for sigma in THUMB_BLURS]
    entry["thumb"] = entry["thumbs"][0]
    return entry
