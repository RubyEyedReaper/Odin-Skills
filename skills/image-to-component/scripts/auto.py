"""Search a small, fixed grid of flags for one asset and name the smallest SVG that passes every check.

Needs vtracer, resvg-py and Pillow (run through toolchain.sh `i2c_py auto`) and SVGO through npx.
The decisions — prep rules, the grid, the winner — are `autogrid.py`, stdlib and unit-tested; this
file only runs them.

    auto.py <image> <work-dir> --kind icon|logo|illustration --report search.json
            [--mono] [--crop x,y,w,h] [--bg auto|none|#rrggbb] [--allow-background] [--seconds N]
            [--iou N] [--mae N] [--edge-f1 N] [--jaggedness N] [--staircase N]

The QA flags are i2c.sh's, passed through so the search chooses against the bars the re-run applies.

One process: the source is keyed once, every candidate is traced in-process, SVGO runs once over the
whole candidate directory, and each result is checked (`svgcheck`) and scored (`diffmetric`) exactly as
`i2c.sh` would. It writes the flags only; `i2c.sh --auto` re-runs the winner through the ordinary
stages, so no artifact comes from a second code path.

stdout: the chosen candidate's i2c.sh flags, one per line — or, on exit 1, the nearest miss's.
Exit codes: 0 a candidate passed; 1 none did (the report names the nearest miss and why);
2 usage, unreadable input, a tool failure, or the --seconds bound reached before the grid finished.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

from PIL import Image

from . import autogrid, diffmetric, edges, prep, svgcheck, trace
from .render_diff import paint_black, render

DEFAULT_SECONDS = 300


def _svgo(src_dir: str, dst_dir: str) -> None:
    skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    version = os.environ.get("I2C_SVGO", "svgo@4.1.0")
    subprocess.run(["npx", "--yes", version, "--quiet", "--config", os.path.join(skill, "scripts", "svgo.config.mjs"),
                    "-f", src_dir, "-o", dst_dir], check=True)


def _within(started: float, seconds: float, doing: str) -> None:
    if time.monotonic() - started > seconds:
        raise TimeoutError(f"--seconds {seconds:g} reached before {doing}")


def _score(svg_text: str, reference: Image.Image, mono: bool, scale: float, edge: str, thresholds: dict) -> dict:
    rendered = render(svg_text, *reference.size)
    ref = reference
    if mono:
        ref, rendered = paint_black(reference, cut=True), paint_black(rendered)
    return diffmetric.compare(ref.tobytes(), rendered.tobytes(), *ref.size, thresholds=thresholds,
                              scale=scale, source_edge=edge)


def search(args: argparse.Namespace) -> tuple[int, dict]:
    started = time.monotonic()
    import vtracer  # toolchain-only, like trace.py

    # Keying reads only key, matte and tolerance, which no rule derives from the ramp; the ramp is
    # measured on the keyed source and decides the rest.
    shape = autogrid.derive_prep(args.mono, None)
    keyed, edge = prep.keyed_source(args.image, args.crop, args.bg, shape["key"], shape["matte"], shape["tolerance"])
    ramp = edges.edge_ramp(keyed.tobytes(), *keyed.size)
    chosen_prep = autogrid.derive_prep(args.mono, ramp)
    prepared = {}  # scale -> (source, reference); the reference is the one input a candidate's scale changes

    grid = autogrid.candidates(args.kind, args.mono, keyed.size)
    raw, opt = os.path.join(args.work, "raw"), os.path.join(args.work, "opt")
    os.makedirs(raw, exist_ok=True)
    os.makedirs(opt, exist_ok=True)
    for i, cand in enumerate(grid):
        _within(started, args.seconds, f"tracing candidate {i + 1} of {len(grid)}")
        scale = float(cand["scale"])
        if scale not in prepared:
            prepared[scale] = prep.finish(keyed, chosen_prep["sharpen"], scale)
        source, reference = prepared[scale]
        smooth = edges.smoothing_for(cand["smooth"], edge, scale)
        trace_png = os.path.join(args.work, f"c{i:02d}.png")
        prep.trace_input(reference, args.mono, smooth, cand["colors"], source,
                         prep.region_radius(cand["smooth"], args.mono)).save(trace_png)
        vtracer.convert_image_to_svg_py(trace_png, os.path.join(raw, f"c{i:02d}.svg"),
                                        **trace.options(args.kind, args.mono, list(cand["sets"])))
    _svgo(raw, opt)

    results = []
    for i, cand in enumerate(grid):
        _within(started, args.seconds, f"scoring candidate {i + 1} of {len(grid)}")
        with open(os.path.join(opt, f"c{i:02d}.svg"), encoding="utf-8") as fh:
            text = fh.read()
        findings = [f.code for f in svgcheck.check(text, args.kind, args.allow_background)]
        # A budget or safety finding refuses the candidate before QA, as i2c.sh's check stage does.
        scale = float(cand["scale"])
        qa = None if findings else _score(text, prepared[scale][1], args.mono, scale, edge, args.thresholds)
        results.append({"flags": autogrid.to_args(chosen_prep, cand), "bytes": len(text.encode()), "tier": cand["tier"],
                        "check": findings, "qa": qa})

    chosen, nearest = autogrid.select(results)
    report = {
        "derived": {"edge": edge, "edge_ramp": None if ramp is None else round(ramp, 3),
                    "blurred_ramp": autogrid.BLURRED_RAMP, "prep": chosen_prep},
        "grid": [{"flags": r["flags"], "bytes": r["bytes"], "tier": r["tier"], "check": r["check"],
                  "qa": None if r["qa"] is None else {k: r["qa"][k] for k in ("iou", "mae", "edge_f1", "jaggedness", "staircase", "failures")},
                  "pass": autogrid.passes(r)} for r in results],
        "chosen": chosen, "nearest": nearest, "flags": results[nearest]["flags"],
        "seconds": round(time.monotonic() - started, 1), "bound_seconds": args.seconds,
    }
    return (0 if chosen is not None else 1), report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auto", description=__doc__.splitlines()[0])
    parser.add_argument("image")
    parser.add_argument("work")
    parser.add_argument("--kind", required=True, choices=sorted(svgcheck.BUDGETS))
    parser.add_argument("--report", required=True)
    parser.add_argument("--mono", action="store_true")
    parser.add_argument("--crop")
    parser.add_argument("--bg", default="auto")
    parser.add_argument("--allow-background", action="store_true")
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    for name in diffmetric.DEFAULT_THRESHOLDS:
        parser.add_argument(f"--{name.replace('_', '-')}", type=float, default=diffmetric.DEFAULT_THRESHOLDS[name])
    args = parser.parse_args(argv)
    args.thresholds = {name: getattr(args, name) for name in diffmetric.DEFAULT_THRESHOLDS}
    try:
        rc, report = search(args)
    except prep.NothingLeft:
        print("auto: nothing left after keying the background; pass --bg or crop tighter", file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.CalledProcessError) as exc:
        print(f"auto: {exc}", file=sys.stderr)
        return 2
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    verdict = "chose" if rc == 0 else "no candidate passed; nearest miss"
    entry = report["grid"][report["nearest"]]
    why = "" if rc == 0 else " — " + ", ".join(entry["check"] + ((entry["qa"] or {}).get("failures") or []))
    print(f"auto: {verdict} {report['nearest'] + 1} of {len(report['grid'])} in {report['seconds']}s: "
          f"{' '.join(report['flags'])} ({entry['bytes']} bytes){why}", file=sys.stderr)
    print("\n".join(report["flags"]))
    return rc


if __name__ == "__main__":
    sys.exit(main())
