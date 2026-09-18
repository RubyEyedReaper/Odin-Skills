#!/usr/bin/env bash
# image-to-component — one raster asset in, a checked SVG and a typed React component out.
#
#   i2c.sh <image> --name <ComponentName> --kind icon|logo|illustration --out <dir>
#          [--crop x,y,w,h] [--bg auto|none|#rrggbb] [--key flood|global] [--matte soft|hard] [--tolerance N] [--scale N] [--smooth auto|R] [--sharpen R] [--colors N]
#          [--color original|currentColor] [--allow-background] [--set key=value]...
#          [--iou N] [--mae N] [--edge-f1 N] [--jaggedness N] [--staircase N] [--features N]
#   i2c.sh <image> --name <ComponentName> --kind icon|logo|illustration --out <dir> --auto
#          [--crop x,y,w,h] [--bg auto|none|#rrggbb] [--color original|currentColor] [--allow-background]
#   either form also takes --replace auto|<lib>:<slug>[,<lib>:<slug>...]
#   and --primitive auto|rect|rounded-rect|circle|ellipse|pill
#
# --replace runs first, before prep's source-quality check: a known icon or brand mark in the source is
# verified against the library icons it could be confused with (scripts/replace_run.py) and, when accepted,
# the library vector is emitted instead of a trace. Nothing accepted → the run continues exactly as without
# the flag. Either way qa.json carries the verdict under "replacement".
# --primitive runs next, and only for an asset that is WHOLLY a container shape — a tile, a badge disc,
# a status pill, a rounded-rect backplate (ADR-0175). Candidacy is a set of predicates over the keyed
# alpha and acceptance is adversarial against the other four families (scripts/primitives_run.py);
# accepted, the fitted <circle>/<rect rx>/<ellipse> is emitted instead of a polygon approximating it.
# Nothing accepted → the run continues exactly as without the flag, and qa.json carries the verdict
# under "primitive". A card, a panel or anything with text is NOT this — see references/rebuild-route.md.
# --auto searches a fixed grid for the kind (scripts/autogrid.py), keeps the smallest SVG that passes
# every check, and runs it through the stages below; qa.json records the grid under "search". It takes
# no tuning flag — choosing them is its job. Nothing passing is exit 1, naming the nearest miss.
# QA flags (--iou …) reach the search too. --search-report <file> is internal: the re-run it makes.
#
# Writes into <dir>: <Name>.src.png (prepared raster), <Name>.svg, <Name>.tsx,
# <Name>.qa.json, <Name>.compare.png. Stages stop at the first failure and name it.
# Exit codes: 0 all stages pass; 1 a check refused (prep source-quality, svgcheck or QA); 2 usage or a tool failed.
# A page or layout is never an input here — see references/rebuild-route.md.
set -euo pipefail

# shellcheck source=toolchain.sh
. "$(dirname "${BASH_SOURCE[0]}")/toolchain.sh"

usage() { sed -n '2,31p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }

[ $# -ge 1 ] || usage
src="$1"; shift
name="" kind="" out="" crop="" bg="auto" key="flood" matte="hard" tolerance="40" scale="1" smooth="auto" sharpen="0" colors="0" color="original" allow_bg="" auto="" search_report="" tuned="" replace="" primitive=""
trace_sets=() qa_args=() pass_through=()
need() { [ $# -ge 2 ] || { echo "i2c: $1 needs a value" >&2; exit 2; }; }
while [ $# -gt 0 ]; do
  case "$1" in
    --name) need "$@"; name="$2"; shift 2 ;;
    --kind) need "$@"; kind="$2"; shift 2 ;;
    --out) need "$@"; out="$2"; shift 2 ;;
    --crop) need "$@"; crop="$2"; pass_through+=(--crop "$2"); shift 2 ;;
    --bg) need "$@"; bg="$2"; pass_through+=(--bg "$2"); shift 2 ;;
    --key) need "$@"; key="$2"; tuned="$1"; shift 2 ;;
    --matte) need "$@"; matte="$2"; tuned="$1"; shift 2 ;;
    --tolerance) need "$@"; tolerance="$2"; tuned="$1"; shift 2 ;;
    --scale) need "$@"; scale="$2"; tuned="$1"; shift 2 ;;
    --smooth) need "$@"; smooth="$2"; tuned="$1"; shift 2 ;;
    --sharpen) need "$@"; sharpen="$2"; tuned="$1"; shift 2 ;;
    --colors) need "$@"; colors="$2"; tuned="$1"; shift 2 ;;
    --color) need "$@"; color="$2"; shift 2 ;;
    --allow-background) allow_bg="--allow-background"; shift ;;
    --set) need "$@"; trace_sets+=(--set "$2"); tuned="$1"; shift 2 ;;
    --auto) auto=1; shift ;;
    --replace) need "$@"; replace="$2"; shift 2 ;;
    --primitive) need "$@"; primitive="$2"; shift 2 ;;
    --search-report) need "$@"; search_report="$2"; shift 2 ;;
    --iou|--mae|--edge-f1|--jaggedness|--staircase|--features) need "$@"; qa_args+=("$1" "$2"); shift 2 ;;
    *) echo "i2c: unknown argument $1" >&2; usage ;;
  esac
