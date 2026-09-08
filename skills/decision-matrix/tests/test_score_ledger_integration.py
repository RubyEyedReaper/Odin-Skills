"""Tests for scripts/score.py Sprint 4 wiring: ledger recording + recall + revisit reminder.

Written before implementation (TDD RED phase). Library/default calls must NOT write any
files — only record=True (always with an explicit tmp decisions_dir in tests) writes.
"""
import json
import tempfile
import unittest
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.score import run, resolve_decisions_dir, DEFAULT_DECISIONS_DIR


def _spec(**overrides):
    spec = {
        "goal": "Pick the best caching layer for the API",
        "reversibility": "two-way",
        "constraints": [],
        "options": [
            {"id": "redis", "label": "Redis"},
            {"id": "memcached", "label": "Memcached"},
        ],
        "criteria": [
            {"id": "features", "label": "Feature Set", "weight": 60, "direction": "higher-is-better"},
            {"id": "ops", "label": "Ops Simplicity", "weight": 40, "direction": "higher-is-better"},
        ],
        "scorers": [{
            "id": "s1", "label": "Team",
            "scores": {
                "redis": {"features": {"value": 90}, "ops": {"value": 70}},
                "memcached": {"features": {"value": 50}, "ops": {"value": 85}},
            },
        }],
        "methods": ["weighted-sum"],
        "tie_threshold": 5,
    }
    spec.update(overrides)
    return spec


class TestRunDefaultNoRecord(unittest.TestCase):
    """Default behavior (record=False) must never write files."""

    def test_default_record_false_no_decisions_dir_writes(self):
        result, exit_code = run(_spec())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["prior_decisions"], [])
        self.assertIsNone(result["dec_record_path"])

    def test_explicit_record_false_with_decisions_dir_still_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result, exit_code = run(_spec(), decisions_dir=decisions_dir, record=False)
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["prior_decisions"], [])
            self.assertIsNone(result["dec_record_path"])
            self.assertFalse(decisions_dir.exists())


