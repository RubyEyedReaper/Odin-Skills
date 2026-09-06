"""Matrix for the gauntlet engine.

Every case here asserts a behaviour that was chosen against a weaker alternative, and several
BREAK the input on purpose so that "it passes" is distinguishable from "it does nothing".

Run:
    cd .claude/skills/gauntlet && python3 -m unittest discover -s tests -t . -v

Confirm the collected count is NON-ZERO. `tests/__init__.py` is what makes discovery work;
without it the suite passes having examined nothing.
"""

import json
import os
import shutil
import tempfile
import unittest

from scripts import gauntlet


def item(id_, **kw):
    """A roadmap item with the fields the engine reads, overridable per case."""
    base = {
        "id": id_,
        "title": f"item {id_}",
        "kind": "ops",
        "tier": "next",
        "status": "proposed",
        "acceptance": ["it is done when the gate exits 0"],
        "deps": [],
        "priority": None,
        "links": {"files": [], "issues": [], "plan": None, "adr": None, "prd": None},
    }
    base.update(kw)
    return base


class Fixture:
    """A throwaway repository root holding only what the engine reads."""

    def __init__(self, items, campaigns=None, ledgers=None, slug="harness"):
        self.root = tempfile.mkdtemp(prefix="gauntlet-test-")
        rm_dir = os.path.join(self.root, ".claude", "docs", "roadmap")
        os.makedirs(rm_dir)
        with open(os.path.join(rm_dir, "roadmap.json"), "w", encoding="utf-8") as fh:
            json.dump({"schema": 1, "slug": slug, "scope": "operational", "items": items}, fh)

        camp_dir = os.path.join(self.root, ".claude", "docs", "campaigns")
        os.makedirs(camp_dir)
        for name, doc in (campaigns or {}).items():
            with open(os.path.join(camp_dir, name), "w", encoding="utf-8") as fh:
                fh.write(doc if isinstance(doc, str) else json.dumps(doc))

        if ledgers:
            loop_dir = os.path.join(self.root, ".claude", ".runtime", "work-loop")
            os.makedirs(loop_dir)
            for name, doc in ledgers.items():
                with open(os.path.join(loop_dir, name), "w", encoding="utf-8") as fh:
                    json.dump(doc, fh)

    def destroy(self):
        shutil.rmtree(self.root, ignore_errors=True)


class QuickwinTest(unittest.TestCase):
    """The ordering reads declared fields, and says so when a field is not there."""

    def test_gain_reads_tier_when_no_recorded_score(self):
        out = gauntlet.quickwin(item("RM-1", tier="now"))
        self.assertEqual(out["provenance"], "tier")
        self.assertEqual(out["factors"]["gain"]["from"], "tier")
        self.assertEqual(out["factors"]["gain"]["value"], 3.0)

    def test_recorded_score_overrides_the_tier_proxy(self):
        """A recorded DEC beats a heuristic; the output says which one it used."""
        out = gauntlet.quickwin(
            item("RM-2", tier="someday", priority={"score": 50, "dec": "DEC-0085"})
        )
        self.assertEqual(out["provenance"], "scored")
        self.assertEqual(out["factors"]["gain"]["from"], "priority.score")
        self.assertEqual(out["factors"]["gain"]["value"], 2.0)

    def test_no_acceptance_is_unscored_not_discounted(self):
        """The regression this rule exists for.

        As a 0.4 multiplier, an item with NOTHING declared out-ranked a fully declared one:
        no acceptance also collapsed `cost` to its floor of 1, and `3.0 x 0.4 / 1` beat
        `3.0 x 1.0 / 3`. Undeclared work sorted FIRST in a quick-win ordering.
        """
        bare = gauntlet.quickwin(item("RM-3", tier="now", acceptance=[]))
        self.assertIsNone(bare["score"])
        self.assertEqual(bare["provenance"], "underdeclared")

        declared = gauntlet.quickwin(item("RM-4", tier="now", acceptance=["a", "b"]))
        self.assertIsNotNone(declared["score"])

    def test_unranked_kind_is_unscored(self):
        out = gauntlet.quickwin(item("RM-5", kind="sorcery"))
        self.assertIsNone(out["score"])
        self.assertEqual(out["provenance"], "underdeclared")

    def test_cost_rises_with_acceptance_and_deps(self):
        cheap = gauntlet.quickwin(item("RM-6", acceptance=["one"]))
        dear = gauntlet.quickwin(item("RM-7", acceptance=["one", "two", "three"], deps=["RM-6"]))
        self.assertGreater(cheap["score"], dear["score"])

    def test_every_factor_names_the_field_it_read(self):
        out = gauntlet.quickwin(item("RM-8"))
        for factor in ("gain", "confidence", "reversibility", "cost"):
            self.assertIn("from", out["factors"][factor], f"{factor} does not name its field")


