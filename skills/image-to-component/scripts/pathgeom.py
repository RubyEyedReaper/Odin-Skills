"""Read an SVG path's geometry: absolute polylines per subpath, winding, bounding box, outer contours.

Stdlib only. The replace route needs two things from a library icon's `d`: where its ink is (a
content box, to fit it onto a source), and which subpaths are holes (a knockout mark's backplate is
the icon with its holes filled). Library icons are nonzero-filled, so a hole is a subpath wound
against the contour that holds it; that is the only geometry this module interprets.

Curves are flattened to CURVE_STEPS segments — enough for a sign and a box, not for rendering.
"""
from __future__ import annotations

import math
import re

CURVE_STEPS = 8
NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
SEPARATORS = re.compile(r"[\s,]*")
FLAG = re.compile(r"[01]")
ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
Point = tuple[float, float]


def _commands(d: str):
    """(command letter, argument list) pairs, implicit repeats split out; a bad token is refused.

    A scanner rather than a tokenizer, because an arc's two flags are single digits that may touch the
    number after them ("a1 1 0 011 1"), which no number pattern can split.
    """
    pos, cmd = SEPARATORS.match(d, 0).end(), None
    while pos < len(d):
        if d[pos].isalpha():
            cmd = d[pos]
            if cmd.upper() not in ARITY:
                raise ValueError(f"path data has an unknown command {cmd!r} at {pos}")
            pos = SEPARATORS.match(d, pos + 1).end()
            if cmd in "Zz":
                yield cmd, []
                continue
        elif cmd is None or cmd in "Zz":
            raise ValueError(f"path data has a number with no command before it at {pos}")
        args = []
        for k in range(ARITY[cmd.upper()]):
            pattern = FLAG if cmd in "Aa" and k in (3, 4) else NUMBER
            m = pattern.match(d, pos)
            if m is None:
                raise ValueError(f"command {cmd} needs {ARITY[cmd.upper()]} numbers at {pos}")
            args.append(float(m.group()))
            pos = SEPARATORS.match(d, m.end()).end()
        yield cmd, args
        if cmd == "M":
            cmd = "L"
        elif cmd == "m":
            cmd = "l"


def _cubic(p0: Point, p1: Point, p2: Point, p3: Point) -> list[Point]:
    out = []
    for k in range(1, CURVE_STEPS + 1):
        t = k / CURVE_STEPS
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    out[-1] = p3
    return out


def _quad(p0: Point, p1: Point, p2: Point) -> list[Point]:
    return _cubic(p0, (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1])),
                  (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1])), p2)


def _arc(p0: Point, rx: float, ry: float, phi_deg: float, large: float, sweep: float, p1: Point) -> list[Point]:
    """SVG endpoint arc → centre parameterisation (SVG 1.1 appendix F.6), sampled."""
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0 or p0 == p1:
        return [p1]
    phi = math.radians(phi_deg)
    cos, sin = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = cos * dx + sin * dy, -sin * dx + cos * dy
    scale = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    coef = math.sqrt(max(0.0, num / den)) * (-1 if bool(large) == bool(sweep) else 1)
    cx1, cy1 = coef * rx * y1 / ry, -coef * ry * x1 / rx
    cx = cos * cx1 - sin * cy1 + (p0[0] + p1[0]) / 2
    cy = sin * cx1 + cos * cy1 + (p0[1] + p1[1]) / 2
    start = math.atan2((y1 - cy1) / ry, (x1 - cx1) / rx)
    end = math.atan2((-y1 - cy1) / ry, (-x1 - cx1) / rx)
    delta = end - start
    if sweep and delta < 0:
        delta += 2 * math.pi
    elif not sweep and delta > 0:
        delta -= 2 * math.pi
    out = []
    for k in range(1, CURVE_STEPS + 1):
        a = start + delta * k / CURVE_STEPS
        out.append((cx + rx * math.cos(a) * cos - ry * math.sin(a) * sin,
                    cy + rx * math.cos(a) * sin + ry * math.sin(a) * cos))
    out[-1] = p1
    return out


def _walk(d: str):
    """Yield (subpath index, absolute start point, command, args, points added) for every command."""
    cur = start = (0.0, 0.0)
    last_ctrl, last_cmd = None, ""
    index = -1
    for cmd, a in _commands(d):
        up, rel = cmd.upper(), cmd.islower()
        ox, oy = cur if rel else (0.0, 0.0)
        pts: list[Point]
        ctrl = None
        if up == "M":
            index += 1
            cur = start = (ox + a[0], oy + a[1])
            pts = [cur]
        elif up == "Z":
            pts = [start]
            cur = start
        elif up == "L":
            pts = [(ox + a[0], oy + a[1])]
        elif up == "H":
            pts = [((cur[0] if rel else 0.0) + a[0], cur[1])]
        elif up == "V":
            pts = [(cur[0], (cur[1] if rel else 0.0) + a[0])]
        elif up in "CS":
            if up == "C":
                c1 = (ox + a[0], oy + a[1])
                rest = a[2:]
            else:
                c1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_cmd in "CS" and last_ctrl else cur
                rest = a
            c2, end = (ox + rest[0], oy + rest[1]), (ox + rest[2], oy + rest[3])
            pts, ctrl = _cubic(cur, c1, c2, end), c2
        elif up in "QT":
            if up == "Q":
                c1, end = (ox + a[0], oy + a[1]), (ox + a[2], oy + a[3])
            else:
                c1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_cmd in "QT" and last_ctrl else cur
                end = (ox + a[0], oy + a[1])
            pts, ctrl = _quad(cur, c1, end), c1
        else:  # A
            pts = _arc(cur, a[0], a[1], a[2], a[3], a[4], (ox + a[5], oy + a[6]))
        if index < 0:
            raise ValueError("path data must start with a moveto")
        if up != "M":
            cur = pts[-1]
        last_ctrl, last_cmd = ctrl, up
        yield index, start, cmd, a, pts


def subpaths(d: str) -> list[list[Point]]:
    """Every subpath as an absolute polyline, starting at its moveto point."""
    polys: list[list[Point]] = []
    for index, _, cmd, _, pts in _walk(d):
        if cmd in "Mm":
            polys.append([])
        polys[index].extend(pts)
    return polys


def signed_area(poly: list[Point]) -> float:
    """Shoelace area; the sign is the winding direction."""
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2


def bbox(d: str) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) over every flattened point of every subpath."""
    pts = [p for poly in subpaths(d) for p in poly]
    if not pts:
        raise ValueError("path data has no points")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _num(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def outer(d: str) -> str:
    """The subpaths wound like the largest one, each standing alone: the icon with its holes filled.

    Each kept subpath is re-emitted from its own text with its leading moveto made absolute, so a
    relative `m` that depended on a dropped neighbour still lands where it did.
    """
    pieces: list[list[str]] = []
    for index, start, cmd, args, _ in _walk(d):
        if cmd in "Mm":
            pieces.append([f"M{_num(start[0])} {_num(start[1])}"])
            continue
        pieces[index].append(cmd + " ".join(_num(v) for v in args))
    polys = subpaths(d)
    areas = [signed_area(p) for p in polys]
    largest = max(areas, key=abs)
    return "".join("".join(pieces[i]) for i, a in enumerate(areas) if a * largest > 0)
