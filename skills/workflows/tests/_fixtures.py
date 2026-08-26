"""Fixture builders shared by the three test modules.

Named with a leading underscore so `unittest discover`'s `test*.py` pattern does not
collect it: a helper module that reports itself as a test suite is how a suite comes to
claim more coverage than it has.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

# The skill directory, so `import scripts.workflow` resolves however the test is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MANIFEST_DIR = os.path.join(".claude", "docs", "workflows")


def valid_manifest(workflow_id: str = "sample-chain", **overrides) -> dict:
    """A manifest that passes every rule, before overrides are applied."""
    manifest = {
        "id": workflow_id,
        "version": "1.0.0",
        "status": "active",
        "owner": "harness",
        "supersedes": None,
        "inputs": ["a failing test name"],
        "outputs": ["a committed reproduction test"],
        "dependencies": [],
        "decision_points": [
            {"at": 2, "question": "is the root cause confirmed?"},
        ],
        "failure_handling": [
            {"when": "the reproduction does not fail", "action": "return to step 1"},
        ],
        "completion_criteria": ["the reproduction test passes"],
        "steps": [
            {"step": 1, "skill": "systematic-debugging", "gates": "diagnosis before fixes"},
            {"step": 2, "skill": "diagnosing-bugs", "gates": "root cause confirmed"},
        ],
    }
    manifest.update(overrides)
    return manifest


def render(manifest: dict | None, *, blocks: int = 1, raw: str | None = None) -> str:
    """Render a manifest file: prose around `blocks` fenced JSON blocks."""
    body = ["# Sample chain", "", "Prose a human reads.", ""]
    for _ in range(blocks):
        body.append("```json")
        body.append(raw if raw is not None else json.dumps(manifest, indent=2))
        body.append("```")
        body.append("")
    return "\n".join(body)


class RootFixture:
    """A throwaway repository root with a manifest directory under it."""

    def __init__(self, *, create_dir: bool = True):
        self.root = tempfile.mkdtemp(prefix="workflow-fixture-")
        self.manifests = os.path.join(self.root, MANIFEST_DIR)
        if create_dir:
            os.makedirs(self.manifests)

    def write(self, manifest: dict | None, *, name: str | None = None, **render_kw) -> str:
        stem = name if name is not None else manifest["id"]
        path = os.path.join(self.manifests, f"{stem}.workflow.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(render(manifest, **render_kw))
        return path

    def read(self, workflow_id: str) -> dict:
        from scripts.workflow import read_manifest

        return read_manifest(os.path.join(self.manifests, f"{workflow_id}.workflow.md"))

    def runtime(self, session: str) -> str:
        return os.path.join(self.root, ".claude", ".runtime", "workflow-run", session)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
