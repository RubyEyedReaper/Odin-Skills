#!/usr/bin/env bash
# The primitives eval: does --primitive fit the right container shape, and never the wrong one?
#
#   run.sh [out-dir]          # default evals/primitives/out
#
# 1. make_sources.py draws the ladder and confusers into <out>/.work/src from parameters, and lists
#    the committed product glyphs and marks as negatives. Nothing is fetched: this eval is offline.
# 2. evaluate.py measure renders every family for every source once; evaluate.py score re-decides
#    with the committed scripts/primitives.json and writes <out>/eval.tsv and <out>/counts.tsv.
#
# Exit 0 = recorded, whatever it scored; 1 = a wrong acceptance anywhere; 2 = toolchain unavailable.
# Calibration is separate and reads the calibrate split only:
#   evaluate.py calibrate <out>/.work/raw.jsonl
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill="$(cd "$here/../.." && pwd)"
out="${1:-$here/out}"
work="$out/.work"
mkdir -p "$work"
# shellcheck source=../../scripts/toolchain.sh
. "$skill/scripts/toolchain.sh"

bash "$skill/scripts/doctor.sh" >/dev/null || { echo "primitives-eval: toolchain unavailable (run scripts/doctor.sh)" >&2; exit 2; }

eval_py() { PYTHONPATH="$skill" uv run --no-project --quiet --with "$I2C_RESVG" --with "$I2C_PILLOW" python3 "$@"; }

eval_py "$here/make_sources.py" "$work/src" || exit 2
eval_py "$here/evaluate.py" measure "$work/src" "$work/raw.jsonl" || exit 2
rc=0
eval_py "$here/evaluate.py" score "$work/raw.jsonl" "$skill/scripts/primitives.json" --split eval \
  --tsv "$out/eval.tsv" >"$out/counts.tsv" || rc=$?

wrong="$(awk -F'\t' '$3 == "WRONG" { n += $4 } END { print n + 0 }' "$out/counts.tsv")"
echo "primitives-eval: wrong acceptances on the eval split: $wrong" >&2
[ "$wrong" -eq 0 ] && [ "$rc" -eq 0 ]