class TestRunWithRecord(unittest.TestCase):

    def test_record_true_writes_dec_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result, exit_code = run(_spec(), decisions_dir=decisions_dir, record=True)
            self.assertEqual(exit_code, 0)
            self.assertIsNotNone(result["dec_record_path"])
            dec_path = Path(result["dec_record_path"])
            self.assertTrue(dec_path.exists())
            self.assertTrue(dec_path.name.startswith("DEC-0001-"))

    def test_a_reserved_id_binds_end_to_end(self):
        """harness:RM-0165, the whole point. A worker handed DEC-0042 in writing could not
        make the engine use it: `run` took max+1 and the worker renamed the file and
        repaired the index row afterwards. Now the reservation reaches the filename, the
        frontmatter and the index row in one pass."""
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result, exit_code = run(
                _spec(), decisions_dir=decisions_dir, record=True, dec_id="DEC-0042"
            )
            self.assertEqual(exit_code, 0)
            dec_path = Path(result["dec_record_path"])
            self.assertTrue(dec_path.name.startswith("DEC-0042-"), dec_path.name)
            self.assertIn("dec_id: DEC-0042", dec_path.read_text(encoding="utf-8"))
            self.assertIn(
                "| DEC-0042 |", (decisions_dir / "README.md").read_text(encoding="utf-8")
            )

    def test_a_reserved_id_that_is_taken_is_refused_not_moved(self):
        """The negative control, and the reason this is a refusal rather than a bump: a run
        that asked for DEC-0042 and silently got DEC-0043 writes 0043's record under 0042's
        name in the filename, the frontmatter, the index row and the commit message.

        The second run scores a DIFFERENT decision, and that is load-bearing rather
        than cosmetic. This case used to re-run the identical spec, which made the
        fixture two things at once: a collision between two decisions over one id,
        and a retry of one decision after a transport failure. Those want opposite
        answers — refuse the first, reuse the second — and the fixture could not
        distinguish them. It asserted the refusal only because reuse did not exist
        yet.
        """
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            run(_spec(), decisions_dir=decisions_dir, record=True, dec_id="DEC-0042")
            other = _spec(goal="Pick the queue for outbound webhooks")
            with self.assertRaises(Exception) as caught:
                run(other, decisions_dir=decisions_dir, record=True, dec_id="DEC-0042")
            self.assertIn("already spoken for", str(caught.exception))

    def test_a_retry_asking_for_the_same_id_reuses_rather_than_colliding(self):
        """The other half of the pair above: an identical spec asking again for the
        id it already holds is a retry, and the id it names is its own."""
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            first, _ = run(_spec(), decisions_dir=decisions_dir, record=True, dec_id="DEC-0042")
            second, code = run(_spec(), decisions_dir=decisions_dir, record=True, dec_id="DEC-0042")

            self.assertEqual(code, 0)
            self.assertTrue(second.get("dec_record_reused"))
            self.assertEqual(first["dec_record_path"], second["dec_record_path"])

    def test_record_true_writes_readme_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            run(_spec(), decisions_dir=decisions_dir, record=True)
            readme = decisions_dir / "README.md"
            self.assertTrue(readme.exists())

    def test_record_true_sets_promote_to_adr_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result, _ = run(_spec(reversibility="one-way"), decisions_dir=decisions_dir, record=True)
            self.assertTrue(result["promote_to_adr_hint"])

    def test_record_true_second_run_increments_dec_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result1, _ = run(_spec(), decisions_dir=decisions_dir, record=True)
            result2, _ = run(_spec(goal="Pick a different cache layer"), decisions_dir=decisions_dir, record=True)
            self.assertNotEqual(
                Path(result1["dec_record_path"]).name,
                Path(result2["dec_record_path"]).name,
            )
            self.assertTrue(Path(result2["dec_record_path"]).name.startswith("DEC-0002-"))

    def test_record_true_populates_prior_decisions_on_second_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            run(_spec(), decisions_dir=decisions_dir, record=True)
            result2, _ = run(_spec(), decisions_dir=decisions_dir, record=True)
            self.assertGreater(len(result2["prior_decisions"]), 0)

    def test_vetoed_all_options_with_record_true_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            spec = _spec()
            spec["options"][0]["constraint_results"] = {"x": False}
            spec["options"][1]["constraint_results"] = {"x": False}
            result, exit_code = run(spec, decisions_dir=decisions_dir, record=True)
            self.assertEqual(exit_code, 0)
            # No winner to record; result should still have the keys, even if no DEC was written.
            self.assertIn("prior_decisions", result)
            self.assertIn("dec_record_path", result)