class SurfaceTest(unittest.TestCase):
    """The collision check reads declared paths, and withholds where none are declared."""

    def test_identical_and_prefix_surfaces_collide(self):
        self.assertTrue(gauntlet.surfaces_intersect([".claude/scripts/a.sh"],
                                                    [".claude/scripts/a.sh"]))
        self.assertTrue(gauntlet.surfaces_intersect([".claude/scripts/"],
                                                    [".claude/scripts/a.sh"]))

    def test_glob_and_literal_collide(self):
        self.assertTrue(gauntlet.surfaces_intersect([".claude/skills/**"],
                                                    [".claude/skills/roadmap/SKILL.md"]))

    def test_disjoint_surfaces_do_not_collide(self):
        self.assertFalse(gauntlet.surfaces_intersect([".claude/scripts/a.sh"],
                                                     [".claude/tests/b.test.sh"]))

    def test_negative_control_the_title_predicate_would_fail(self):
        """The control that proves this predicate does work the obvious one does not.

        A weaker check — "do two items MENTION the same file?" — reports a collision for these
        two, because both titles name `ci-local.sh`. Their declared surfaces are disjoint: one
        edits the script, the other edits the matrix that tests it. Co-scheduling them is
        correct, and the title predicate would have serialised them forever.
        """
        a = item("RM-9", title="ci-local.sh loses a step",
                 links={"files": [".claude/scripts/ci-local.sh"], "issues": []})
        b = item("RM-10", title="the matrix for ci-local.sh never fires",
                 links={"files": [".claude/tests/gate-wiring.test.sh"], "issues": []})
        self.assertIn("ci-local.sh", a["title"])
        self.assertIn("ci-local.sh", b["title"])
        self.assertFalse(
            gauntlet.surfaces_intersect(gauntlet.surface_of(a), gauntlet.surface_of(b))
        )

    def test_converse_control_titles_share_nothing_but_surfaces_overlap(self):
        """And the other half: prose agreement is neither necessary nor sufficient."""
        a = item("RM-11", title="a stale count in the runbook",
                 links={"files": [".claude/docs/odin-runbook.md"], "issues": []})
        b = item("RM-12", title="document the new gate",
                 links={"files": [".claude/docs/**"], "issues": []})
        self.assertTrue(
            gauntlet.surfaces_intersect(gauntlet.surface_of(a), gauntlet.surface_of(b))
        )

    def test_mid_pattern_glob_on_a_dotted_path_collides(self):
        """The CRITICAL the first critic pass found, and the case no earlier test covered.

        `_normalise` used `lstrip("./")` — a character-class strip — so it ate the leading dot of
        every dotted path and `fnmatch` compared a de-dotted literal against a dotted pattern.
        Every `.claude/**`-rooted mid-pattern glob pair in this repository answered "disjoint",
        which is the one namespace the skill exists to protect. Trailing globs were unaffected
        (they are cut before the comparison and caught by the prefix arm), and the undotted form
        `src/*/index.ts` worked — so nothing in the original matrix could see it.
        """
        self.assertEqual(gauntlet._normalise(".claude/docs/x.md"), ".claude/docs/x.md")
        for pattern, literal in (
            (".claude/scripts/*.sh", ".claude/scripts/ci-local.sh"),
            (".claude/skills/*/SKILL.md", ".claude/skills/gauntlet/SKILL.md"),
            (".github/workflows/*.yml", ".github/workflows/ci.yml"),
            ("src/*/index.ts", "src/a/index.ts"),
        ):
            self.assertTrue(
                gauntlet.surfaces_intersect([pattern], [literal]),
                f"{pattern} should collide with {literal}",
            )

    def test_a_leading_dot_slash_is_still_stripped(self):
        """The prefix strip the character-class strip was standing in for."""
        self.assertEqual(gauntlet._normalise("./.claude/x"), ".claude/x")
        self.assertTrue(gauntlet.surfaces_intersect(["./.claude/scripts/"], [".claude/scripts/a"]))

    def test_undeclared_surface_is_none_not_empty(self):
        self.assertIsNone(gauntlet.surface_of(item("RM-13")))
        self.assertEqual(
            gauntlet.surface_of(item("RM-14", links={"files": ["x.md"], "issues": []})), ["x.md"]
        )


