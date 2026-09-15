"""Turn an optimized SVG into a typed React component.

Stdlib only. The input is the narrow dialect vtracer + SVGO produce — `svg`, `g` and `path` with
paint, geometry and transform attributes — and nothing else is transcribed: any other element or
attribute is refused by name (exit 1). A general converter such as SVGR buys nothing here, and an
offline converter is the only one the gated suite can exercise. Hand-authored SVG is a component to
write, not one to run through this (#1352).

    python3 -m scripts.svg2tsx in.svg --name RubyTechLogo [--color currentColor] --out Out.tsx
    python3 -m scripts.svg2tsx --barrel <dir>      # writes <dir>/index.ts from *.tsx names

Exit codes: 0 written, 1 input refused (unsafe or unscalable), 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

from .svgcheck import FORBIDDEN, is_external, parse_view_box

SVG_NS = "http://www.w3.org/2000/svg"
COLOR_MODES = ("original", "currentColor")
DROPPED = {"title", "desc", "metadata"}
ELEMENTS = {"svg", "g", "path"}
ATTRS = {"d", "fill", "fill-rule", "fill-opacity", "opacity", "stroke", "transform"}
PAINT_ATTRS = {"fill", "stroke"}
ROOT_DROPPED_ATTRS = {"width", "height", "version", "x", "y", "enable-background"}
ROOT_ATTRS = ATTRS | ROOT_DROPPED_ATTRS | {"viewBox", "xmlns"}
NO_PAINT = {"none", "transparent", "currentColor", "inherit"}
INDENT = "  "
IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def component_name(raw: str) -> str:
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", raw) if p]
    if not parts:
        raise ValueError(f"cannot derive a component name from {raw!r}")
    name = "".join(p[:1].upper() + p[1:] for p in parts)
    return f"Svg{name}" if name[0].isdigit() else name


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _jsx_attr_name(name: str) -> str:
    return re.sub(r"-([a-z])", lambda m: m.group(1).upper(), name)


def _jsx_value(value: str) -> str:
    if '"' in value or "{" in value or "}" in value:
        return "{" + json.dumps(value) + "}"
    return f'"{value}"'


def _refuse_outside_dialect(el: ET.Element, allowed: set[str]) -> None:
    tag = _local(el.tag)
    if tag not in ELEMENTS:
        raise ValueError(f"<{tag}> is outside the dialect svg2tsx transcribes (svg, g, path from vtracer + SVGO);"
                         " write this component by hand")
    for attr in el.attrib:
        if attr not in allowed:
            raise ValueError(f"attribute {attr!r} on <{tag}> is outside the dialect svg2tsx transcribes"
                             f" ({', '.join(sorted(allowed))})")


def _refuse_unsafe(el: ET.Element) -> None:
    tag = _local(el.tag)
    if tag in FORBIDDEN:
        raise ValueError(f"<{tag}> is not allowed in a generated component (run svgcheck)")
    for attr, value in el.attrib.items():
        if _local(attr).lower().startswith("on"):
            raise ValueError(f"event handler attribute {attr!r} is not allowed")
        if is_external(_local(attr), value):
            raise ValueError(f"external reference {attr}={value!r} is not allowed")


def _attrs(el: ET.Element, color_mode: str, skip: set[str]) -> list[str]:
    out = []
    for name, value in el.attrib.items():
        if name in skip:
            continue
        if color_mode == "currentColor" and name in PAINT_ATTRS and value not in NO_PAINT:
            value = "currentColor"
        out.append(f"{_jsx_attr_name(name)}={_jsx_value(value)}")
    return out


def _render(el: ET.Element, color_mode: str, depth: int) -> list[str]:
    _refuse_unsafe(el)
    tag = _local(el.tag)
    if tag in DROPPED:
        return []
    _refuse_outside_dialect(el, ATTRS)
    pad = INDENT * depth
    attrs = " ".join(_attrs(el, color_mode, set()))
    head = f"<{tag}{' ' + attrs if attrs else ''}"
    children = [line for child in el for line in _render(child, color_mode, depth + 1)]
    if not children:
        return [f"{pad}{head} />"]
    lines = [f"{pad}{head}>"]
    lines.extend(children)
    lines.append(f"{pad}</{tag}>")
    return lines


def _view_box(root: ET.Element) -> str:
    view_box = root.get("viewBox")
    if view_box is not None:
        if parse_view_box(view_box) is None:
            raise ValueError(f"viewBox {view_box!r} is not four numbers")
        return " ".join(view_box.replace(",", " ").split())
    width, height = root.get("width"), root.get("height")
    numeric = r"^\s*([0-9.]+)(px)?\s*$"
    if width and height and re.match(numeric, width) and re.match(numeric, height):
        return f"0 0 {re.match(numeric, width).group(1)} {re.match(numeric, height).group(1)}"
    raise ValueError("SVG has no viewBox and no numeric width/height; it cannot scale")


def convert(svg_text: str, name: str, color_mode: str = "original") -> str:
    if color_mode not in COLOR_MODES:
        raise ValueError(f"color_mode must be one of {COLOR_MODES}, got {color_mode!r}")
    try:
        root = ET.fromstring(svg_text.encode() if isinstance(svg_text, str) else svg_text)
    except ET.ParseError as exc:
        raise ValueError(f"SVG does not parse: {exc}") from exc
    if _local(root.tag) != "svg":
        raise ValueError(f"root element is <{_local(root.tag)}>, not <svg>")
    _refuse_unsafe(root)
    _refuse_outside_dialect(root, ROOT_ATTRS)
    view_box = _view_box(root)
    component = component_name(name)

    root_attrs = [f'xmlns="{SVG_NS}"', f'viewBox="{view_box}"']
    # A binary trace carries no paint at all; without a root fill it renders SVG's default black.
    if color_mode == "currentColor" and root.get("fill") is None:
        root_attrs.append('fill="currentColor"')
    root_attrs += _attrs(root, color_mode, ROOT_DROPPED_ATTRS | {"viewBox", "xmlns"})
    root_attrs += [
        'role={labelled ? "img" : undefined}',
        "aria-hidden={labelled ? undefined : true}",
        "aria-labelledby={title ? titleId : undefined}",
        'focusable="false"',
        "{...props}",
    ]
    body = [line for child in root for line in _render(child, color_mode, 3)]
    root_open = "\n".join(f"{INDENT * 3}{a}" for a in root_attrs)

    return "\n".join([
        'import { useId, type SVGProps } from "react";',
        "",
        f"export interface {component}Props extends SVGProps<SVGSVGElement> {{",
        f"{INDENT}/** Accessible name. Omit for decorative use; the icon is then aria-hidden. */",
        f"{INDENT}title?: string;",
        "}",
        "",
        f"export function {component}({{ title, ...props }}: {component}Props) {{",
        f"{INDENT}const titleId = useId();",
        f'{INDENT}const labelled = Boolean(title || props["aria-label"] || props["aria-labelledby"]);',
        f"{INDENT}return (",
        f"{INDENT * 2}<svg",
        root_open,
        f"{INDENT * 2}>",
        f"{INDENT * 3}{{title ? <title id={{titleId}}>{{title}}</title> : null}}",
        *body,
        f"{INDENT * 2}</svg>",
        f"{INDENT});",
        "}",
        "",
        f"export default {component};",
        "",
    ])


def barrel(names: list[str]) -> str:
    bad = [n for n in names if not IDENTIFIER.match(n)]
    if bad:
        raise ValueError(f"not valid export names: {bad}; name components with --name in PascalCase")
    return "".join(f'export {{ {n} }} from "./{n}";\n' for n in sorted(set(names)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="svg2tsx", description=__doc__.splitlines()[0])
    parser.add_argument("svg", nargs="?")
    parser.add_argument("--name")
    parser.add_argument("--color", choices=COLOR_MODES, default="original")
    parser.add_argument("--out")
    parser.add_argument("--barrel", metavar="DIR")
    args = parser.parse_args(argv)

    if args.barrel:
        names = sorted(f[:-4] for f in os.listdir(args.barrel) if f.endswith(".tsx"))
        with open(os.path.join(args.barrel, "index.ts"), "w", encoding="utf-8") as fh:
            fh.write(barrel(names))
        return 0
    if not (args.svg and args.name and args.out):
        parser.print_usage(sys.stderr)
        return 2
    try:
        with open(args.svg, encoding="utf-8") as fh:
            tsx = convert(fh.read(), args.name, args.color)
    except OSError as exc:
        print(f"svg2tsx: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"svg2tsx: refused: {exc}", file=sys.stderr)
        return 1
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(tsx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