class TestVetoReasonsInResult(unittest.TestCase):
    """harness:RM-0228 — the reason must travel in the result, not only in the renderer.

    `_render_visual` hands `visual.mjs` the result and nothing else, so a reason that lives
    only inside the markdown writer can never reach the HTML companion of the same DEC, and
    the two files of one decision would disagree.
    """

    def _vetoed_spec(self):
        spec = _spec(constraints=[
            {"id": "self-hostable", "description": "Must be self-hostable on our own hardware"},
        ])
        spec["options"][0]["constraint_results"] = {"self-hostable": False}
        spec["options"][1]["constraint_results"] = {"self-hostable": True}
        return spec

    def test_the_normal_path_carries_the_reason(self):
        result, exit_code = run(self._vetoed_spec())

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["veto_reasons"], [{
            "option": "redis",
            "option_label": "Redis",
            "constraints": [{
                "id": "self-hostable",
                "description": "Must be self-hostable on our own hardware",
                "lifted_by": None,
            }],
        }])

    def test_nothing_vetoed_is_an_empty_list_not_a_missing_key(self):
        result, _ = run(_spec())
        self.assertEqual(result["veto_reasons"], [])

    def test_the_all_options_vetoed_path_carries_it_too(self):
        """The path that returns early, before any of the scoring pipeline runs.

        Two result dicts are built by hand in this module and have already drifted from
        each other; this is the case that fails if only one of them is edited.
        """
        spec = _spec(constraints=[
            {"id": "self-hostable", "description": "Must be self-hostable"},
        ])
        spec["options"][0]["constraint_results"] = {"self-hostable": False}
        spec["options"][1]["constraint_results"] = {"self-hostable": False}

        result, exit_code = run(spec)

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["recommendation"]["rationale"], "all options vetoed")
        self.assertEqual([v["option"] for v in result["veto_reasons"]], ["redis", "memcached"])
        self.assertEqual(
            result["veto_reasons"][0]["constraints"][0]["description"], "Must be self-hostable"
        )

    def test_a_non_recording_run_carries_it_and_still_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            result, _ = run(self._vetoed_spec(), decisions_dir=decisions_dir, record=False)

            self.assertEqual(len(result["veto_reasons"]), 1)
            self.assertFalse(decisions_dir.exists())

    def test_the_explanation_cannot_drift_from_the_partition(self):
        """Across every golden fixture, in order — not just as sets.

        Three of the seven carry a veto. If the two lists are ever computed by different
        predicates, this is what says so.
        """
        fixtures_dir = (
            Path(__file__).resolve().parent.parent / "evals" / "fixtures"
        )
        specs = sorted(
            p for p in fixtures_dir.glob("*.json") if not p.name.endswith(".expected.json")
        )
        self.assertGreaterEqual(len(specs), 7, "the skill's golden fixtures are missing")

        vetoed_seen = 0
        for path in specs:
            with self.subTest(fixture=path.name):
                result, _ = run(json.loads(path.read_text(encoding="utf-8")))
                self.assertEqual(
                    [v["option"] for v in result["veto_reasons"]],
                    result["vetoed_options"],
                    f"{path.name}: veto_reasons and vetoed_options disagree",
                )
                vetoed_seen += len(result["vetoed_options"])

        self.assertGreater(vetoed_seen, 0, "no fixture vetoes anything — this asserts nothing")

    def test_a_round_trip_proves_the_recorded_file_carries_the_constraint_text(self):
        """The acceptance is about the file on disk, not about a dict a function returned.

        Runs the real entry point against the skill's own hiring-candidate fixture — which
        vetoes candidate-c on the declared constraint `salary-band` — records it, and reads
        the produced markdown back off the path the run reported.
        """
        fixture = (
            Path(__file__).resolve().parent.parent
            / "evals" / "fixtures" / "hiring-candidate.json"
        )
        spec = json.loads(fixture.read_text(encoding="utf-8"))
        declared = next(c for c in spec["constraints"] if c["id"] == "salary-band")

        with tempfile.TemporaryDirectory() as tmp:
            result, exit_code = run(spec, decisions_dir=Path(tmp) / "decisions", record=True)
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["vetoed_options"], ["candidate-c"])

            text = Path(result["dec_record_path"]).read_text(encoding="utf-8")

            self.assertIn("salary-band", text)
            self.assertIn(declared["description"], text)
            # The sections that were already there must survive the insertion.
            for heading in ("## Recommendation", "## Scored Matrix", "## Sensitivity"):
                self.assertIn(heading, text)

    def test_the_round_trip_fixture_is_one_a_reader_could_misread(self):
        """The case above proves nothing if the vetoed option was going to lose anyway.

        Cora outscores the winner outright on Collaboration & Communication — 82.8 to 52.0,
        the widest gap in the table — so her row is exactly the shape that reads as a strong
        contender when its total is a bare em-dash.
        """
        fixture = (
            Path(__file__).resolve().parent.parent
            / "evals" / "fixtures" / "hiring-candidate.json"
        )
        result, _ = run(json.loads(fixture.read_text(encoding="utf-8")))

        winner = result["recommendation"]["winner"]
        vetoed = result["vetoed_options"][0]
        agg = result["aggregated_scores"]
        beaten = [
            cid for cid in agg[vetoed]
            if agg[vetoed][cid]["confidence_adjusted"] > agg[winner][cid]["confidence_adjusted"]
        ]
        self.assertTrue(beaten, "the vetoed fixture option is beaten everywhere — it proves nothing")
        widest = max(
            agg[vetoed][cid]["confidence_adjusted"] - agg[winner][cid]["confidence_adjusted"]
            for cid in beaten
        )
        self.assertGreater(widest, 25.0, "the vetoed option's lead is too small to misread")


