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
# Icon libraries for the replace route (scripts/library.py reads these three from the environment).
# Material Symbols publishes one package per weight: @material-symbols/svg-<100..700>@$I2C_MATERIAL.
I2C_SIMPLE_ICONS="simple-icons@16.31.0"
I2C_MATERIAL="0.47.3"
I2C_LIB_CACHE="${I2C_LIB_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/odin-image-to-component/libs}"
export I2C_SIMPLE_ICONS I2C_MATERIAL I2C_LIB_CACHE

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

# i2c_lib_fetch [weight...] — unpack simple-icons and Material Symbols (weight 400 unless named) into
# $I2C_LIB_CACHE once per version, with npm pack. An interrupted fetch leaves only a .partial directory,
# which the next call replaces. Exit 2 when a package cannot be fetched.
i2c_lib_fetch() {
  local specs=("$I2C_SIMPLE_ICONS") weight spec dir tmp members
  for weight in "${@:-400}"; do specs+=("@material-symbols/svg-$weight@$I2C_MATERIAL"); done
  mkdir -p "$I2C_LIB_CACHE" || return 2
  for spec in "${specs[@]}"; do
    dir="$I2C_LIB_CACHE/${spec#@}"; dir="${dir/material-symbols\//material-symbols-}"
    [ -f "$dir/package/package.json" ] && continue
    tmp="$(mktemp -d)"
    [ -d "$dir.partial" ] && find "$dir.partial" -depth -delete
    # Material ships outlined, rounded and sharp (~23k files, ~90 MB a weight); only outlined is ever read.
    members=(); [[ "$spec" == @material-symbols/* ]] && members=(package/package.json package/outlined)
    if (cd "$tmp" && npm pack --silent "$spec" >/dev/null 2>&1) && mkdir -p "$dir.partial" \
       && tar xzf "$tmp"/*.tgz -C "$dir.partial" "${members[@]}" && mv "$dir.partial" "$dir"; then
      find "$tmp" -depth -delete
    else
      find "$tmp" -depth -delete
      echo "i2c: could not fetch $spec into $I2C_LIB_CACHE" >&2
      return 2
    fi
  done
}