done
[ -n "$name" ] && [ -n "$kind" ] && [ -n "$out" ] || usage
# The name becomes a file name and an export identifier; refuse anything that is not both.
[[ "$name" =~ ^[A-Z][A-Za-z0-9]*$ ]] || { echo "i2c: --name must be PascalCase letters and digits, got '$name'" >&2; exit 2; }
[ -f "$src" ] || { echo "i2c: no such image: $src" >&2; exit 2; }
mkdir -p "$out"

stage() { printf 'i2c: %-9s %s\n' "$1" "$2" >&2; }
replacement_report="" primitive_report=""
record_replacement() {
  [ -z "$replacement_report" ] || i2c_stdlib autorecord "$replacement_report" "$out/$name.qa.json" --key replacement
  [ -z "$primitive_report" ] || i2c_stdlib autorecord "$primitive_report" "$out/$name.qa.json" --key primitive
}
fail() { echo "i2c: FAILED at $1 (exit $2)" >&2; record_replacement; exit "$3"; }

prepared="$out/$name.src.png"
work="$(mktemp -d)"
trap 'find "$work" -depth -delete' EXIT
traced="$work/traced.svg"

if [ -n "$replace" ]; then
  stage replace "$replace"
  i2c_lib_fetch || fail replace 2 2
  replace_args=("$src" --refs "$replace" --report "$work/replacement.json" --name "$name" --kind "$kind" --out "$out" "${pass_through[@]}")
  [ "$color" = currentColor ] && replace_args+=(--mono)
  rc=0; i2c_py replace_run "${replace_args[@]}" || rc=$?
  [ "$rc" -eq 0 ] || [ "$rc" -eq 4 ] || fail replace "$rc" 2
  replacement_report="$work/replacement.json"
  if [ "$rc" -eq 0 ]; then
    find "$out" -maxdepth 1 -name "$name.qa.json" -delete
    record_replacement
    stage done "$out/$name.{svg,tsx} (replaced)"
    exit 0
  fi
fi

if [ -n "$primitive" ]; then
  stage primitive "$primitive"
  primitive_args=("$src" --family "$primitive" --report "$work/primitive.json" --name "$name" --kind "$kind"
                  --out "$out" "${pass_through[@]}")
  [ "$color" = currentColor ] && primitive_args+=(--mono)
  rc=0; i2c_py primitives_run "${primitive_args[@]}" || rc=$?
  [ "$rc" -eq 0 ] || [ "$rc" -eq 4 ] || fail primitive "$rc" 2
  primitive_report="$work/primitive.json"
  if [ "$rc" -eq 0 ]; then
    find "$out" -maxdepth 1 -name "$name.qa.json" -delete
    record_replacement
    stage done "$out/$name.{svg,tsx} (fitted primitive)"
    exit 0
  fi
fi

if [ -n "$auto" ]; then
  [ -z "$tuned" ] || { echo "i2c: --auto chooses the tuning flags itself; drop $tuned" >&2; exit 2; }
  auto_args=(--kind "$kind" --report "$work/search.json" "${pass_through[@]}" "${qa_args[@]}")
  [ "$color" = currentColor ] && auto_args+=(--mono)
  [ -n "$allow_bg" ] && auto_args+=(--allow-background)
  stage auto "grid search, $kind"
  rc=0; chosen="$(i2c_py auto "$src" "$work/auto" "${auto_args[@]}")" || rc=$?
  if [ "$rc" -eq 3 ]; then
    # The source was refused before the search: the record names source-quality and its measurement.
    i2c_stdlib autorecord "$work/search.json" "$out/$name.qa.json"
    fail prep 3 1
  fi
  if [ "$rc" -eq 1 ]; then
    # Nothing passed: keep the search as the record and name the nearest miss (auto.py printed it).
    i2c_stdlib autorecord "$work/search.json" "$out/$name.qa.json"
    fail auto 1 1
  fi
  [ "$rc" -eq 0 ] || fail auto "$rc" 2
  mapfile -t flags <<< "$chosen"
  rc=0
  bash "${BASH_SOURCE[0]}" "$src" --name "$name" --kind "$kind" --out "$out" --color "$color" $allow_bg \
    "${pass_through[@]}" "${flags[@]}" "${qa_args[@]}" --search-report "$work/search.json" || rc=$?
  record_replacement
  exit "$rc"
fi

stage prep "$src -> $prepared"
prep_args=("$src" "$prepared" --trace-input "$work/trace.png" --edge-report "$work/edge" --colors "$colors" --smooth "$smooth" --sharpen "$sharpen" --bg "$bg" --key "$key" --matte "$matte" --tolerance "$tolerance" --scale "$scale")
[ -n "$crop" ] && prep_args+=(--crop "$crop")
binary=() mono=()
[ "$color" = currentColor ] && { prep_args+=(--mono); binary=(--binary); mono=(--mono); }
rc=0; i2c_py prep "${prep_args[@]}" || rc=$?
[ "$rc" -eq 3 ] && fail prep 3 1   # source-quality: a refusal, not a tool failure
[ "$rc" -eq 0 ] || fail prep "$rc" 2

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
  --sheet "$out/$name.compare.png" --scale "$scale" --source-edge "$(cat "$work/edge")" \
  "${mono[@]}" "${qa_args[@]}" || rc=$?
[ -z "$search_report" ] || i2c_stdlib autorecord "$search_report" "$out/$name.qa.json"
[ "$rc" -eq 0 ] || fail qa "$rc" "$([ "$rc" -eq 1 ] && echo 1 || echo 2)"

record_replacement
stage done "$out/$name.{svg,tsx}"
