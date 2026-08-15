"""Which surfaces on disk does no roadmap item claim?

The counterpart to `_missing_files`, which asks the same question from the other end (an item's
files that no longer exist). Without this the `untracked-surface` finding kind and its applier
describe a capability the engine does not have.

Three decisions shape everything here, and each exists to stop a specific way this goes wrong.

**Enumerate from git.** `git ls-files --cached --others --exclude-standard` honours `.gitignore`,
`.git/info/exclude`, global excludes and nested ignore files — semantics a stdlib reimplementation
gets subtly wrong forever, and always in the direction of more noise. It also does not recurse into
a nested repository, so a workspace holding other projects reports each as one entry instead of
proposing roadmap items for a foreign project's source (ADR-0026, enforced by the mechanism rather
than by a rule someone has to remember).

**No fallback when git is unavailable.** A filesystem walk with a hand-written ignore list is a
*different* universe of paths, so `--apply-auto` on a machine without git would add items the next
run on a machine with git would never propose. An evidence channel that changes what gets written
depending on the runner is worse than an absent one.

**Bounded three ways.** Depth, a hard cap, and sorted order before the cap. A sweep that drops
findings silently makes the next run's output depend on what the last one happened to see; the
dropped count is reported instead.
"""
from __future__ import annotations

import os
import subprocess

from .reconcile import claims

# The directories a source tree usually keeps its surfaces in. Filtered by existence, so a repo
# with none of them — Odin's own, for instance — sweeps nothing until `surface_roots` says otherwise.
# That is the intended outcome: a sweep of a harness tree, where every directory is deliberate,
# produces a hundred findings and no signal.
DEFAULT_ROOTS = ("src", "app", "apps", "packages", "lib", "services")

# A surface is a directory this deep under a root: `src/app/billing`, not `src` and not every file
# beneath it. One finding per feature directory is the granularity a roadmap item maps to.
DEPTH = 2

# Per run. Ten unclaimed surfaces is already a conversation; a hundred is a wall nobody reads, and
# under `--apply-auto` it would be a hundred items in a file the skill calls permanent.
MAX_FINDINGS = 10


def _git_files(root):
    """Every tracked or untracked-but-not-ignored path, repo-relative. `None` when git cannot say."""
    try:
        result = subprocess.run(
            ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [entry for entry in result.stdout.split("\0") if entry]


def resolve_roots(root, doc, override=None):
    """Which directories to sweep: explicit override, then the doc, then convention — existing only."""
    candidates = override or doc.get("surface_roots") or DEFAULT_ROOTS
    return [c for c in candidates if os.path.isdir(os.path.join(root, str(c).rstrip("/")))]


def _fold(path, sweep_root):
    """The ancestor of `path` at DEPTH components below `sweep_root` (or `path` if it is shallower)."""
    rest = path[len(sweep_root):].lstrip("/").split("/")
    # A file directly under the root has one component and no directory to fold to; keep it whole.
    if len(rest) <= DEPTH:
        return path
    return "/".join([sweep_root] + rest[:DEPTH])


def untracked_surfaces(root, doc, override=None):
    """`(paths, dropped)` — unclaimed surfaces, bounded, and how many the cap discarded."""
    roots = resolve_roots(root, doc, override)
    if not roots:
        return [], 0
    files = _git_files(root)
    if files is None:
        return [], 0

    claimed = []
    for item in doc.get("items", []):
        claimed.extend((item.get("links") or {}).get("files") or [])

    surfaces = set()
    for path in files:
        for sweep_root in roots:
            prefix = str(sweep_root).rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                surfaces.add(_fold(path, prefix))
                break

    # Filtered with the same predicate `analyze` uses. If the two disagreed, pruning here would
    # silently drop findings the filtering layer would have emitted — or waste work it would not.
    unclaimed = sorted(s for s in surfaces if not claims(s, claimed))
    if len(unclaimed) <= MAX_FINDINGS:
        return unclaimed, 0
    return unclaimed[:MAX_FINDINGS], len(unclaimed) - MAX_FINDINGS
