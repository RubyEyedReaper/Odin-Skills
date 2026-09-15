#!/usr/bin/env bash
# Regenerate the RubyTech evals: five assets that must pass every stage, and one that must be
# refused at the budget check. Outputs land in evals/rubytech/out/; review qa.json diffs before
# committing a regeneration, and commit it on its own.
#
# Exit codes: 0 every expectation held; 1 an expectation failed; 2 toolchain unavailable.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill="$(cd "$here/../.." && pwd)"
out="$here/out"
mkdir -p "$out"
i2c() { bash "$skill/scripts/i2c.sh" "$@"; }

bash "$skill/scripts/doctor.sh" >/dev/null || { echo "rubytech: toolchain unavailable (run scripts/doctor.sh)" >&2; exit 2; }

failed=0
expect() {  # expect <rc> <label> -- <i2c args...>
  local want="$1" label="$2"; shift 3
  local rc=0; i2c "$@" >"$out/.$label.log" 2>&1 || rc=$?
  if [ "$rc" -eq "$want" ]; then
    echo "ok    $label (exit $rc)"
  else
    echo "FAIL  $label: exit $rc, expected $want — see $out/.$label.log"; failed=1
  fi
}

# No --smooth: these sources are anti-aliased, so auto resolves to a Gaussian of 0.375 x scale = 3,
# the radius this row was tuned at. A diff in any glyph here means auto stopped seeing a soft edge.
glyph=(--kind icon --key global --matte soft --scale 8 --color currentColor --out "$out")
expect 0 computer-icon   -- "$here/src/computer-icon.png"   --name ComputerIcon   "${glyph[@]}"
expect 0 gear-icon       -- "$here/src/gear-icon.png"       --name GearIcon       "${glyph[@]}"
expect 0 controller-icon -- "$here/src/controller-icon.png" --name ControllerIcon "${glyph[@]}"
expect 0 wrench-icon     -- "$here/src/wrench-icon.png"     --name WrenchIcon     "${glyph[@]}"

brand=(--kind logo --scale 2 --colors 32 --matte soft --set filter_speckle=12 --set layer_difference=12)
expect 0 rubytech-mark -- "$here/src/rubytech-mark.png" --name RubyTechMark "${brand[@]}" --out "$out"

# The full lockup carries a tagline in ~9px type. Tracing it is the wrong route, and the budget
# is what must say so: exit 1 at the check stage, never a pass with thresholds loosened.
refused="$(mktemp -d)"
expect 1 rubytech-lockup-refused -- "$here/src/rubytech-logo.png" --name RubyTechLogo "${brand[@]}" --out "$refused"
grep -q "budget-" "$out/.rubytech-lockup-refused.log" || { echo "FAIL  lockup refused for a reason other than budget"; failed=1; }
find "$refused" -depth -delete

bash "$skill/scripts/typecheck.sh" "$out" || { echo "FAIL  typecheck"; failed=1; }

# Exit codes cannot see these, and both once shipped: a standalone .svg with no namespace renders
# nowhere but inline, and a currentColor glyph with no fill renders black whatever the text colour.
for svg in "$out"/*.svg; do
  body="$(head -c 200 "$svg")"
  grep -q 'xmlns="http://www.w3.org/2000/svg"' <<< "$body" || { echo "FAIL  $(basename "$svg") has no xmlns"; failed=1; }
done
for icon in ComputerIcon GearIcon ControllerIcon WrenchIcon; do
  grep -q 'fill="currentColor"' "$out/$icon.tsx" || { echo "FAIL  $icon.tsx does not inherit colour"; failed=1; }
done
[ "$failed" -eq 0 ] && find "$out" -maxdepth 1 -name '.*.log' -delete
exit "$failed"