class FrontierTest(unittest.TestCase):
    """Channels, counts, and the refusal to read an unread channel as an empty one."""

    def setUp(self):
        self.fx = None

    def tearDown(self):
        if self.fx:
            self.fx.destroy()

    def test_open_statuses_only(self):
        self.fx = Fixture([
            item("RM-1", status="proposed"),
            item("RM-2", status="in-progress"),
            item("RM-3", status="ready"),
            item("RM-4", status="done"),
            item("RM-5", status="dropped"),
        ])
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        self.assertEqual(payload["counts"]["roadmap"], 3)
        self.assertEqual(payload["channels"]["tracker"], "skipped (--no-tracker)")

    def test_unreadable_roadmap_is_undetermined_not_empty(self):
        self.fx = Fixture([item("RM-1")])
        with open(os.path.join(self.fx.root, ".claude", "docs", "roadmap", "roadmap.json"),
                  "w", encoding="utf-8") as fh:
            fh.write("{ this is not json")
        with self.assertRaises(gauntlet.Undetermined):
            gauntlet.build_frontier(self.fx.root, want_tracker=False)

    def test_unparsable_campaign_manifest_is_undetermined(self):
        self.fx = Fixture([item("RM-1")], campaigns={"broken.json": "{{{"})
        with self.assertRaises(gauntlet.Undetermined):
            gauntlet.build_frontier(self.fx.root, want_tracker=False)

    def test_unreadable_tracker_is_undetermined_not_a_clean_tracker(self):
        """The failure this engine exists to refuse.

        An unauthenticated `gh` and a tracker with nothing open produce the same empty list in
        every format `gh` prints. Reading the first as the second is a gauntlet reporting that
        it is finished because it could not look.
        """
        self.fx = Fixture([item("RM-1")])
        original = gauntlet._run
        gauntlet._run = lambda *a, **k: (4, "", "gh: not authenticated")
        try:
            with self.assertRaises(gauntlet.Undetermined):
                gauntlet.build_frontier(self.fx.root, want_tracker=True)
        finally:
            gauntlet._run = original

    def test_relative_root_is_refused_before_it_reaches_a_subprocess(self):
        with self.assertRaises(gauntlet.Undetermined):
            gauntlet.build_frontier("relative/path", want_tracker=False)

    def test_the_two_senses_of_blocked_stay_apart(self):
        """A rate limit must never be reported as a dependency."""
        self.fx = Fixture(
            [item("RM-1", deps=["RM-9"], status="proposed"),
             item("RM-2"),
             item("RM-9", status="proposed")],
            ledgers={"s1.json": {
                "session": "s1",
                "iterations": [{
                    "outcome": "escalate",
                    "blocker": "the deploy credential RM-2 declares is absent",
                    "evidence": "gh auth status exited 1",
                    "recommended_next": "issue a scoped token",
                }],
            }},
        )
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        by_id = {r["raw_id"]: r for r in payload["items"]}
        self.assertTrue(by_id["RM-1"]["blocked"].startswith("blocked-by-dep"))
        self.assertTrue(by_id["RM-2"]["blocked"].startswith("blocked-external"))
        self.assertEqual(payload["counts"]["blocked_by_dep"], 1)
        self.assertEqual(payload["counts"]["blocked_external"], 1)

    def test_an_unreadable_ledger_is_undetermined_not_a_dropped_blocker(self):
        """A file that EXISTS and cannot be read is a failure, not a skip.

        Skipping it dropped an externally-blocked item back into the assignable set while the
        channel still reported `read` — the same policy `read_campaign_items` already applies to
        a manifest, held oppositely two functions away.
        """
        self.fx = Fixture(
            [item("RM-1")],
            ledgers={"s1.json": {"session": "s1", "iterations": []}},
        )
        led = os.path.join(self.fx.root, ".claude", ".runtime", "work-loop", "s1.json")
        with open(led, "w", encoding="utf-8") as fh:
            fh.write("{ truncated")
        with self.assertRaises(gauntlet.Undetermined):
            gauntlet.build_frontier(self.fx.root, want_tracker=False)

    def test_an_absent_ledger_directory_is_not_undetermined(self):
        """The other half: a fresh checkout has run no loops, and that is a fact, not a failure."""
        self.fx = Fixture([item("RM-1")])
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        self.assertEqual(payload["channels"]["work-loop"], "absent")

    def test_recommended_next_does_not_name_the_blocked_item(self):
        """`recommended_next` names the SUCCESSOR, not the casualty.

        Scanning it marked RM-1 blocked on a record whose blocker was about RM-2, and left the
        item the escalation was actually about assignable.
        """
        self.fx = Fixture(
            [item("RM-1"), item("RM-2")],
            ledgers={"s1.json": {"session": "s1", "iterations": [{
                "outcome": "escalate",
                "blocker": "the credential RM-2 declares is absent",
                "evidence": "gh auth status exited 1",
                "recommended_next": "do RM-1 next instead",
            }]}},
        )
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        by_id = {r["raw_id"]: r for r in payload["items"]}
        self.assertIsNone(by_id["RM-1"]["blocked"])
        self.assertTrue(by_id["RM-2"]["blocked"].startswith("blocked-external"))

    def test_an_escalate_a_later_iteration_follows_has_expired(self):
        """`escalate` is terminal, so an iteration after it means the loop was re-opened.

        Without this a blocker never expires — the item stays blocked until somebody deletes
        the ledger file.
        """
        self.fx = Fixture(
            [item("RM-1")],
            ledgers={"s1.json": {"session": "s1", "iterations": [
                {"outcome": "escalate", "blocker": "RM-1 needs a token",
                 "evidence": "gh auth status exited 1", "recommended_next": "issue one"},
                {"outcome": "continue", "action": "token issued, work resumed"},
            ]}},
        )
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        self.assertIsNone(payload["items"][0]["blocked"])

    def test_a_tracker_read_at_the_cap_is_undetermined(self):
        """At exactly the limit, "this many" and "at least this many" are the same output."""
        self.fx = Fixture([item("RM-1")])
        original = gauntlet._run
        rows = json.dumps([{"number": n, "title": "t", "labels": [], "updatedAt": ""}
                           for n in range(3)])
        gauntlet._run = lambda *a, **k: (0, rows, "")
        try:
            with self.assertRaises(gauntlet.Undetermined):
                gauntlet.build_frontier(self.fx.root, want_tracker=True, issue_limit=3)
            payload = gauntlet.build_frontier(self.fx.root, want_tracker=True, issue_limit=4)
            self.assertEqual(payload["counts"]["tracker"], 3)
        finally:
            gauntlet._run = original

    def test_a_met_dependency_does_not_block(self):
        self.fx = Fixture([item("RM-1", deps=["RM-2"]), item("RM-2", status="done")])
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        self.assertIsNone(payload["items"][0]["blocked"])

    def test_coverage_is_reported_as_numerator_over_denominator(self):
        self.fx = Fixture([
            item("RM-1", links={"files": [".claude/a"], "issues": []}),
            item("RM-2"),
            item("RM-3"),
            item("RM-4", priority={"score": 40}),
        ])
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        cov = payload["coverage"]
        self.assertEqual((cov["surface_declared"], cov["surface_denominator"]), (1, 4))
        self.assertEqual((cov["recorded_score"], cov["score_denominator"]), (1, 4))
        self.assertEqual(cov["surface_percent"], 25.0)

    def test_campaign_claim_is_recorded_against_the_qualified_id(self):
        self.fx = Fixture(
            [item("RM-1"), item("RM-2")],
            campaigns={"c.json": {"campaign": "c", "objective": "o", "waves": [
                {"wave": 1, "workers": [{"worker": "w", "branch": "b", "item": "harness:RM-2"}]}
            ]}},
        )
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        by_id = {r["raw_id"]: r for r in payload["items"]}
        self.assertFalse(by_id["RM-1"]["claimed_by_campaign"])
        self.assertTrue(by_id["RM-2"]["claimed_by_campaign"])

    def test_scored_rows_sort_before_unscored_ones(self):
        self.fx = Fixture([item("RM-1", acceptance=[]), item("RM-2", tier="now")])
        payload = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        self.assertEqual(payload["items"][0]["raw_id"], "RM-2")
        self.assertIsNone(payload["items"][-1]["score"])


