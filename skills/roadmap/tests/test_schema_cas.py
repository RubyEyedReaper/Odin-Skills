"""The same-directory lost update, and the truncating write that makes it worse.

ADR-0062 closed the *cross-worktree* loss: two branches each holding a full copy of
roadmap.json, resolved at rebase. It says in as many words that the loss it addresses "is not two
processes racing on one file". That sentence is true of the incident it was written about and false
as a general statement about the engine — this file is the reproduction.

    p1 = load(path)          # both read the same bytes
    p2 = load(path)
    p2.mutate(); save(p2)    # lands
    p1.mutate(); save(p1)    # whole-file rewrite from a stale copy — p2's write is gone

Both processes print success. The file is valid JSON either way. Nothing downstream can tell.

So the assertion is not "the write succeeded". It is that a write whose target moved under it is
**refused**, and that a write which does happen lands whole or not at all.

The cases assert the *behaviour*, deliberately not the mechanism. DEC-0028 picked compare-and-swap
over an advisory flock by 73.36 to 71.27 and flagged the recommendation fragile — the winner flips
on a 10 pp weight shift. A suite that asserted "a digest was compared" would have to be rewritten
the day that flip happens; one that asserts "the stale write was refused" survives it.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import roadmap  # noqa: E402
from scripts import render as render_mod  # noqa: E402
from scripts import schema  # noqa: E402


def doc(*statuses):
    """A schema-valid roadmap built by the engine's own constructors.

    Hand-rolled dicts drift from the schema the moment a field is added, and a fixture the
    engine rejects tests the validator rather than the write path.
    """
    document = schema.default_doc("operational", today="2026-08-20")
    document["slug"] = "harness"
    for number, status in enumerate(statuses, start=1):
        item = schema.new_item("RM-%04d" % number, "item %d" % number, "ops",
                               today="2026-08-20")
        item["status"] = status
        item["tier"] = "now"
        document["items"].append(item)
    return document


class TestStaleWriteIsRefused(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="roadmap-cas-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.dir = os.path.join(self.root, "docs", "roadmap")
        self.path = os.path.join(self.dir, "roadmap.json")
        schema.save(self.path, doc("proposed", "proposed"))

    def read(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def statuses(self):
        return [i["status"] for i in self.read()["items"]]

    def test_the_lost_update_is_refused(self):
        """Two loads of the same file; the second save must not silently clobber the first."""
        mine = schema.load(self.path)          # this process reads
        theirs = schema.load(self.path)        # a concurrent process reads the same bytes
        theirs["items"][1]["status"] = "in-progress"
        schema.save(self.path, theirs)         # theirs lands first

        mine["items"][0]["status"] = "in-progress"
        with self.assertRaises(schema.StaleWrite):
            schema.save(self.path, mine)

        self.assertEqual(self.statuses(), ["proposed", "in-progress"],
                         "the write that landed must survive the refusal")

    def test_the_refusal_names_the_file_and_the_remedy(self):
        """A refusal with no remedy is a refusal people route around."""
        mine = schema.load(self.path)
        other = schema.load(self.path)
        other["items"][0]["status"] = "ready"
        schema.save(self.path, other)

        mine["items"][1]["status"] = "ready"
        with self.assertRaises(schema.StaleWrite) as caught:
            schema.save(self.path, mine)

        message = str(caught.exception)
        self.assertIn(os.path.basename(self.path), message)
        self.assertIn("re-run", message)

    def test_a_write_to_a_path_this_process_never_loaded_is_allowed(self):
        """`init` creates a file it never read. That is not a stale write."""
        fresh = os.path.join(self.root, "other", "docs", "roadmap", "roadmap.json")
        schema.save(fresh, doc("proposed"))
        with open(fresh, encoding="utf-8") as fh:
            self.assertEqual(len(json.load(fh)["items"]), 1)

    def test_a_second_write_in_one_process_is_allowed(self):
        """`reconcile --apply` saves after a save. The guard must compare against our own write."""
        mine = schema.load(self.path)
        mine["items"][0]["status"] = "ready"
        schema.save(self.path, mine)
        mine["items"][1]["status"] = "ready"
        schema.save(self.path, mine)
        self.assertEqual(self.statuses(), ["ready", "ready"])

    def test_rendering_between_load_and_save_does_not_trip_the_guard(self):
        """`refresh()` runs between load and save on every read-then-write command.

        render_all writes ROADMAP.md, graph.dot and graph.svg — never roadmap.json. Asserted
        rather than assumed: if that ever stops being true, every mutating command starts
        refusing itself and the cause would be invisible.
        """
        mine = schema.load(self.path)
        render_mod.render_all(self.path)
        mine["items"][0]["status"] = "ready"
        schema.save(self.path, mine)
        self.assertEqual(self.statuses(), ["ready", "proposed"])

    def test_a_forgotten_path_is_writable_again(self):
        """The test seam that lets a case force the stale branch, and the escape for a caller
        that genuinely means to overwrite."""
        mine = schema.load(self.path)
        other = schema.load(self.path)
        other["items"][0]["status"] = "done"
        schema.save(self.path, other)

        schema.forget(self.path)
        mine["items"][1]["status"] = "done"
        schema.save(self.path, mine)
        self.assertEqual(self.statuses(), ["proposed", "done"])


class TestWriteIsAtomic(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="roadmap-atomic-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.dir = os.path.join(self.root, "docs", "roadmap")
        self.path = os.path.join(self.dir, "roadmap.json")
        schema.save(self.path, doc("proposed"))

    def test_a_failed_serialisation_leaves_the_previous_document_intact(self):
        """`open(path, "w")` truncates before it writes anything.

        A write that dies partway therefore leaves a roadmap that `validate` reports as broken
        with no cause visible. The failure is forced here with a value json cannot serialise,
        because that is the one interruption a test can produce deterministically.
        """
        broken = schema.load(self.path)
        broken["items"][0]["deps"] = {"not", "serialisable"}
        with self.assertRaises(TypeError):
            schema.save(self.path, broken)

        with open(self.path, encoding="utf-8") as fh:
            survived = json.load(fh)
        self.assertEqual(survived["items"][0]["status"], "proposed")

    def test_no_temp_file_is_left_behind_after_a_successful_write(self):
        mine = schema.load(self.path)
        mine["items"][0]["status"] = "ready"
        schema.save(self.path, mine)
        self.assertEqual(sorted(os.listdir(self.dir)), ["roadmap.json"])


if __name__ == "__main__":
    unittest.main()


class TestTheEngineReportsARefusal(unittest.TestCase):
    """The `schema` layer raises; the CLI has to turn that into something a caller can read.

    A traceback is not a refusal — a wrapper script sees a non-zero exit either way, and the
    agent reading the transcript sees a crash where it should see a one-line instruction.

    The concurrent write is injected at `_refuse_lost_claim`, which `cmd_set` calls between its
    load and its save. Only the *timing* is arranged; the write itself is a real external
    process writing real bytes, and the assertion is on the engine's real exit code and stderr.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="roadmap-cli-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.path = os.path.join(self.root, "docs", "roadmap", "roadmap.json")
        schema.save(self.path, doc("proposed", "proposed"))
        schema.forget(self.path)

    def run_set(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            try:
                code = roadmap.main(["--path", self.path, "set", *argv])
            except SystemExit as exc:
                code = exc.code
        return code, err.getvalue()

    def test_a_stale_set_exits_non_zero_with_a_readable_message(self):
        def concurrent_write(*a, **kw):
            with open(self.path, encoding="utf-8") as fh:
                landed = json.load(fh)
            landed["items"][1]["status"] = "done"
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(landed, indent=2, sort_keys=True) + "\n")

        original = roadmap._refuse_lost_claim
        roadmap._refuse_lost_claim = concurrent_write
        self.addCleanup(setattr, roadmap, "_refuse_lost_claim", original)

        code, err = self.run_set("RM-0001", "--status", "in-progress")

        self.assertNotEqual(code, 0, "a refused write must not report success")
        self.assertIn("[roadmap]", err)
        self.assertIn("re-run", err)
        self.assertNotIn("Traceback", err)

    def test_an_ordinary_set_still_exits_zero(self):
        code, err = self.run_set("RM-0001", "--status", "ready")
        self.assertEqual(code, 0, err)
