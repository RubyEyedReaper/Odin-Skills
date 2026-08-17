#!/usr/bin/env bash
# publish-skill.sh — publish one skill from this repository as its own tiny
# public repository, <owner>/skill-<name>, so a user can take one skill without
# the bundle.
#
# The split carries real commit history, so a `git subtree split` rather than a
# fresh `git init`. Three things it refuses to guess:
#   * the subtree prefix, which is repository-root-relative — `git subtree` runs
#     cd_to_toplevel before reading -P, so a $ROOT-relative prefix splits nothing
#   * the licence artefacts, chosen by skill class and never inferred; a fork
#     with no upstream artefact aborts before any network call
#   * whether the repository already exists — a rerun clones and pushes only a
#     real change, because a second `subtree split` cannot fast-forward the
#     first push and force-pushing is forbidden
#
# Usage: scripts/publish-skill.sh <skill-name> [--owner OWNER] [--root DIR]
#                                 [--dry-run] [--verify]
#        Flags follow the skill name. --owner defaults to RubyEyedReaper.
#        --dry-run prints every git and gh command and touches no network.
#        --verify diffs the published tree against the local skill directory.
# Exit:  0 success or nothing to do, 1 refused or failed, 2 usage error.
set -uo pipefail

ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}"
OWNER_DEFAULT="RubyEyedReaper"
OWNER="${OWNER:-$OWNER_DEFAULT}"
DRY_RUN=0
VERIFY=0

