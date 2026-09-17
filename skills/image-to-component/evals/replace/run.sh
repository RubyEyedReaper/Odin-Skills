#!/usr/bin/env bash
# The replacement eval: does --replace put the right library icon in, and never the wrong one?
#
#   run.sh [out-dir]          # default evals/replace/out
#
# 1. make_sources.py synthesises the ladder, confusers and negatives from the pinned libraries into
#    <out>/.work (never committed: library artwork is fetched, not vendored).
# 2. evaluate.py measure renders every candidate once; evaluate.py score re-decides with the committed
#    scripts/replace.json and writes <out>/eval.tsv (per naming) and <out>/counts.tsv (the table).
# 3. The held-out marks and glyphs run through replace_run with the names a person reading them would give;
#    <out>/heldout.tsv records replaced / refused and the runner-up. Held-out is scored, never calibrated on.
#
# Exit 0 = recorded, whatever it scored; 1 = a wrong replacement anywhere; 2 = toolchain or library unavailable.
# Calibration is separate and reads the calibrate split only: evaluate.py calibrate <out>/.work/raw.jsonl
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill="$(cd "$here/../.." && pwd)"
out="${1:-$here/out}"
work="$out/.work"
mkdir -p "$work" "$out/heldout"
# shellcheck source=../../scripts/toolchain.sh
. "$skill/scripts/toolchain.sh"

bash "$skill/scripts/doctor.sh" >/dev/null || { echo "replace-eval: toolchain unavailable (run scripts/doctor.sh)" >&2; exit 2; }
i2c_lib_fetch || exit 2

eval_py() { PYTHONPATH="$skill" uv run --no-project --quiet --with "$I2C_RESVG" --with "$I2C_PILLOW" python3 "$@"; }

eval_py "$here/make_sources.py" "$work/src" || exit 2
eval_py "$here/evaluate.py" measure "$work/src" "$work/raw.jsonl" || exit 2
eval_py "$here/evaluate.py" score "$work/raw.jsonl" "$skill/scripts/replace.json" --split eval --tsv "$out/eval.tsv" \
  >"$out/counts.tsv" || exit 2

# Held-out: asset, names, colour mode, kind. The names are what the asset visibly is; a mark the library draws
# differently (the pre-2023 Facebook square) is still named, because falling through is the expected answer.
heldout=(
  "facebook-mark.low|simple-icons:facebook|original|logo"
  "facebook-banner-mark.low|simple-icons:facebook|original|logo"
  "alert-mark.low|material:error-fill|original|logo"
  "x-glyph.low|simple-icons:x|currentColor|icon"
  "clock-glyph.low|material:schedule|currentColor|icon"
  "thermometer-glyph.low|material:device_thermostat,material:thermostat|currentColor|icon"
)
pascal() { awk -F'[-.]' '{ for (i = 1; i <= NF; i++) printf "%s%s", toupper(substr($i, 1, 1)), substr($i, 2) }' <<< "$1"; }
printf 'asset\tnames\texit\taccepted\treason\tnamed\tfit\trunner_up\tmargin\tweight\tinterpretation\n' >"$out/heldout.tsv"
for row in "${heldout[@]}"; do
  IFS='|' read -r asset names color kind <<< "$row"
  name="$(pascal "$asset")"
  find "$out/heldout" -maxdepth 1 -name "$name.*" -delete
  args=("$skill/evals/heldout/src/$asset.png" --refs "$names" --report "$out/heldout/$name.replacement.json"
        --name "$name" --kind "$kind" --out "$out/heldout")
  [ "$color" = currentColor ] && args+=(--mono)
  rc=0; i2c_py replace_run "${args[@]}" 2>"$work/$name.log" || rc=$?
  [ "$rc" -eq 2 ] && { cat "$work/$name.log" >&2; exit 2; }
  python3 - "$out/heldout/$name.replacement.json" "$asset" "$names" "$rc" >>"$out/heldout.tsv" <<'PY'
import json, sys
path, asset, names, rc = sys.argv[1:]
r = json.load(open(path))
print("\t".join([asset, names, rc] + [str(r.get(k)) for k in ("accepted", "reason", "named", "fit", "runner_up", "margin", "weight", "interpretation")]))
PY
done

wrong="$(awk -F'\t' '$3 == "WRONG" { n += $4 } END { print n + 0 }' "$out/counts.tsv")"
echo "replace-eval: wrong replacements on the eval split: $wrong" >&2
[ "$wrong" -eq 0 ]