class WaveTest(unittest.TestCase):
    """What `rearm` will and will not put in one wave."""

    def setUp(self):
        self.fx = None

    def tearDown(self):
        if self.fx:
            self.fx.destroy()

    def _wave(self, items, width=4, **kw):
        self.fx = Fixture(items, **kw)
        frontier = gauntlet.build_frontier(self.fx.root, want_tracker=False)
        return gauntlet.compute_wave(frontier, width=width)

    def test_colliding_surfaces_are_never_co_scheduled(self):
        wave = self._wave([
            item("RM-1", tier="now", links={"files": [".claude/scripts/a.sh"], "issues": []}),
            item("RM-2", tier="next", links={"files": [".claude/scripts/a.sh"], "issues": []}),
        ])
        self.assertEqual(wave["counts"]["placed"], 1)
        self.assertEqual(wave["counts"]["held_collision"], 1)

    def test_disjoint_surfaces_are_co_scheduled(self):
        wave = self._wave([
            item("RM-1", tier="now", links={"files": [".claude/scripts/a.sh"], "issues": []}),
            item("RM-2", tier="now", links={"files": [".claude/tests/b.sh"], "issues": []}),
        ])
        self.assertEqual(wave["counts"]["placed"], 2)

    def test_at_most_one_unknown_surface_per_wave(self):
        """Two undeclared surfaces cannot be shown disjoint, so they are not assumed to be."""
        wave = self._wave([item("RM-1"), item("RM-2"), item("RM-3")])
        self.assertEqual(wave["counts"]["placed"], 1)
        self.assertEqual(wave["counts"]["held_surface_unknown"], 2)

    def test_blocked_items_are_never_placed(self):
        """Both fixtures declare DISJOINT surfaces, which is what makes this test load-bearing.

        With undeclared surfaces the assertion held for the wrong reason: deleting the blocked
        check left the suite green, because the one-unknown-surface-per-wave rule kept RM-1 out
        anyway. Declared and disjoint, nothing but the blocked check can hold it back.
        """
        wave = self._wave([
            item("RM-1", deps=["RM-2"], links={"files": [".claude/scripts/a.sh"], "issues": []}),
            item("RM-2", status="proposed",
                 links={"files": [".claude/tests/b.test.sh"], "issues": []}),
        ])
        placed = {w["item"] for w in wave["workers"]}
        self.assertNotIn("harness:RM-1", placed)
        self.assertIn("harness:RM-2", placed)
        self.assertEqual(wave["counts"]["held_blocked"], 1)

    def test_the_breakdown_sums_to_the_deferred_total(self):
        """A breakdown that does not add up reads as a measurement and is not one.

        On the real corpus the width check ran before the surface checks, so 125 of 149
        deferrals landed in no bucket and `held_surface_unknown` read 4 against 138 unknown
        surfaces in the same frontier.
        """
        wave = self._wave(
            [item(f"RM-{n}", links={"files": [f"dir{n}/x"], "issues": []}) for n in range(1, 9)],
            width=2,
        )
        counts = wave["counts"]
        buckets = ("held_blocked", "held_collision", "held_surface_unknown",
                   "held_untriaged", "held_claimed", "held_wave_full")
        self.assertEqual(sum(counts[b] for b in buckets), counts["deferred"])
        self.assertEqual(counts["held_wave_full"], 6)

    def test_claimed_items_are_never_placed(self):
        wave = self._wave(
            [item("RM-1", links={"files": ["a"], "issues": []})],
            campaigns={"c.json": {"campaign": "c", "objective": "o", "waves": [
                {"wave": 1, "workers": [{"worker": "w", "branch": "b", "item": "harness:RM-1"}]}
            ]}},
        )
        self.assertEqual(wave["counts"]["placed"], 0)

    def test_width_is_respected(self):
        wave = self._wave(
            [item(f"RM-{n}", links={"files": [f"dir{n}/x"], "issues": []}) for n in range(1, 8)],
            width=3,
        )
        self.assertEqual(wave["counts"]["placed"], 3)

    def test_worker_rows_carry_no_state_key_campaign_would_refuse(self):
        """The wave is copied into a campaign manifest, which refuses any state key."""
        wave = self._wave([item("RM-1", links={"files": ["a"], "issues": []})])
        forbidden = {"status", "state", "progress", "completed", "complete",
                     "evidence", "landed", "done", "verdict", "title", "acceptance"}
        for row in wave["workers"]:
            self.assertFalse(forbidden & set(row), f"worker row carries {forbidden & set(row)}")
            for key in ("worker", "branch", "item"):
                self.assertTrue(row.get(key), f"worker row missing {key}")
            self.assertIn(":", row["item"], "item must be qualified <roadmap>:<id>")

    def test_scope_is_the_declared_surface_and_provenance_says_when_it_is_not(self):
        wave = self._wave([item("RM-1", links={"files": [".claude/x"], "issues": []})])
        self.assertEqual(wave["workers"][0]["scope"], [".claude/x"])
        self.assertEqual(wave["workers"][0]["surface_provenance"], "declared")
        wave = self._wave([item("RM-2")])
        self.assertEqual(wave["workers"][0]["surface_provenance"], "unknown")


