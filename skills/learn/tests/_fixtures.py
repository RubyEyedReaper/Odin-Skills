"""Fixture builders shared by the two test modules.

Named with a leading underscore so `unittest discover`'s `test*.py` pattern does not
collect it: a helper module that reports itself as a test suite is how a suite comes to
claim more coverage than it has.

**Every synthetic secret in this file is assembled by concatenation** rather than written
as a literal token. Two reasons, both real. `secret-scan.sh` runs gitleaks over the full
history of this repository, and a literal `AKIA…`-shaped string is a finding whether or
not the key was ever valid — a fixture that reds the repository's own secret gate is a
defect, not a test. And a value that never exists as a contiguous token in a tracked file
cannot be copied out of one.
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

# The skill directory, so `import scripts.capture_bar` resolves however the test is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --------------------------------------------------------------- synthetic secrets

#: AWS access-key-id shape: AKIA + 16 upper-alphanumerics. Assembled, never literal.
FAKE_AWS_KEY = "AKIA" + ("EXAMPLE" * 2) + "12"

#: GitHub personal-access-token shape: ghp_ + 36 alphanumerics.
FAKE_GH_TOKEN = "ghp" + "_" + ("EXAMPLE" * 5) + "X"

#: A vendor-style API key: sk- + 32 alphanumerics.
FAKE_API_KEY = "sk" + "-" + ("EXAMPLE" * 4) + "TAIL"

assert len(FAKE_AWS_KEY) == 20
assert len(FAKE_GH_TOKEN) == 40
assert len(FAKE_API_KEY) == 35


class Root:
    """A throwaway tree: a fake repository, a corpus directory, and a scratch space.

    No case may read the live memory tier or the real `HOME`; every path a test hands the
    engine is rooted here.
    """

    def __enter__(self) -> "Root":
        self.path = tempfile.mkdtemp(prefix="learn-test-")
        self.repo = os.path.join(self.path, "repo")
        self.corpus = os.path.join(self.path, "corpus")
        os.makedirs(self.repo)
        os.makedirs(self.corpus)
        return self

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def tracked(self, relpath: str, text: str) -> str:
        """Write a file into the fake repository."""
        full = os.path.join(self.repo, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)
        return full

    def record(self, name: str, text: str) -> str:
        """Write an existing record into the corpus."""
        full = os.path.join(self.corpus, name)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)
        return full

    def candidate(self, **fields) -> str:
        """Write a candidate record as JSON and return its path."""
        import json

        full = os.path.join(self.path, "candidate.json")
        with open(full, "w", encoding="utf-8") as handle:
            json.dump(fields, handle)
        return full

    def scratch(self, name: str, text: str) -> str:
        full = os.path.join(self.path, name)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)
        return full


def run_cli(*argv) -> tuple[int, str, str]:
    """Invoke the engine in-process; stdout is data, stderr is diagnostics."""
    from scripts.capture_bar import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def check(root: Root, *, corpus: bool = True, **fields) -> tuple[int, str, str]:
    """`check` over a candidate built from `fields`, aimed at the fixture tree."""
    argv = ["check", "--candidate", root.candidate(**fields), "--root", root.repo]
    if corpus:
        argv += ["--corpus", root.corpus]
    return run_cli(*argv)


def a_finding(**overrides) -> dict:
    """A record that passes every class: a durable, non-obvious harness finding."""
    fields = {
        "title": "A shadow database is nominated, never created",
        "body": (
            "prisma migrate diff destroys whatever database URL is handed to its "
            "shadow flag, so the guard requires the target be named shadow rather "
            "than trusting the caller to have nominated a scratch database."
        ),
        "confidence": "gated",
        "verified_by": "bash .claude/tests/safety-guard.test.sh",
        "verified_on": "2026-08-27",
    }
    fields.update(overrides)
    return fields
