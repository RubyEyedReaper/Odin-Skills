"""Is this SVG safe, scalable, and small enough to ship as a component?

Stdlib only. Findings, not fixes: every finding carries the remedy in its message.

    python3 -m scripts.svgcheck file.svg --kind icon|logo|illustration [--allow-background] [--json]

Exit codes: 0 clean, 1 findings (a parse error is a finding), 2 unreadable file or usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

# Past these, the asset is a layout or a screenshot, not a vector — see rebuild-route.md.
BUDGETS = {
    "icon": {"bytes": 8_000, "paths": 40},
    "logo": {"bytes": 40_000, "paths": 200},
    "illustration": {"bytes": 250_000, "paths": 1_500},
}
# The one deny set; svg2tsx imports it. `use` and `style` can pull external content or rules in.
FORBIDDEN = frozenset({"script", "foreignObject", "image", "iframe", "use", "style"})
EXTERNAL_URL = re.compile(r"url\(\s*['\"]?(?!#)", re.IGNORECASE)
SHAPES = {"path", "rect", "circle", "ellipse", "polygon", "polyline", "line"}
# SVG path grammar: "4.32.01" is two numbers, 4.32 and .01 — SVGO emits exactly that.
PATH_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
REBUILD = ("rebuild it as semantic markup instead of tracing it — "
           "see references/rebuild-route.md")


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_view_box(value: str) -> tuple[float, float, float, float] | None:
    """Exactly four numbers, or None. Anything else is refused, never transcribed."""
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4 or not all(PATH_NUMBER.fullmatch(p) for p in parts):
        return None
    return tuple(float(p) for p in parts)


def is_external(name: str, value: str) -> bool:
    """A reference that leaves the document: a non-# href, or a url() not pointing at #id."""
    return (name == "href" and not value.startswith("#")) or bool(EXTERNAL_URL.search(value))


def _num(value: str | None, default: float = 0.0) -> float:
    try:
        return float(re.sub(r"px$", "", value.strip())) if value is not None else default
    except ValueError:
        return float("nan")


def _is_opaque(el: ET.Element) -> bool:
    fill = el.get("fill", "#000")
    if fill in ("none", "transparent"):
        return False
    for attr in ("opacity", "fill-opacity"):
        if el.get(attr) is not None and _num(el.get(attr)) < 1:
            return False
    return True


def _covers(el: ET.Element, vb: tuple[float, float, float, float]) -> bool:
    x0, y0, w, h = vb
    tag = _local(el.tag)
    if tag == "rect":
        return (_num(el.get("x")) <= x0 and _num(el.get("y")) <= y0
                and _num(el.get("width")) >= w and _num(el.get("height")) >= h)
    if tag == "path":
        nums = [float(n) for n in PATH_NUMBER.findall(el.get("d", ""))]
        cmds = re.sub(r"[-0-9.,\s]", "", el.get("d", "")).upper()
        return cmds in ("MHVHZ", "MHVH", "MLLLZ", "MLLL") and (
            nums[:2] == [x0, y0] and max(nums) >= max(w, h) and w in nums and h in nums)
    return False


def check(svg_text: str, kind: str, allow_background: bool = False) -> list[Finding]:
    if kind not in BUDGETS:
        raise ValueError(f"kind must be one of {sorted(BUDGETS)}; a page or layout is not traced — {REBUILD}")
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        return [Finding("parse-error", f"SVG does not parse: {exc}")]

    findings: list[Finding] = []
    view_box = root.get("viewBox")
    vb = None
    if not view_box:
        findings.append(Finding("no-viewbox", "no viewBox: the asset cannot scale; add one from width/height"))
    else:
        vb = parse_view_box(view_box)
        if vb is None:
            findings.append(Finding("bad-viewbox", f"viewBox {view_box!r} is not four numbers"))

    shapes = 0
    for el in root.iter():
        tag = _local(el.tag)
        if tag in FORBIDDEN:
            findings.append(Finding("forbidden-element", f"<{tag}> is not allowed: embedded rasters, "
                                    "scripts and foreign content defeat vectorization and are unsafe"))
        for attr, value in el.attrib.items():
            name = _local(attr)
            if name.lower().startswith("on"):
                findings.append(Finding("event-handler", f"{name} on <{tag}>: remove event handler attributes"))
            if tag not in FORBIDDEN and is_external(name, value):
                findings.append(Finding("external-ref", f"<{tag} {name}={value!r}>: only same-document #refs are allowed"))
        if tag in SHAPES:
            shapes += 1
            if vb and not allow_background and _is_opaque(el) and _covers(el, vb):
                findings.append(Finding("opaque-background", f"<{tag}> covers the whole viewBox with an opaque fill: "
                                        "remove the background, or pass --allow-background if it is part of the design"))

    budget = BUDGETS[kind]
    size = len(svg_text.encode())
    if size > budget["bytes"]:
        findings.append(Finding("budget-bytes", f"{size} bytes exceeds the {kind} budget of {budget['bytes']}: "
                                f"raise filter_speckle/corner threshold, or {REBUILD}"))
    if shapes > budget["paths"]:
        findings.append(Finding("budget-paths", f"{shapes} shapes exceeds the {kind} budget of {budget['paths']}: "
                                f"reduce colour_precision, or {REBUILD}"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="svgcheck", description=__doc__.splitlines()[0])
    parser.add_argument("svg")
    parser.add_argument("--kind", required=True, choices=sorted(BUDGETS))
    parser.add_argument("--allow-background", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.svg, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"svgcheck: {exc}", file=sys.stderr)
        return 2
    findings = check(text, args.kind, args.allow_background)
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        for f in findings:
            print(f"{args.svg}: {f.code}: {f.message}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