class ExitCodeTest(unittest.TestCase):
    """The interface, so a caller greps nothing."""

    def setUp(self):
        self.fx = None

    def tearDown(self):
        if self.fx:
            self.fx.destroy()

    def test_frontier_exits_1_when_work_remains_and_0_when_empty(self):
        self.fx = Fixture([item("RM-1")])
        self.assertEqual(
            gauntlet.main(["frontier", "--root", self.fx.root, "--no-tracker", "--json"]),
            gauntlet.EXIT_WORK_REMAINS,
        )
        self.fx.destroy()
        self.fx = Fixture([item("RM-1", status="done")])
        self.assertEqual(
            gauntlet.main(["frontier", "--root", self.fx.root, "--no-tracker", "--json"]),
            gauntlet.EXIT_OK,
        )

    def test_frontier_exits_2_when_a_channel_could_not_be_read(self):
        self.assertEqual(
            gauntlet.main(["frontier", "--root", "/nonexistent-gauntlet-root", "--no-tracker"]),
            gauntlet.EXIT_UNDETERMINED,
        )

    def test_rearm_exits_3_when_there_is_nothing_to_assign(self):
        """Distinct from 0 on purpose: a caller that cannot tell them apart cannot drive a loop."""
        self.fx = Fixture([item("RM-1", status="done")])
        self.assertEqual(
            gauntlet.main(["rearm", "--root", self.fx.root, "--no-tracker", "--json"]),
            gauntlet.EXIT_NOTHING_TO_ASSIGN,
        )

    def test_rearm_exits_0_when_a_wave_was_emitted(self):
        self.fx = Fixture([item("RM-1", links={"files": ["a"], "issues": []})])
        self.assertEqual(
            gauntlet.main(["rearm", "--root", self.fx.root, "--no-tracker", "--json"]),
            gauntlet.EXIT_OK,
        )

    def test_verify_maps_campaign_close_exits_to_its_own_set(self):
        """`verify` had ZERO coverage, and collapsed three "could not look" answers into 1.

        `campaign`'s set is 0/1/2/64, and `_run` manufactures 124 (timeout) and 127 (no such
        program) of its own. Everything outside {0,1,2} used to return 1 — which this module
        defines as "items unlanded, or new work has appeared", told to a caller that greps
        nothing.
        """
        self.fx = Fixture([item("RM-1")])
        original = gauntlet._run
        expected = {
            0: gauntlet.EXIT_WORK_REMAINS,   # closeable, but the frontier is not empty
            1: gauntlet.EXIT_WORK_REMAINS,   # blocked — genuinely unlanded
            2: gauntlet.EXIT_UNDETERMINED,
            64: gauntlet.EXIT_UNDETERMINED,  # usage: the question was never asked
            124: gauntlet.EXIT_UNDETERMINED,  # timeout
            127: gauntlet.EXIT_UNDETERMINED,  # no python3
        }
        try:
            for rc, want in expected.items():
                gauntlet._run = lambda *a, _rc=rc, **k: (_rc, "", "")
                got = gauntlet.main(["verify", "--root", self.fx.root, "--no-tracker",
                                     "--manifest", os.path.join(self.fx.root, "m.json"), "--json"])
                self.assertEqual(got, want, f"campaign close rc {rc} mapped to {got}")
        finally:
            gauntlet._run = original

    def test_verify_exits_0_only_when_the_batch_closes_and_the_frontier_is_empty(self):
        """The thesis, as an assertion: a closeable batch is not a finished gauntlet."""
        self.fx = Fixture([item("RM-1", status="done")])
        original = gauntlet._run
        gauntlet._run = lambda *a, **k: (0, "", "")
        try:
            self.assertEqual(
                gauntlet.main(["verify", "--root", self.fx.root, "--no-tracker",
                               "--manifest", os.path.join(self.fx.root, "m.json"), "--json"]),
                gauntlet.EXIT_OK,
            )
        finally:
            gauntlet._run = original

    def test_verify_without_a_manifest_does_not_claim_a_close_verdict(self):
        self.fx = Fixture([item("RM-1")])
        payload = gauntlet.verify_batch(self.fx.root, None, want_tracker=False)
        self.assertEqual(payload["campaign_close"]["verdict"], "not-asked")
        self.assertIsNone(payload["campaign_close"]["exit"])

    def test_metric_prints_one_number(self):
        self.fx = Fixture([item("RM-1", links={"files": ["a"], "issues": []}), item("RM-2")])
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            gauntlet.main(["frontier", "--root", self.fx.root, "--no-tracker",
                           "--metric", "surface-coverage"])
        self.assertEqual(buf.getvalue().strip(), "50.0")


if __name__ == "__main__":
    unittest.main()