# The banner every published landing page opens with. These repositories take no
# pull requests, and a visitor has no other way to learn that. It names the
# published mirror rather than the harness that develops the skill: the harness
# repository is private, so a link to it is a 404 for every visitor and an issue
# tracker nobody outside the account can reach.
BANNER='> **Read-only publish target.** Development is coordinated in
> [RubyEyedReaper/Odin-Skills](https://github.com/RubyEyedReaper/Odin-Skills), where this skill
> lives under `skills/`. Pull requests opened here are not merged — please file issues there
> instead.'

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"; }
note()  { printf '%s\n' "$*" >&2; }

# frontmatter_field <file> <key> — value of a top-level YAML key in the leading
# --- block, folded continuation lines joined (same reader as validate-skills.sh).
frontmatter_field() {
  awk -v key="$2" '
    NR == 1 && $0 != "---" { exit }
    NR == 1 { next }
    $0 == "---" { exit }
    {
      if ($0 ~ "^" key ":") { found = 1; sub("^" key ":[ \t]*", ""); val = $0; next }
      if (found && $0 ~ /^[ \t]+[^ \t]/) { sub(/^[ \t]+/, " "); val = val $0; next }
      if (found) { exit }
    }
    END { if (found) print val }
  ' "$1"
}

# ---------------------------------------------------------------------------
# Decisions — every one of these is testable without a network
# ---------------------------------------------------------------------------

# validate_skill_name <name> — a publishable name that exists on disk.
validate_skill_name() {
  local name="${1:-}"
  if [[ ! "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    note "not a skill name: '$name' — expected lowercase letters, digits and dashes"
    return 1
  fi
  if [[ ! -f "$ROOT/skills/$name/SKILL.md" ]]; then
    note "no such skill: '$name' — expected skills/$name/SKILL.md under $ROOT"
    return 1
  fi
}

# repo_name_for <name> — the published repository's name.
repo_name_for() { printf 'skill-%s\n' "${1:-}"; }

# repo_description_for <name> — the public one-liner on the repository page.
repo_description_for() { printf '%s — a skill from the Odin agent harness\n' "${1:-}"; }

# toplevel_for_root — the enclosing git repository's root.
toplevel_for_root() {
  local top
  top="$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null)"
  if [[ -z "$top" ]]; then
    note "not inside a git repository: $ROOT"
    return 1
  fi
  (cd "$top" && pwd -P)
}

# subtree_prefix_for <name> — the -P argument, relative to the repository root
# rather than to $ROOT. Inside the harness that is
# projects/Odin-Skills/skills/<name>; in a standalone clone of the published
# monorepo it is skills/<name>. Never hardcoded, because both are real.
subtree_prefix_for() {
  local name="${1:-}" top root_abs rel
  top="$(toplevel_for_root)" || return 1
  root_abs="$(cd "$ROOT" && pwd -P)" || return 1
  rel="${root_abs#"$top"}"
  rel="${rel#/}"
  if [[ -n "$rel" ]]; then
    printf '%s/skills/%s\n' "$rel" "$name"
  else
    printf 'skills/%s\n' "$name"
  fi
}

# license_files_for <name> — root-relative paths of the artefacts the published
# repository must carry, by skill class. Fails closed: the alternative to an
# unsatisfied class is publishing someone else's work under Odin's terms.
license_files_for() {
  local name="${1:-}" dir="$ROOT/skills/${1:-}"

  if [[ -f "$dir/UPSTREAM.md" || -f "$dir/LICENSE" ]]; then
    # A fork. The root NOTICE travels with every one of them: it carries the
    # Apache-2.0 §4(d) notice text, which exists nowhere else in the tree.
    if [[ ! -f "$ROOT/NOTICE" ]]; then
      note "refusing to publish $name: it is a fork and $ROOT/NOTICE is missing"
      return 1
    fi
    if [[ -f "$dir/LICENSE" ]]; then
      printf 'skills/%s/LICENSE\nNOTICE\n' "$name"
      return 0
    fi
    if [[ -f "$dir/NOTICE" ]]; then
      printf 'skills/%s/NOTICE\nNOTICE\n' "$name"
      return 0
    fi
    note "refusing to publish $name: skills/$name/UPSTREAM.md declares a fork, but neither"
    note "skills/$name/LICENSE nor skills/$name/NOTICE states its upstream terms"
    return 1
  fi

  local f
  for f in LICENSE-MIT LICENSE-CC-BY-SA-4.0; do
    if [[ ! -f "$ROOT/$f" ]]; then
      note "refusing to publish $name: $ROOT/$f is missing"
      return 1
    fi
  done
  printf 'LICENSE-MIT\nLICENSE-CC-BY-SA-4.0\n'
}

# license_line_for <name> — the landing page's one-line licence pointer, naming
# the artefacts license_files_for selected.
license_line_for() {
  local name="${1:-}" dir="$ROOT/skills/${1:-}"
  if [[ -f "$dir/LICENSE" ]]; then
    printf 'A fork: upstream terms in `LICENSE`, attribution and modification notices in `NOTICE`.\n'
  elif [[ -f "$dir/UPSTREAM.md" ]]; then
    printf 'A fork whose upstream ships no licence file; what upstream declared, and Odin'"'"'s own notices, are in `NOTICE`.\n'
  else
    printf 'Odin'"'"'s own work: prose under CC-BY-SA-4.0, code under MIT — see `LICENSE-CC-BY-SA-4.0` and `LICENSE-MIT`.\n'
  fi
}

# readme_body <name> — the whole public landing page. No skill directory in the
# mirror carries a README, so a banner alone would be the entire page.
readme_body() {
  local name="${1:-}" desc repo
  desc="$(frontmatter_field "$ROOT/skills/$name/SKILL.md" description)"
  repo="$(repo_name_for "$name")"
  license_files_for "$name" >/dev/null || return 1

  cat <<EOF
# $name

$BANNER

$desc

## Install

\`\`\`sh
git clone https://github.com/$OWNER/$repo.git
cp -r $repo ~/.claude/skills/$name
\`\`\`

## Licence

$(license_line_for "$name")
EOF
}

# publish_mode <owner/repo> — create when the repository is absent, update when
# it is there. This is what makes a rerun a no-op instead of a rejected push.
publish_mode() {
  if gh repo view "${1:-}" >/dev/null 2>&1; then
    printf 'update\n'
  else
    printf 'create\n'
  fi
}

# needs_commit <dir> — 0 when the working tree has something to commit.
needs_commit() {
  local dir="${1:-}" out
  out="$(git -C "$dir" status --porcelain 2>/dev/null)" || return 1
  [[ -n "$out" ]]
}

# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------

# write_publish_files <destdir> <name> <license-file>... — the two things this
# script contributes to the published repository. Artefacts sharing a basename
# (a declared-absence fork's own NOTICE and the root NOTICE) are concatenated in
# selection order rather than one clobbering the other; the write is a rewrite,
# not an append, so a rerun produces the same file.
write_publish_files() {
  local dest="$1" name="$2"; shift 2
  readme_body "$name" > "$dest/README.md" || return 1

  local f base
  local -A written=()
  for f in "$@"; do
    base="$(basename "$f")"
    if [[ -n "${written[$base]:-}" ]]; then
      { printf '\n---\n\n'; cat "$ROOT/$f"; } >> "$dest/$base"
    else
      cat "$ROOT/$f" > "$dest/$base"
      written[$base]=1
    fi
  done
}

# print_plan <name> <slug> <prefix> <license-file>... — --dry-run. Both modes
# are printed: choosing between them is the one thing a dry run cannot do
# without calling gh, and calling gh is what a dry run must not do.
print_plan() {
  local name="$1" slug="$2" prefix="$3"; shift 3
  local top branch
  top="$(toplevel_for_root)" || return 1
  branch="publish-$name-\$\$"

  cat <<EOF
plan for $slug (dry run — nothing below is executed)

licence artefacts carried:
$(printf '  %s\n' "$@")

mode is chosen by:   gh repo view $slug

if absent (create):
  git -C $top subtree split -P $prefix -b $branch
  git clone -b $branch $top <tmp>
  gh repo create $slug --public --description "$(repo_description_for "$name")"
  git -C <tmp> remote set-url origin https://github.com/$slug.git
  git -C <tmp> branch -M main
  <write README.md and the licence artefacts>
  git -C <tmp> add -A && git -C <tmp> commit -m "publish $name"
  git -C <tmp> push -u origin main
  git -C $top branch -D $branch

if present (update):
  git clone https://github.com/$slug.git <tmp>
  <replace tracked content from $ROOT/skills/$name, preserving .git>
  <write README.md and the licence artefacts>
  git -C <tmp> status --porcelain    # empty means nothing to push
  git -C <tmp> add -A && git -C <tmp> commit -m "sync $name from Odin"
  git -C <tmp> push origin HEAD:main
EOF
}

# publish_create <name> <slug> <prefix> <license-file>...
# The split runs before the repository is created, so a failed split leaves no
# empty public repository behind.
publish_create() {
  local name="$1" slug="$2" prefix="$3"; shift 3
  local top branch tmp rc=0
  top="$(toplevel_for_root)" || return 1
  branch="publish-$name-$$"

  if ! git -C "$top" subtree split -P "$prefix" -b "$branch" >&2; then
    note "subtree split failed for prefix $prefix"
    return 1
  fi

  tmp="$(mktemp -d)"
  git clone -q -b "$branch" "$top" "$tmp" >&2
  if [[ ! -d "$tmp/.git" ]]; then
    note "clone of $branch produced no repository at $tmp"
    rm -rf "$tmp"
    git -C "$top" branch -D "$branch" >&2
    return 1
  fi

  git -C "$tmp" branch -M main >&2
  write_publish_files "$tmp" "$name" "$@" || rc=1

  if [[ $rc -eq 0 ]]; then
    gh repo create "$slug" --public --description "$(repo_description_for "$name")" >&2 || rc=1
  fi
  if [[ $rc -eq 0 ]]; then
    git -C "$tmp" remote set-url origin "https://github.com/$slug.git" >&2 || rc=1
  fi
  if [[ $rc -eq 0 ]]; then
    git -C "$tmp" add -A >&2
    git -C "$tmp" commit -qm "publish $name from the Odin agent harness" >&2 || rc=1
  fi
  if [[ $rc -eq 0 ]]; then
    git -C "$tmp" push -u origin main >&2 || rc=1
  fi
  if [[ $rc -eq 0 ]]; then
    git -C "$tmp" rev-parse HEAD
  fi

  rm -rf "$tmp"
  git -C "$top" branch -D "$branch" >&2
  return $rc
}

# publish_update <name> <slug> <license-file>...
# Never force-pushes: the clone is the published history, so the commit this
# adds fast-forwards by construction.
publish_update() {
  local name="$1" slug="$2"; shift 2
  local tmp rc=0
  tmp="$(mktemp -d)"
  git clone -q "https://github.com/$slug.git" "$tmp" >&2
  if [[ ! -d "$tmp/.git" ]]; then
    note "clone of $slug produced no repository at $tmp"
    rm -rf "$tmp"
    return 1
  fi

  find "$tmp" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  cp -a "$ROOT/skills/$name/." "$tmp/"
  write_publish_files "$tmp" "$name" "$@" || rc=1

  if [[ $rc -eq 0 ]] && ! needs_commit "$tmp"; then
    note "$slug already matches skills/$name — nothing to push"
    rm -rf "$tmp"
    return 0
  fi
  if [[ $rc -eq 0 ]]; then
    git -C "$tmp" add -A >&2
    git -C "$tmp" commit -qm "sync $name from the Odin agent harness" >&2 || rc=1
  fi
  if [[ $rc -eq 0 ]]; then
    git -C "$tmp" push origin HEAD:main >&2 || rc=1
  fi
  if [[ $rc -eq 0 ]]; then
    git -C "$tmp" rev-parse HEAD
  fi

  rm -rf "$tmp"
  return $rc
}

# verify_published <name> <slug> <license-file>... — the published tree matches
# the local skill directory, ignoring exactly the files this script writes.
verify_published() {
  local name="$1" slug="$2"; shift 2
  local tmp rc=0 f
  local -a excl=(-x .git -x README.md)
  for f in "$@"; do excl+=(-x "$(basename "$f")"); done

  tmp="$(mktemp -d)"
  git clone -q --depth 1 "https://github.com/$slug.git" "$tmp" >&2
  if [[ ! -d "$tmp/.git" ]]; then
    note "cannot verify $slug: clone produced no repository"
    rm -rf "$tmp"
    return 1
  fi

  if diff -r "${excl[@]}" "$ROOT/skills/$name" "$tmp" >&2; then
    printf 'verified: %s matches skills/%s\n' "$slug" "$name"
  else
    note "published $slug differs from skills/$name"
    rc=1
  fi
  rm -rf "$tmp"
  return $rc
}

# ---------------------------------------------------------------------------
main() {
  # Shadowed so a second call in the same shell starts from the defaults, and so
  # --root cannot leak out of the invocation that asked for it.
  local ROOT="$ROOT" OWNER="$OWNER_DEFAULT" DRY_RUN=0 VERIFY=0
  local name=""

  if [[ $# -eq 0 ]]; then
    usage >&2
    return 2
  fi
  case "$1" in
    -h|--help) usage; return 0 ;;
    -*) note "the skill name comes first: publish-skill.sh <skill-name> [flags]"; return 2 ;;
    *) name="$1"; shift ;;
  esac

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --owner) OWNER="${2:-}"; shift 2 ;;
      --root)
        if ! ROOT="$(cd "${2:-}" 2>/dev/null && pwd -P)"; then
          note "no such directory: ${2:-}"
          return 2
        fi
        shift 2 ;;
      --dry-run) DRY_RUN=1; shift ;;
      --verify) VERIFY=1; shift ;;
      -h|--help) usage; return 0 ;;
      *) note "unknown argument: $1"; return 2 ;;
    esac
  done

  validate_skill_name "$name" || return 1

  local repo slug prefix
  repo="$(repo_name_for "$name")"
  slug="$OWNER/$repo"

  # Both before any network call: an unsatisfied licence class or an
  # uncomputable prefix must abort while nothing public exists.
  local -a licenses=()
  local line
  while IFS= read -r line; do [[ -n "$line" ]] && licenses+=("$line"); done < <(license_files_for "$name")
  [[ ${#licenses[@]} -gt 0 ]] || return 1
  prefix="$(subtree_prefix_for "$name")" || return 1

  if [[ $VERIFY -eq 1 ]]; then
    verify_published "$name" "$slug" "${licenses[@]}"
    return $?
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    print_plan "$name" "$slug" "$prefix" "${licenses[@]}"
    return $?
  fi

  case "$(publish_mode "$slug")" in
    create) publish_create "$name" "$slug" "$prefix" "${licenses[@]}" ;;
    update) publish_update "$name" "$slug" "${licenses[@]}" ;;
  esac
}

[[ "${BASH_SOURCE[0]}" == "${0}" ]] && main "$@"
