# Component contract

What `scripts/svg2tsx.py` emits, held by `tests/test_svg2tsx.py`.

**Input is the pipeline's dialect only** (decided for #1352). `svg`, `g` and `path`, carrying `d`,
`fill`, `fill-rule`, `fill-opacity`, `opacity`, `stroke` and `transform` (plus the root's size and
namespace attributes, which are dropped or rewritten); `title`, `desc` and `metadata` are dropped.
Anything else — another element, `style`, `class`, `id`, a `data-` or namespaced attribute — exits
1 with `svg2tsx: refused: … is outside the dialect`. The standalone CLI used to transcribe arbitrary
SVG through a style-object, namespace and text surface nothing ever fed it and no test held against
real input. Hand-authored SVG is a component to write by hand; vtracer + SVGO output converts
exactly as before (the RubyTech goldens regenerate byte-identical).

```tsx
import { GearIcon } from "./icons";

<GearIcon width={20} height={20} className="text-cyan-400" />          // decorative: aria-hidden
<GearIcon title="Settings" width={20} height={20} />                   // role="img" + <title>
<button aria-label="Settings"><GearIcon /></button>                     // label on the control
```

| Guarantee | How |
|---|---|
| Typed props | `interface <Name>Props extends SVGProps<SVGSVGElement> { title?: string }` |
| Responsive | `viewBox` preserved (derived from width/height when absent); width/height removed from the root |
| Accessible when labelled | `title` → `<title id>` via `useId()` + `aria-labelledby`; `title`, `aria-label` or `aria-labelledby` → `role="img"` |
| Silent when decorative | no label → `aria-hidden`, `focusable="false"` |
| Caller wins | `{...props}` spread after every default |
| Themeable | `--color currentColor`: the root gets `fill="currentColor"` (a binary trace carries no paint of its own), and every paint except `none`/`transparent` becomes `currentColor` |
| Safe | `<script>`, `<image>`, `<foreignObject>`, `<use>`, `<iframe>` and `on*` attributes refuse conversion (exit 1) |
| Clean | source `<title>`, `<desc>`, `<metadata>`, comments and XML prolog dropped |
| JSX-correct | hyphenated attributes camel-cased, `class` → `className`, `style` string → object, values with quotes or braces emitted as expressions |
| Discoverable | named + default export; `typecheck.sh` writes a sorted `index.ts` barrel |

## Naming

`--name` is PascalCased (`ruby-tech_logo` → `RubyTechLogo`); a leading digit gets an `Svg` prefix.
File name equals component name. Suffix by role: `…Icon`, `…Mark`, `…Logo`, `…Illustration`.

## Where it goes

Into the consuming project's component tree, e.g. `src/components/ui/icons/`. Keep the `.svg`
beside it only when a non-React surface (email, CSS `mask-image`, favicon) needs the raw file.
