#!/usr/bin/env bash
# The held-out eval: ten assets from the RubyTech mockups that no preset, flag or threshold was ever
# tuned on, each clean and degraded (make_sources.py). Every run uses only its SKILL.md starting row —
# never a flag picked for the asset — so the pass rate says how the skill does on an image nobody has
# looked at. Outputs land in evals/heldout/out/; out/summary.tsv is the record.
#
#   run.sh [out-dir] [-- extra i2c args...]   # default evals/heldout/out; extra args go to every run
#   run.sh [out-dir] -- --auto                # the same set with no row flags at all: kind and colour only
#
# The rate is a measurement, not an expectation: exit 0 means every run completed and was recorded,
# whatever it scored. Exit 1 = a run failed as a tool (i2c exit 2); exit 2 = toolchain unavailable.
# FREEZE RULE (README): nothing in the skill is tuned by reading this set's per-asset results.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill="$(cd "$here/../.." && pwd)"
out="$here/out"
if [ $# -gt 0 ] && [ "$1" != "--" ]; then out="$1"; shift; fi
[ $# -gt 0 ] && [ "$1" = "--" ] && shift
extra=("$@")
mkdir -p "$out"
# shellcheck source=../../scripts/toolchain.sh
. "$skill/scripts/toolchain.sh"

bash "$skill/scripts/doctor.sh" >/dev/null || { echo "heldout: toolchain unavailable (run scripts/doctor.sh)" >&2; exit 2; }

# The SKILL.md starting rows, verbatim, by asset class. A degraded source is the "blurred, JPEG-soft
# or <= 32 px" glyph row and the "noisy or JPEG-soft" logo row; a clean crop gets the plain row.
glyph_clean=(--kind icon --key global --matte soft --color currentColor --scale 8)
glyph_low=(--kind icon --key global --matte soft --tolerance 25 --color currentColor --scale 8 --smooth 1.5 --sharpen 0.8)
mark_clean=(--kind logo --scale 2 --colors 32 --matte soft)
mark_low=(--kind logo --scale 2 --colors 64 --matte soft --set filter_speckle=7)
# --auto takes no tuning flag, so under it every class keeps only what the asset is: kind and colour.
if [[ " ${extra[*]} " == *" --auto "* ]]; then
  glyph_clean=(--kind icon --color currentColor) glyph_low=(--kind icon --color currentColor)
  mark_clean=(--kind logo) mark_low=(--kind logo)
fi

eval_py() { uv run --no-project --quiet --with "$I2C_RESVG" --with "$I2C_PILLOW" python3 "$@"; }
pascal() { awk -F- '{ for (i = 1; i <= NF; i++) printf "%s%s", toupper(substr($i, 1, 1)), substr($i, 2) }' <<< "$1"; }

toolfail=0 passed=0 total=0
printf 'asset\texit\tfailed_at\tiou\tmae\tedge_f1\tjaggedness\tstaircase\tagreement_iou\tsvg_bytes\n' >"$out/summary.tsv"
run() {  # run <label> <Name> <agree-with Name or -> <src> <i2c args...>
  local label="$1" name="$2" golden="$3" src="$4"; shift 4
  local rc=0 agree="-" failed_at="-" log="$out/.$label.log"
  find "$out" -maxdepth 1 -name "$name.*" -delete
  bash "$skill/scripts/i2c.sh" "$src" "$@" "${extra[@]}" --name "$name" --out "$out" >"$log" 2>&1 || rc=$?
  total=$((total + 1))
  if [ "$rc" -eq 0 ]; then
    passed=$((passed + 1))
    # Context, never a bar: a degraded glyph's silhouette against its clean crop's trace, when that passed.
    if [ "$golden" != "-" ] && [ -f "$out/$golden.svg" ]; then
      agree="$(eval_py "$skill/evals/degraded/agreement.py" "$out/$name.svg" "$out/$golden.svg" | sed -n 's/.*"agreement_iou": \([0-9.]*\).*/\1/p')"
    fi
  else
    failed_at="$(sed -n 's/.*FAILED at \([a-z]*\).*/\1/p' "$log")"
    [ "$rc" -eq 2 ] && toolfail=1
    # A refused run keeps no SVG or component in the record.
    find "$out" -maxdepth 1 \( -name "$name.svg" -o -name "$name.tsx" \) -delete
  fi
  python3 - "$out/$name.qa.json" "$label" "$rc" "${failed_at:--}" "${agree:--}" "$log" >>"$out/summary.tsv" <<'PY'
import json, os, re, sys
path, label, rc, failed_at, agree, log = sys.argv[1:]
q = json.load(open(path)) if failed_at in ("-", "qa", "auto") and os.path.exists(path) else {}
if failed_at == "check":  # svgcheck names the finding; keep it, the numbers were never scored
    found = re.findall(r"(budget-bytes|budget-paths|opaque-background)", open(log).read())
    failed_at = "check:" + ",".join(sorted(set(found))) if found else failed_at
elif failed_at == "qa":
    failed_at = "qa:" + ",".join(q.get("failures", []))
elif failed_at == "auto" and "search" in q:  # no candidate passed: name the nearest miss's failures
    miss = q["search"]["grid"][q["search"]["nearest"]]
    failed_at = "auto:" + ",".join(miss["check"] + ((miss["qa"] or {}).get("failures") or []))
    q = {**(miss["qa"] or {}), "svg_bytes": miss["bytes"]}
print("\t".join([label, rc, failed_at] + [str(q.get(k, "-")) for k in ("iou", "mae", "edge_f1", "jaggedness", "staircase")]
                + [agree, str(q.get("svg_bytes", "-"))]))
PY
  [ "$rc" -eq 0 ] || find "$out" -maxdepth 1 -name "$name.qa.json" -delete
}

for asset in monitor-glyph gamepad-glyph x-glyph clock-glyph thermometer-glyph; do
  name="$(pascal "$asset")"
  run "$asset" "$name" - "$here/src/$asset.png" "${glyph_clean[@]}"
  run "$asset.low" "${name}Low" "$name" "$here/src/$asset.low.png" "${glyph_low[@]}"
done
for asset in facebook-mark instagram-mark whatsapp-mark alert-mark facebook-banner-mark; do
  name="$(pascal "$asset")"
  run "$asset" "$name" - "$here/src/$asset.png" "${mark_clean[@]}"
  run "$asset.low" "${name}Low" - "$here/src/$asset.low.png" "${mark_low[@]}"
done

column -t -s "$(printf '\t')" "$out/summary.tsv"
echo "heldout: pass rate $passed/$total"
printf '%s/%s\n' "$passed" "$total" >"$out/pass-rate.txt"
[ "$toolfail" -eq 0 ] && find "$out" -maxdepth 1 -name '.*.log' -delete
exit "$toolfail"
