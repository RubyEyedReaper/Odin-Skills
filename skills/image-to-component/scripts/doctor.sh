#!/usr/bin/env bash
# doctor.sh — can the pipeline run on this host?
#
# Exit codes: 0 every stage can run; 1 a required launcher (uv, node, npx) is missing;
# 3 launchers exist but the pinned tools could not be resolved (offline with a cold cache, or a
# registry error). 3 is never folded into 0: "could not tell" is not "ready".
set -uo pipefail

# shellcheck source=toolchain.sh
. "$(dirname "${BASH_SOURCE[0]}")/toolchain.sh"

missing=0
for tool in uv node npx python3; do
  if command -v "$tool" >/dev/null; then
    echo "ok       $tool"
  else
    echo "MISSING  $tool" ; missing=1
  fi
done
[ "$missing" -eq 0 ] || exit 1

undetermined=0
if i2c_py doctor_probe 2>/dev/null; then
  echo "ok       $I2C_VTRACER $I2C_RESVG $I2C_PILLOW"
else
  echo "UNKNOWN  python toolchain did not resolve (network or cache)"; undetermined=1
fi
if npx --yes "$I2C_SVGO" --version >/dev/null 2>&1; then
  echo "ok       $I2C_SVGO"
else
  echo "UNKNOWN  $I2C_SVGO did not resolve (network or cache)"; undetermined=1
fi
command -v magick >/dev/null && echo "info     ImageMagick present (optional; prep.py does not need it)"
[ "$undetermined" -eq 0 ] || exit 3
