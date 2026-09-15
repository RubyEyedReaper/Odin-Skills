# shellcheck shell=bash
# The one place tool versions are pinned. Sourced by i2c.sh, doctor.sh and typecheck.sh.
#
# Nothing is installed globally: Python tools resolve per run through `uv run --with`, Node tools
# through `npx --yes`, both cached after the first run. Bumping a pin re-baselines the RubyTech
# evals — rerun evals/rubytech/run.sh and review qa.json before committing the bump.

I2C_SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

I2C_VTRACER="vtracer==0.6.15"
I2C_RESVG="resvg-py==0.5.0"
I2C_PILLOW="pillow==12.3.0"
I2C_SVGO="svgo@4.1.0"
I2C_TYPESCRIPT="typescript@5.9.3"
I2C_TYPES_REACT="@types/react@19.3.0"

# i2c_py <module> [args...] — run scripts/<module>.py with the pinned Python toolchain.
i2c_py() {
  local module="$1"; shift
  PYTHONPATH="$I2C_SKILL_DIR" uv run --no-project --quiet \
    --with "$I2C_VTRACER" --with "$I2C_RESVG" --with "$I2C_PILLOW" \
    python3 -m "scripts.$module" "$@"
}

# i2c_stdlib <module> [args...] — the stdlib modules (svgcheck, svg2tsx) on system python3.
i2c_stdlib() {
  local module="$1"; shift
  PYTHONPATH="$I2C_SKILL_DIR" python3 -m "scripts.$module" "$@"
}

# i2c_svgo <in.svg> <out.svg>
i2c_svgo() {
  npx --yes "$I2C_SVGO" --quiet --config "$I2C_SKILL_DIR/scripts/svgo.config.mjs" -i "$1" -o "$2"
}
