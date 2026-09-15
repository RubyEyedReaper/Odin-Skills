#!/usr/bin/env bash
# image-to-component — one raster asset in, a checked SVG and a typed React component out.
#
#   i2c.sh <image> --name <ComponentName> --kind icon|logo|illustration --out <dir>
#          [--crop x,y,w,h] [--bg auto|none|#rrggbb] [--key flood|global] [--matte soft|hard] [--tolerance N] [--scale N] [--smooth R] [--colors N]
#          [--color original|currentColor] [--allow-background] [--set key=value]...
#          [--iou N] [--mae N] [--edge-f1 N] [--jaggedness N]
#
# Writes into <dir>: <Name>.src.png (prepared raster), <Name>.svg, <Name>.tsx,
# <Name>.qa.json, <Name>.compare.png. Stages stop at the first failure and name it.
# Exit codes: 0 all stages pass; 1 a check failed (svgcheck or QA); 2 usage or a tool failed.
# A page or layout is never an input here — see references/rebuild-route.md.
set -euo pipefail

# shellcheck source=toolchain.sh
. "$(dirname "${BASH_SOURCE[0]}")/toolchain.sh"

usage() { sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }

[ $# -ge 1 ] || usage
src="$1"; shift
name="" kind="" out="" crop="" bg="auto" key="flood" matte="hard" tolerance="40" scale="1" smooth="0" colors="0" color="original" allow_bg=""
trace_sets=() qa_args=()
need() { [ $# -ge 2 ] || { echo "i2c: $1 needs a value" >&2; exit 2; }; }
while [ $# -gt 0 ]; do
  case "$1" in
    --name) need "$@"; name="$2"; shift 2 ;;
    --kind) need "$@"; kind="$2"; shift 2 ;;
    --out) need "$@"; out="$2"; shift 2 ;;
    --crop) need "$@"; crop="$2"; shift 2 ;;
    --bg) need "$@"; bg="$2"; shift 2 ;;
    --key) need "$@"; key="$2"; shift 2 ;;
    --matte) need "$@"; matte="$2"; shift 2 ;;
    --tolerance) need "$@"; tolerance="$2"; shift 2 ;;
    --scale) need "$@"; scale="$2"; shift 2 ;;
    --smooth) need "$@"; smooth="$2"; shift 2 ;;
    --colors) need "$@"; colors="$2"; shift 2 ;;
    --color) need "$@"; color="$2"; shift 2 ;;
    --allow-background) allow_bg="--allow-background"; shift ;;
    --set) need "$@"; trace_sets+=(--set "$2"); shift 2 ;;
    --iou|--mae|--edge-f1|--jaggedness) need "$@"; qa_args+=("$1" "$2"); shift 2 ;;
    *) echo "i2c: unknown argument $1" >&2; usage ;;
  esac
done
[ -n "$name" ] && [ -n "$kind" ] && [ -n "$out" ] || usage
# The name becomes a file name and an export identifier; refuse anything that is not both.
[[ "$name" =~ ^[A-Z][A-Za-z0-9]*$ ]] || { echo "i2c: --name must be PascalCase letters and digits, got '$name'" >&2; exit 2; }
[ -f "$src" ] || { echo "i2c: no such image: $src" >&2; exit 2; }
mkdir -p "$out"

stage() { printf 'i2c: %-9s %s\n' "$1" "$2" >&2; }
fail() { echo "i2c: FAILED at $1 (exit $2)" >&2; exit "$3"; }

prepared="$out/$name.src.png"
work="$(mktemp -d)"
trap 'find "$work" -depth -delete' EXIT
traced="$work/traced.svg"

stage prep "$src -> $prepared"
prep_args=("$src" "$prepared" --trace-input "$work/trace.png" --colors "$colors" --smooth "$smooth" --bg "$bg" --key "$key" --matte "$matte" --tolerance "$tolerance" --scale "$scale")
[ -n "$crop" ] && prep_args+=(--crop "$crop")
binary=() mono=()
[ "$color" = currentColor ] && { prep_args+=(--mono); binary=(--binary); mono=(--mono); }
i2c_py prep "${prep_args[@]}" || fail prep $? 2

stage trace "$kind preset"
i2c_py trace "$work/trace.png" "$traced" --kind "$kind" "${binary[@]}" "${trace_sets[@]}" || fail trace $? 2

stage optimize "svgo -> $out/$name.svg"
i2c_svgo "$traced" "$out/$name.svg" || fail optimize $? 2

stage check "svgcheck --kind $kind"
rc=0; i2c_stdlib svgcheck "$out/$name.svg" --kind "$kind" $allow_bg || rc=$?
[ "$rc" -eq 0 ] || fail check "$rc" 1

stage generate "$out/$name.tsx ($color)"
rc=0; i2c_stdlib svg2tsx "$out/$name.svg" --name "$name" --color "$color" --out "$out/$name.tsx" || rc=$?
[ "$rc" -eq 0 ] || fail generate "$rc" 1

stage qa "render + diff"
rc=0; i2c_py render_diff "$prepared" "$out/$name.svg" --report "$out/$name.qa.json" \
  --sheet "$out/$name.compare.png" "${mono[@]}" "${qa_args[@]}" || rc=$?
[ "$rc" -eq 0 ] || fail qa "$rc" "$([ "$rc" -eq 1 ] && echo 1 || echo 2)"

stage done "$out/$name.{svg,tsx}"
