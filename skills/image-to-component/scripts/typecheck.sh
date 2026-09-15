#!/usr/bin/env bash
# typecheck.sh <dir> — compile every generated .tsx in <dir> under strict TypeScript + React types.
#
# Installs the pinned typescript and @types/react into a throwaway directory (never the project's
# node_modules), and writes the barrel index.ts first so the export surface is checked too.
# Exit codes: 0 compiles, 1 type errors, 2 usage or install failure.
set -euo pipefail

# shellcheck source=toolchain.sh
. "$(dirname "${BASH_SOURCE[0]}")/toolchain.sh"

dir="${1:-}"
[ -n "$dir" ] && [ -d "$dir" ] || { echo "usage: typecheck.sh <dir-with-tsx>" >&2; exit 2; }
dir="$(cd "$dir" && pwd)"
compgen -G "$dir/*.tsx" >/dev/null || { echo "typecheck: no .tsx files in $dir" >&2; exit 2; }

i2c_stdlib svg2tsx --barrel "$dir"

work="$(mktemp -d)"
trap 'find "$work" -depth -delete' EXIT
(cd "$work" && npm init -y >/dev/null && npm install --silent --no-audit --no-fund \
  "$I2C_TYPESCRIPT" "$I2C_TYPES_REACT" >/dev/null) || { echo "typecheck: install failed" >&2; exit 2; }

cat > "$work/tsconfig.json" <<JSON
{
  "compilerOptions": {
    "strict": true, "noEmit": true, "jsx": "react-jsx", "target": "ES2022",
    "module": "ESNext", "moduleResolution": "Bundler", "skipLibCheck": true,
    "typeRoots": ["$work/node_modules/@types"], "types": ["react"],
    "baseUrl": "$work", "paths": { "react": ["node_modules/@types/react"], "react/jsx-runtime": ["node_modules/@types/react/jsx-runtime"] }
  },
  "include": ["$dir/*.tsx", "$dir/index.ts"]
}
JSON
"$work/node_modules/.bin/tsc" -p "$work/tsconfig.json" && echo "typecheck: ok ($dir)" >&2 || exit 1
