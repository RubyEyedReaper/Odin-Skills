"""Fixtures: a real git repository, a synthetic bare origin, and a throwaway roadmap.

Named with a leading underscore so `unittest discover`'s `test*.py` pattern does not
collect it as a suite.

Every fixture lives under `mktemp -d`. No case reads the live roadmap, the live remote or
the real HOME — a suite that consults the tree it is run from reports on that tree's
accidents rather than on the engine.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

# The skill directory, so `import scripts.campaign` resolves however the test is invoked.
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

#: The repository this suite is *running inside*. Never a subject, only a witness: one
#: case asserts it is byte-identical before and after the whole suite, because an empty
#: or mistaken fixture root silently drives the live tree (`git -C ""` is the current
#: repository).
LIVE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _env(home: str) -> dict:
    """A git environment pinned to the fixture's own HOME, never the operator's."""
    env = dict(os.environ)
    env.update(GIT_ENV)
    env["HOME"] = home
    env["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
    return env


def git(root: str, *args: str, home: str = "", check: bool = True) -> str:
    """Run git against an explicitly named root.

    The root is validated before the call, not after: `git -C ""` means the *current*
    repository, so an empty fixture root would run the command against the live tree and
    report success.
    """
    if not root or not os.path.isdir(root):
        raise ValueError(f"refusing git with an unusable root: {root!r}")
    proc = subprocess.run(
        ["git", "-C", root, *args],
        capture_output=True,
        text=True,
        env=_env(home or os.path.dirname(root)),
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


class Campaign:
    """A campaign's world: bare origin, working clone, roadmap, manifest.

    Workers are added one at a time and each declares whether its work has landed on the
    base and what the roadmap says about its item. The two are set independently on
    purpose — a roadmap that claims `done` while the content is absent is the disagreement
    the engine must report as undeterminable rather than resolve.
    """

    def __enter__(self) -> "Campaign":
        self.tmp = tempfile.mkdtemp(prefix="campaign-test-")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".config"))
        self.origin = os.path.join(self.tmp, "origin.git")
        self.root = os.path.join(self.tmp, "work")

        subprocess.run(
            ["git", "init", "--bare", "-b", "main", self.origin],
            capture_output=True, text=True, check=True, env=_env(self.home),
        )
        subprocess.run(
            ["git", "clone", self.origin, self.root],
            capture_output=True, text=True, check=True, env=_env(self.home),
        )
        self._git("config", "user.name", "Fixture")
        self._git("config", "user.email", "fixture@example.invalid")

        os.makedirs(os.path.join(self.root, ".claude", "docs", "roadmap"))
        self._write("README.md", "base\n")
        self._git("add", "-A")
        self._git("commit", "-m", "base")
        self._git("push", "-u", "origin", "main")

        self.items: list[dict] = []
        self.workers: list[dict] = []
        return self

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ----------------------------------------------------------------- helpers

    def _git(self, *args: str, check: bool = True) -> str:
        return git(self.root, *args, home=self.home, check=check)

    def _write(self, rel: str, body: str) -> None:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)

    # ------------------------------------------------------------------ world

    def add_worker(
        self,
        item: str,
        branch: str,
        landed: bool = False,
        roadmap_status: str = "open",
        in_roadmap: bool = True,
        evidence: str | None = None,
    ) -> dict:
        """Create a worker's branch, optionally land its content, and record its item."""
        self._git("checkout", "-q", "-b", branch, "main")
        self._write(f"{branch.replace('/', '-')}.md", f"work for {item}\n")
        self._git("add", "-A")
        self._git("commit", "-m", f"feat: {item}")
        self._git("push", "-q", "-u", "origin", branch)
        tip = self._git("rev-parse", branch)
        self._git("checkout", "-q", "main")

        landed_sha = None
        if landed:
            # A rebase merge: same patch, different sha. Ancestry says "not merged" here
            # and content says otherwise, which is the whole reason `bl_classify` exists.
            self._git("cherry-pick", tip)
            # Amend so the landed commit carries a *different sha for the same patch* —
            # the shape a rebase merge produces, and the reason ancestry cannot answer
            # this question (ADR-0093). Without this the cherry-pick is sha-identical to
            # the branch tip and the fixture proves nothing about content comparison.
            self._git("commit", "--amend", "-m", f"feat: {item} (landed by rebase)")
            landed_sha = self._git("rev-parse", "HEAD")
            self._git("push", "-q", "origin", "main")

        if in_roadmap:
            self.items.append({
                "id": item.split(":", 1)[-1],
                "status": roadmap_status,
                "evidence": evidence if evidence is not None else landed_sha,
                "title": f"item {item}",
            })
        worker = {"worker": branch.rsplit("/", 1)[-1], "branch": branch, "item": item}
        self.workers.append(worker)
        return worker

    def write_roadmap(self, scope: str = "operational", slug: str | None = None) -> str:
        """A roadmap shaped like the live one.

        `scope` defaults to `operational` — the live harness roadmap's value — precisely
        because it is NOT the half of a qualified id before the colon. That prefix is the
        roadmap's *slug*, derived by the roadmap engine from the document's own path when
        the document does not declare one. A fixture that set `scope: harness` would let a
        prefix-against-scope comparison pass while reading every real id as foreign.
        """
        path = os.path.join(self.root, ".claude", "docs", "roadmap", "roadmap.json")
        doc = {"schema": 1, "scope": scope, "items": self.items}
        if slug is not None:
            doc["slug"] = slug
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(doc, handle)
        return path

    def manifest(self, path: str = "campaign.json", **overrides) -> str:
        """Write a manifest holding the plan and nothing else, then return its path."""
        doc = {
            "campaign": "fixture-campaign",
            "objective": "prove the close refuses",
            "base": "origin/main",
            "remote": "origin",
            "close_out": ["every item landed", "residue handed to tidy"],
            "waves": [{"wave": 1, "workers": self.workers}],
        }
        doc.update(overrides)
        full = os.path.join(self.root, path)
        with open(full, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=1)
        return full

    def unreachable_remote(self) -> None:
        """Point origin at a path that is not there — the remote cannot be consulted."""
        self._git("remote", "set-url", "origin", os.path.join(self.tmp, "gone.git"))


def run_cli(*argv: str) -> tuple[int, str, str]:
    """Invoke the engine in-process. Stdout is data, stderr is diagnostics."""
    from scripts.campaign import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def git_rc(root: str, *args: str, home: str = "") -> int:
    """A git call's exit code, for the cases where the code is the evidence."""
    if not root or not os.path.isdir(root):
        raise ValueError(f"refusing git with an unusable root: {root!r}")
    return subprocess.run(
        ["git", "-C", root, *args],
        capture_output=True, text=True, env=_env(home or os.path.dirname(root)),
    ).returncode


def live_tree_signature() -> str:
    """The live repository's porcelain status — the witness that fixtures stayed home."""
    proc = subprocess.run(
        ["git", "-C", LIVE_ROOT, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    return proc.stdout
