#!/usr/bin/env bash
# check-doc-links.sh — no document here links a repository a visitor cannot open.
#
# This repository is public; the Odin harness it mirrors is not. v0.1.0 shipped
# five links to https://github.com/RubyEyedReaper/Odin across four files, each a
# 404 for every visitor and two of them instructions ("report it at…",
# "git clone…") sending the reader somewhere they cannot go.
#
# Every github.com/<owner>/<repo> reference in the tracked Markdown of this tree
# must appear in scripts/public-repos.txt, which is a committed, reviewed claim
# that the repository is public. The gate never touches the network: a check
# that asks GitHub fails offline, on a rate limit, and for a contributor with no
# token, and all three are indistinguishable from "the docs are broken".
#
# Boundary: this tree only. The Odin harness is private on purpose, so the same
# predicate applied to it would refuse correct links. Whether an allowlisted
# repository is *still* public is not checked — that needs the network. Link rot
# (a URL that 404s for any other reason) is a different defect and not checked.
#
# Usage: scripts/check-doc-links.sh [--root DIR] [--allowlist FILE]
# Exit:  0 clean, 1 with one 'FAIL: <file>:<line>: …' line per offending link,
#        2 on a usage error.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --allowlist) ALLOWLIST="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -d "$ROOT" ]] || { echo "not a directory: $ROOT" >&2; exit 2; }
ROOT="$(cd "$ROOT" && pwd)"
[[ -n "$ALLOWLIST" ]] || ALLOWLIST="$ROOT/scripts/public-repos.txt"

FAILURES=0
fail() { echo "FAIL: $*"; FAILURES=$((FAILURES + 1)); }

# grep does the extraction and supplies the line numbers. It is the only
# external tool here, and its absence must not read as "no links found":
# a guard that disables itself when a dependency is missing is
# indistinguishable from a guard that agrees with every input.
command -v grep >/dev/null 2>&1 || { echo "FAIL: grep not on PATH — cannot scan"; exit 1; }

# Tracked Markdown. git ls-files is the definition of "tracked", but a synthetic
# fixture is not a work tree, so fall back to find rather than scanning nothing.
docs=()
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  while IFS= read -r rel; do
    [[ -n "$rel" && -f "$ROOT/$rel" ]] && docs+=("$rel")
  done < <(git -C "$ROOT" ls-files -- '*.md' 2>/dev/null)
else
  while IFS= read -r abs; do
    [[ -n "$abs" ]] && docs+=("${abs#$ROOT/}")
  done < <(find "$ROOT" -type f -name '*.md' 2>/dev/null | sort)
fi

# Collect every candidate before consulting the allowlist. A tree with nothing
# to classify is clean whether or not an allowlist exists — there is no link to
# refuse. A tree WITH candidates and no allowlist is refused below.
findings=()
for rel in "${docs[@]}"; do
  while IFS= read -r hit; do
    [[ -n "$hit" ]] || continue
    line="${hit%%:*}"
    slug="${hit#*:}"
    slug="${slug#github.com/}"
    slug="${slug%.git}"
    slug="${slug%%[).,>]}"
    slug="${slug%%[).,>]}"
    # A <placeholder> is a template, not a link. No repository name may contain
    # an angle bracket, so this cannot mask a real slug.
    [[ "$slug" == *'<'* || "$slug" == *'>'* ]] && continue
    findings+=("$rel:$line:$slug")
  done < <(grep -noE 'github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._<>-]+' "$ROOT/$rel" 2>/dev/null)
done

if [[ ${#findings[@]} -eq 0 ]]; then
  echo "OK: no GitHub repository links in ${#docs[@]} tracked document(s)."
  exit 0
fi

allow=()
if [[ -f "$ALLOWLIST" ]]; then
  while IFS= read -r entry; do
    entry="${entry%%#*}"
    entry="${entry//[[:space:]]/}"
    [[ -n "$entry" ]] && allow+=("$entry")
  done < "$ALLOWLIST"
fi

if [[ ${#allow[@]} -eq 0 ]]; then
  rel_allow="${ALLOWLIST#$ROOT/}"
  fail "${#findings[@]} GitHub link(s) to classify but no entries in $rel_allow — the allowlist is missing or empty, and a check with no data must refuse rather than agree"
  echo
  echo "$FAILURES check(s) failed."
  exit 1
fi

is_allowed() {
  local want="$1" entry
  for entry in "${allow[@]}"; do
    [[ "$entry" == "$want" ]] && return 0
  done
  return 1
}

for finding in "${findings[@]}"; do
  rel="${finding%%:*}"; rest="${finding#*:}"
  line="${rest%%:*}"; slug="${rest#*:}"
  is_allowed "$slug" && continue
  fail "$rel:$line: links https://github.com/$slug, which is not on the public allowlist (${ALLOWLIST#$ROOT/}) — a link to a repository visitors cannot open is a 404 for all of them"
done

if [[ $FAILURES -gt 0 ]]; then
  echo
  echo "$FAILURES check(s) failed."
  exit 1
fi
echo "OK: ${#findings[@]} GitHub repository link(s) checked, all public."