class TestRevisitReminder(unittest.TestCase):

    def test_revisit_after_days_two_way_sets_reminder(self):
        result, _ = run(_spec(revisit_after_days=30))
        self.assertIn("revisit_reminder", result)
        self.assertIn("due_date", result["revisit_reminder"])
        self.assertIn("message", result["revisit_reminder"])

    def test_no_revisit_after_days_no_reminder_key_or_none(self):
        result, _ = run(_spec())
        # Either absent or explicitly None — must not silently populate a reminder.
        self.assertIn(result.get("revisit_reminder"), [None, {}])

    def test_revisit_after_days_one_way_no_reminder(self):
        result, _ = run(_spec(revisit_after_days=30, reversibility="one-way"))
        self.assertIn(result.get("revisit_reminder"), [None, {}])

    def test_due_date_is_n_days_from_today(self):
        import datetime
        result, _ = run(_spec(revisit_after_days=7))
        due_date = result["revisit_reminder"]["due_date"]
        expected = (datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=7))
        self.assertEqual(due_date, expected.isoformat())


class TestDecisionsDirResolution(unittest.TestCase):
    """A decision about a project belongs in that project's ledger, not the harness one.

    The engine is mandated to run with its CWD inside the skill directory, so the working
    directory carries no information about who owns the decision. The spec declares it.
    Precedence: explicit argument > spec's `decisions_dir` > harness default.
    """

    def test_spec_key_beats_the_harness_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            declared = Path(tmp) / "projects" / "demo" / "docs" / "decisions"
            resolved = resolve_decisions_dir(_spec(decisions_dir=str(declared)), None)
            self.assertEqual(resolved, declared.resolve())

    def test_explicit_argument_beats_the_spec_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            declared = Path(tmp) / "from-spec"
            override = Path(tmp) / "from-flag"
            resolved = resolve_decisions_dir(_spec(decisions_dir=str(declared)), override)
            self.assertEqual(resolved, override)

    def test_neither_falls_back_to_the_harness_ledger(self):
        resolved = resolve_decisions_dir(_spec(), None)
        self.assertEqual(resolved, DEFAULT_DECISIONS_DIR)

    def test_relative_spec_path_resolves_against_the_repo_not_the_skill_dir(self):
        # The mandated CWD is the skill directory; resolving a relative path against it
        # would bury a project's ledger inside the skill.
        resolved = resolve_decisions_dir(
            _spec(decisions_dir="projects/decision-matrix-web/docs/decisions"), None
        )
        self.assertTrue(
            str(resolved).endswith("/projects/decision-matrix-web/docs/decisions"), resolved
        )
        self.assertNotIn("/.claude/skills/", str(resolved))

    def test_a_run_records_where_the_spec_declares(self):
        with tempfile.TemporaryDirectory() as tmp:
            declared = Path(tmp) / "docs" / "decisions"
            result, exit_code = run(_spec(decisions_dir=str(declared)), record=True)
            self.assertEqual(exit_code, 0)
            self.assertTrue(Path(result["dec_record_path"]).is_relative_to(declared))


