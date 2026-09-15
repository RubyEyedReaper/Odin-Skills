#!/usr/bin/env bash
# Regenerate the degraded evals: the RubyTech assets at half size, blurred, noisy and JPEG-soft
# (make_sources.py), plus the wrench as a transparent PNG. Each must pass every stage, agree with
# a frozen trace of the clean crop in truth/, and stay under the jaggedness limit its own QA enforces.
# Outputs land in evals/degraded/out/; out/summary.tsv is the before/after record.
#
#   run.sh [out-dir]    # default evals/degraded/out; a scratch dir for experiments
#
# Exit codes: 0 every expectation held; 1 an expectation failed; 2 toolchain unavailable.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill="$(cd "$here/../.." && pwd)"
# The clean RubyTech traces, frozen: agreement against the live goldens would move every time a flag
# change improves the clean set, and a before/after needs one fixed truth. Copied from
# evals/rubytech/out/ at the soft-matte flags, whose silhouettes follow the source's half-coverage
# edge; the hard-keyed goldens before them were fattened by the glow halo (README).
clean="$here/truth"
out="${1:-$here/out}"
mkdir -p "$out"
# shellcheck source=../../scripts/toolchain.sh
. "$skill/scripts/toolchain.sh"

bash "$skill/scripts/doctor.sh" >/dev/null || { echo "degraded: toolchain unavailable (run scripts/doctor.sh)" >&2; exit 2; }

# Silhouette agreement with truth/, bounding-box normalised (see agreement.py). Every glyph traced
# at the old flags (hard key) agrees 0.57-0.66; the best single threshold any per-pixel method can
# put on a degraded glyph's distance map reaches 0.75-0.89. README records both.
AGREEMENT_MIN=0.68

glyph=(--kind icon --key global --matte soft --tolerance 25 --scale 8 --smooth 1.5 --color currentColor)
brand=(--kind logo --scale 4 --colors 32 --matte soft --set filter_speckle=12 --set layer_difference=12)

failed=0
eval_py() { uv run --no-project --quiet --with "$I2C_RESVG" --with "$I2C_PILLOW" python3 "$@"; }
printf 'asset\texit\tiou\tmae\tedge_f1\tjaggedness\tagreement_iou\tsvg_bytes\n' >"$out/summary.tsv"
expect() {  # expect <rc> <label> <Name> <clean Name> -- <i2c args...>
  local want="$1" label="$2" name="$3" golden="$4"; shift 5
  local rc=0 agree=""
  bash "$skill/scripts/i2c.sh" "$@" --name "$name" --out "$out" >"$out/.$label.log" 2>&1 || rc=$?
  # A refused run can still leave the SVG the refusing stage read; scoring it would put a number
  # in the record for an asset that shipped nothing.
  [ -f "$out/$name.svg" ] && [ "$rc" -eq 0 ] &&
    agree="$(eval_py "$here/agreement.py" "$out/$name.svg" "$clean/$golden.svg" | sed -n 's/.*"agreement_iou": \([0-9.]*\).*/\1/p')"
  python3 - "$out/$name.qa.json" "$label" "$rc" "${agree:--}" >>"$out/summary.tsv" <<'PY'
import json, os, sys
path, label, rc, agree = sys.argv[1:]
q = json.load(open(path)) if rc != "2" and os.path.exists(path) else {}
print("\t".join([label, rc] + [str(q.get(k, "-")) for k in ("iou", "mae", "edge_f1", "jaggedness")]
                + [agree, str(q.get("svg_bytes", "-"))]))
PY
  if [ "$rc" -ne "$want" ]; then
    echo "FAIL  $label: exit $rc, expected $want — see $out/.$label.log"; failed=1
  elif [ "$want" -ne 0 ]; then
    echo "ok    $label (refused, exit $rc: $(grep -o 'FAILED at [a-z]*' "$out/.$label.log"))"
    find "$out" -maxdepth 1 -name "$name.*" ! -name '*.png' -delete
  elif ! awk -v a="$agree" -v m="$AGREEMENT_MIN" 'BEGIN { exit !(a != "" && a + 0 >= m) }'; then
    echo "FAIL  $label: agreement_iou ${agree:-unreadable} below $AGREEMENT_MIN"; failed=1
  else
    echo "ok    $label (agreement $agree)"
  fi
}

for pair in computer-icon:ComputerIcon gear-icon:GearIcon controller-icon:ControllerIcon wrench-icon:WrenchIcon; do
  expect 0 "${pair%%:*}.low" "${pair##*:}" "${pair##*:}" -- "$here/src/${pair%%:*}.low.png" "${glyph[@]}"
done
# Noise and JPEG blocking on a gradient-faceted gem trace as slivers past the logo budget, and a
# flat-colour trace cannot meet mae 12 against a noisy reference. Refused, never loosened.
expect 1 rubytech-mark.low RubyTechMark RubyTechMark -- "$here/src/rubytech-mark.low.png" "${brand[@]}"
# A transparent PNG has no ground to key; auto must notice rather than key the glyph away. Its edge
# is a hard 1px staircase, which --smooth 3 at --scale 8 reproduces step for step; 7 (~0.9 x scale)
# rounds the steps and keeps the jaws and the eye.
expect 0 wrench-icon.alpha WrenchIconAlpha WrenchIcon -- "$here/src/wrench-icon.alpha.png" \
  --kind icon --scale 8 --smooth 7 --color currentColor

column -t -s "$(printf '\t')" "$out/summary.tsv"
[ "$failed" -eq 0 ] && find "$out" -maxdepth 1 -name '.*.log' -delete
exit "$failed"