class TestRecordedIdSurvivesACollision(unittest.TestCase):
    """End-to-end reproduction of the id/index-row desync.

    Simulates a concurrent session claiming the next number between this run's read and
    its write. The recorded file, the run's reported path, and the ledger row must all
    name the same DEC.
    """

    def test_ledger_row_names_the_file_that_was_written(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"
            decisions_dir.mkdir(parents=True)
            (decisions_dir / "DEC-0001-claimed-by-another-session.md").write_text(
                "---\ndec_id: DEC-0001\n---\n", encoding="utf-8"
            )

            # The race: this run read the number *before* the other session's file landed,
            # so it walks in holding a number that is no longer free.
            with mock.patch("scripts.score.next_dec_number", return_value=1):
                result, exit_code = run(_spec(), decisions_dir=decisions_dir, record=True)
            self.assertEqual(exit_code, 0)

            written = Path(result["dec_record_path"]).name
            written_id = written[: len("DEC-0000")]
            readme = (decisions_dir / "README.md").read_text(encoding="utf-8")

            self.assertEqual(written_id, "DEC-0002")
            self.assertIn(f"| {written_id} |", readme)
            self.assertIn(written, readme)
            # The other session's record is on disk, so it HAS a row — the index is
            # rendered from every record, and reflecting one is not inventing one
            # (harness:RM-0224). What must not happen is this run's row landing under
            # the other session's id: DEC-0001's row links the other session's file.
            self.assertIn("DEC-0001-claimed-by-another-session.md", readme)
            self.assertNotIn(f"| DEC-0001 | {written}", readme)


class TestRunSignatureIsKeywordOnly(unittest.TestCase):
    """decisions_dir / record must be keyword-only per spec: run(spec, *, decisions_dir=None, record=False)."""

    def test_cannot_pass_decisions_dir_positionally(self):
        with self.assertRaises(TypeError):
            run(_spec(), None, True)


if __name__ == "__main__":
    unittest.main()


class TestAmbiguousLedgerWarning(unittest.TestCase):
    """Guard 2 of issue #244, in the form DEC-0023 chose.

    When the workspace holds project ledgers and the spec names none, the destination is
    ambiguous: the run is about to write into the harness ledger on the strength of a
    default rather than a declaration. That warns on stderr and proceeds — it does not
    refuse, because a refusal would break `roadmap`'s documented `prioritize --record`
    chain, whose files this change is not authorized to fix. DEC-0023 records the veto,
    the scoring, and the condition under which `refuse` becomes available.

    stderr, never stdout: stdout is the result document a caller pipes into jq.
    """

    def _spec(self, decisions_dir=None):
        spec = {
            "goal": "Ambiguity fixture",
            "reversibility": "two-way",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "criteria": [
                {"id": "c1", "label": "C1", "weight": 100, "direction": "higher-is-better"}
            ],
            "scorers": [
                {
                    "id": "s1",
                    "label": "S1",
                    "scores": {
                        "a": {"c1": {"value": 80, "confidence": 1}},
                        "b": {"c1": {"value": 20, "confidence": 1}},
                    },
                }
            ],
            "methods": ["weighted-sum"],
        }
        if decisions_dir is not None:
            spec["decisions_dir"] = decisions_dir
        return spec

    def _root_with_project_ledger(self, tmp):
        root = Path(tmp)
        (root / ".claude" / "docs" / "decisions").mkdir(parents=True)
        (root / "projects" / "demo" / "docs" / "decisions").mkdir(parents=True)
        return root

    def _run_capturing_stderr(self, spec, **kwargs):
        import io
        from contextlib import redirect_stderr

        buf = io.StringIO()
        with redirect_stderr(buf):
            result, code = run(spec, **kwargs)
        return result, code, buf.getvalue()

    def test_warns_and_still_records_when_the_destination_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_project_ledger(tmp)
            harness = root / ".claude" / "docs" / "decisions"

            result, code, err = self._run_capturing_stderr(
                self._spec(), decisions_dir=harness, record=True, workspace_root=root
            )

            self.assertEqual(code, 0, "the run completes — this warns, it does not refuse")
            self.assertIsNotNone(result.get("dec_record_path"), "the record was still written")
            self.assertIn("ambiguous", err.lower())
            self.assertIn("projects/demo/docs/decisions", err.replace(os.sep, "/"))
            self.assertIn("decisions_dir", err, "the remedy is named, not merely the problem")

    def test_a_spec_that_declares_its_ledger_is_never_warned_about(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_project_ledger(tmp)
            project = root / "projects" / "demo" / "docs" / "decisions"

            result, code, err = self._run_capturing_stderr(
                self._spec(decisions_dir=str(project)),
                record=True,
                workspace_root=root,
            )

            self.assertEqual(code, 0)
            self.assertNotIn("ambiguous", err.lower())
            self.assertIn("projects", result["dec_record_path"], "recorded where it was declared")

    def test_an_explicit_flag_is_never_warned_about(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_project_ledger(tmp)
            harness = root / ".claude" / "docs" / "decisions"

            _, code, err = self._run_capturing_stderr(
                self._spec(), decisions_dir=harness, record=True, workspace_root=root,
                declared_destination=True,
            )
            self.assertEqual(code, 0)
            self.assertNotIn("ambiguous", err.lower())

    def test_a_workspace_with_no_project_ledger_is_never_warned_about(self):
        """The genuine-harness-decision case, and the one that must not regress: a
        checkout with no project ledger has no ambiguity to report."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            harness = root / ".claude" / "docs" / "decisions"
            harness.mkdir(parents=True)

            result, code, err = self._run_capturing_stderr(
                self._spec(), decisions_dir=harness, record=True, workspace_root=root
            )

            self.assertEqual(code, 0)
            # Scoped to the ambiguity warning, which is what this case owns. stderr is a
            # shared channel: the id allocator announces a degrade there too, and asserting
            # the whole stream empty makes this case fail whenever any unrelated subsystem
            # correctly says something. The invariant is "no warning", not "no output".
            warnings = [ln for ln in err.splitlines() if ln.startswith("warning:")]
            self.assertEqual(warnings, [], "silence when there is nothing to disambiguate")
            self.assertIsNotNone(result.get("dec_record_path"))

    def test_a_non_recording_run_is_never_warned_about(self):
        """A scoring run writes nothing, so it has no destination to be ambiguous about.
        Warning there would fire on the common case."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_project_ledger(tmp)

            _, code, err = self._run_capturing_stderr(
                self._spec(), record=False, workspace_root=root
            )

            self.assertEqual(code, 0)
            self.assertEqual(err, "")

    def test_candidate_ledgers_are_listed_repo_relative_and_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_project_ledger(tmp)
            (root / "projects" / "alpha" / "docs" / "decisions").mkdir(parents=True)
            harness = root / ".claude" / "docs" / "decisions"

            _, _, err = self._run_capturing_stderr(
                self._spec(), decisions_dir=harness, record=True, workspace_root=root
            )
            normalized = err.replace(os.sep, "/")
            self.assertLess(
                normalized.index("projects/alpha/docs/decisions"),
                normalized.index("projects/demo/docs/decisions"),
                "candidates are sorted, so the message is stable across machines",
            )
                # The warning block is what must carry repo-relative paths; a diagnostic from
            # another subsystem naming an absolute path is not this invariant's business.
            warning_block = err.split("note:")[0]
            self.assertNotIn(str(root), warning_block,
                             "paths are repo-relative, not absolute")


class TestRecordIdempotence(unittest.TestCase):
    """`--record` run twice on one spec must produce one record, not two.

    THE INCIDENT (KinNest ledger, 2026-09-07). The engine wrote DEC-0050 and
    DEC-0051 and exited 0; the shell pipe consuming its stdout errored, the
    operator read that as a failed run and retried, and the retry allocated
    DEC-0052 and DEC-0053 for the same two decisions. Nothing detected it — the
    duplicates were found by eye and removed by hand, and the ledger carries the
    gap.

    The engine cannot see a broken pipe, but it can see that this exact spec has
    already been recorded, which is the condition that actually matters.
    """

    def test_a_second_record_of_one_spec_returns_the_first_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"

            first, code_a = run(_spec(), decisions_dir=decisions_dir, record=True)
            second, code_b = run(_spec(), decisions_dir=decisions_dir, record=True)

            self.assertEqual(code_a, 0)
            self.assertEqual(code_b, 0)
            self.assertEqual(first["dec_record_path"], second["dec_record_path"])
            self.assertTrue(second.get("dec_record_reused"))
            self.assertFalse(first.get("dec_record_reused"))

            records = sorted(decisions_dir.glob("DEC-*.md"))
            self.assertEqual(
                len(records), 1,
                "a retried --record wrote a second record for the same spec: %s" % records,
            )

    def test_a_changed_weight_is_a_new_decision_and_gets_its_own_record(self):
        # The inverse case, and the reason the fingerprint is over the spec
        # rather than over the goal: re-scoring with different weights is the
        # documented way to revisit a decision, and it must still record.
        with tempfile.TemporaryDirectory() as tmp:
            decisions_dir = Path(tmp) / "decisions"

            run(_spec(), decisions_dir=decisions_dir, record=True)

            reweighted = _spec()
            reweighted["criteria"] = [
                {"id": "features", "label": "Feature Set", "weight": 30,
                 "direction": "higher-is-better"},
                {"id": "ops", "label": "Ops Simplicity", "weight": 70,
                 "direction": "higher-is-better"},
            ]
            second, _ = run(reweighted, decisions_dir=decisions_dir, record=True)

            self.assertFalse(second.get("dec_record_reused"))
            self.assertEqual(len(sorted(decisions_dir.glob("DEC-*.md"))), 2)
