"""The facade's own matrix.

WHAT IS STUBBED, AND WHAT IS NOT. Every case here builds a fixture root under `mktemp -d` holding a
**stub work-loop engine** at `.claude/skills/work-loop/scripts/loop.py`, and the facade reaches it
through its real `subprocess` path. So the wiring under test is real: the module invocation, the
cwd the engine is run from, the `--root` pass-through, and the JSON parse. Only the engine's own
arithmetic is stubbed, and that arithmetic has its own suite next door.

The alternative — patching `loop_call` — would have asserted that a function returns what it was
told to return. Recorded as `a-test-against-its-own-function-asserts-wiring`: a constant-returning
mutant once left 23 of 24 cases green.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts import todo  # noqa: E402


STUB_ENGINE = '''\
import json, sys
# A stub. It answers `status --json` from a file the fixture wrote, and records `iterate` calls so a
# case can assert the facade passed what it claims to pass.
argv = sys.argv[1:]
here = __file__
state = here.replace("loop.py", "state.json")
doc = json.load(open(state))
if argv and argv[0] == "status":
    print(json.dumps(doc["status"]))
    sys.exit(0)
if argv and argv[0] == "iterate":
    doc.setdefault("iterate_calls", []).append(argv)
    json.dump(doc, open(state, "w"))
    print("iteration recorded")
    sys.exit(0)
sys.exit(9)
'''


def build_root(tmp, *, items, completed, ledger_status="open", session="S1"):
    """A fixture root with a stub engine, a ledger holding `items`, and a stub status payload."""
    root = os.path.join(tmp, "root")
    eng = os.path.join(root, ".claude", "skills", "work-loop", "scripts")
    runtime = os.path.join(root, ".claude", ".runtime", "work-loop")
    os.makedirs(eng, exist_ok=True)
    os.makedirs(runtime, exist_ok=True)

    with open(os.path.join(eng, "loop.py"), "w", encoding="utf-8") as fh:
        fh.write(STUB_ENGINE)
    open(os.path.join(eng, "__init__.py"), "w").close()

    with open(os.path.join(eng, "state.json"), "w", encoding="utf-8") as fh:
        json.dump({"status": {"session": session, "status": ledger_status,
                              "completed_actions": list(completed)}}, fh)

    with open(os.path.join(runtime, session + ".json"), "w", encoding="utf-8") as fh:
        json.dump({"session": session, "status": ledger_status,
                   "contract": {"expected_outputs": list(items)}}, fh)
    return root


def engine_state(root):
    path = os.path.join(root, ".claude", "skills", "work-loop", "scripts", "state.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class ItemIdTests(unittest.TestCase):
    def test_the_text_before_the_first_colon_is_the_id(self):
        self.assertEqual(todo.item_id("gate: write the checker"), "gate")

    def test_a_head_containing_a_space_is_not_an_id(self):
        # "write the gate: now" has no id-shaped head; the whole line is the id rather than a
        # three-word fragment that reads like prose and collides with the next such item.
        self.assertEqual(todo.item_id("write the gate: now"), "write the gate: now")

    def test_an_item_with_no_colon_is_its_own_id(self):
        self.assertEqual(todo.item_id("write the gate"), "write the gate")

    def test_surrounding_whitespace_is_not_part_of_the_id(self):
        self.assertEqual(todo.item_id("  gate : write it"), "gate")


class ContractTests(unittest.TestCase):
    def synth(self, *items, session="S1"):
        argv = ["contract", "--session", session]
        for i in items:
            argv += ["--item", i]
        proc = subprocess.run([sys.executable, todo.__file__] + argv,
                              capture_output=True, text=True)
        return proc

    def test_a_synthesised_contract_declares_all_twelve_fields(self):
        proc = self.synth("a: one", "b: two")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(proc.stdout)
        for field in ("purpose", "owner", "starting_state", "inputs", "expected_outputs",
                      "success_criteria", "failure_criteria", "dependencies", "iteration_limit",
                      "timeout_behaviour", "escalation_path", "quality_rubric"):
            self.assertIn(field, doc)

    def test_the_items_are_the_expected_outputs_verbatim(self):
        doc = json.loads(self.synth("a: one", "b: two").stdout)
        self.assertEqual(doc["expected_outputs"], ["a: one", "b: two"])

    def test_the_rubric_dimension_declares_all_eight_keys(self):
        # `loop.py` refuses a dimension missing one, and `hard_gate` is NOT the optional key —
        # `must_not_regress` is. Measured: omitting it made `loop open` refuse the contract.
        doc = json.loads(self.synth("a: one").stdout)
        dim = doc["quality_rubric"][0]
        for key in ("dimension", "evidence_command", "baseline", "target", "weight",
                    "failure_threshold", "direction", "hard_gate"):
            self.assertIn(key, dim)

    def test_the_baseline_is_the_item_count_and_the_target_is_zero(self):
        doc = json.loads(self.synth("a: one", "b: two", "c: three").stdout)
        dim = doc["quality_rubric"][0]
        self.assertEqual(dim["baseline"], 3)
        self.assertEqual(dim["target"], 0)
        self.assertEqual(dim["direction"], "lower-is-better")

    def test_the_evidence_command_carries_no_shell_metacharacter(self):
        # `loop.py` splits a command into segments BEFORE shlex.split sees it, so a `|` inside a
        # quoted span breaks the quoting and the contract is refused with `No closing quotation` —
        # a message naming the quote and not the pipe. Measured in this campaign.
        cmd = json.loads(self.synth("a: one").stdout)["quality_rubric"][0]["evidence_command"]
        for ch in "|&;<>$`":
            self.assertNotIn(ch, cmd, "evidence_command carries %r" % ch)

    def test_the_evidence_command_names_the_session_it_will_be_run_for(self):
        cmd = json.loads(self.synth("a: one", session="S-xyz").stdout)["quality_rubric"][0]["evidence_command"]
        self.assertIn("S-xyz", cmd)

    def test_an_empty_item_list_is_refused(self):
        proc = self.synth()
        self.assertEqual(proc.returncode, todo.EXIT_USAGE)
        self.assertIn("declares nothing to track", proc.stderr)

    def test_duplicate_item_ids_are_refused_by_name(self):
        proc = self.synth("a: one", "a: two")
        self.assertEqual(proc.returncode, todo.EXIT_USAGE)
        self.assertIn("duplicate item id(s): a", proc.stderr)


class DerivedStandingTests(unittest.TestCase):
    """The list and its open count, derived through the real subprocess path."""

    def run_facade(self, root, argv):
        proc = subprocess.run([sys.executable, todo.__file__] + argv,
                              capture_output=True, text=True)
        return proc

    def test_count_open_is_declared_minus_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one", "b: two", "c: three"], completed=["a"])
            proc = self.run_facade(root, ["count-open", "--root", root, "--session", "S1"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "2")

    def test_count_open_is_zero_when_every_item_is_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one", "b: two"], completed=["a", "b"])
            proc = self.run_facade(root, ["count-open", "--root", root, "--session", "S1"])
            self.assertEqual(proc.stdout.strip(), "0")

    def test_a_completed_action_nobody_declared_does_not_reduce_the_count(self):
        # The engine records actions the facade did not write — a `loop iterate --action` issued by
        # hand, for instance. Those are not items, and counting them would let the list read empty
        # while every declared item is still open.
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one", "b: two"], completed=["zzz", "qqq"])
            proc = self.run_facade(root, ["count-open", "--root", root, "--session", "S1"])
            self.assertEqual(proc.stdout.strip(), "2")

    def test_list_marks_each_item_open_or_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one", "b: two"], completed=["b"])
            proc = self.run_facade(root, ["list", "--root", root, "--session", "S1", "--json"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["open"], 1)
            by_id = {r["id"]: r["done"] for r in doc["items"]}
            self.assertEqual(by_id, {"a": False, "b": True})

    def test_no_ledger_is_exit_three_not_an_empty_list(self):
        # "I looked and found nothing open" and "there is no list" are different answers, and a
        # caller that cannot tell them apart reports a finished loop for a session that never
        # started one.
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one"], completed=[])
            proc = self.run_facade(root, ["count-open", "--root", root, "--session", "OTHER"])
            self.assertEqual(proc.returncode, todo.EXIT_NO_LEDGER)
            self.assertIn("not the same as nothing open", proc.stderr)

    def test_a_root_that_does_not_exist_is_a_usage_error(self):
        proc = self.run_facade("/nonexistent", ["list", "--root", "/nonexistent/x",
                                                "--session", "S1"])
        self.assertEqual(proc.returncode, todo.EXIT_USAGE)
        self.assertIn("no such directory", proc.stderr)


class DoneTests(unittest.TestCase):
    def run_facade(self, root, argv):
        return subprocess.run([sys.executable, todo.__file__] + argv,
                              capture_output=True, text=True)

    def test_done_passes_the_item_id_as_the_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one", "b: two"], completed=[])
            proc = self.run_facade(root, ["done", "--root", root, "--session", "S1",
                                          "--item", "a"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            call = engine_state(root)["iterate_calls"][0]
            self.assertIn("--action", call)
            self.assertEqual(call[call.index("--action") + 1], "a")
            self.assertEqual(call[call.index("--outcome") + 1], "continue")

    def test_done_passes_the_remaining_count_as_the_dimension_measure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one", "b: two", "c: three"], completed=[])
            self.run_facade(root, ["done", "--root", root, "--session", "S1", "--item", "a"])
            call = engine_state(root)["iterate_calls"][0]
            self.assertEqual(call[call.index("--measure") + 1], "items-open=2")

    def test_an_undeclared_item_is_refused_and_the_engine_is_never_called(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one"], completed=[])
            proc = self.run_facade(root, ["done", "--root", root, "--session", "S1",
                                          "--item", "delta"])
            self.assertEqual(proc.returncode, todo.EXIT_FAIL)
            self.assertIn("is not a declared item", proc.stderr)
            self.assertIn("Declared: a", proc.stderr)
            self.assertNotIn("iterate_calls", engine_state(root))


class RouteTests(unittest.TestCase):
    def run_facade(self, root, argv):
        return subprocess.run([sys.executable, todo.__file__] + argv,
                              capture_output=True, text=True)

    def test_an_open_ledger_satisfies_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one"], completed=[])
            proc = self.run_facade(root, ["route", "--root", root, "--session", "S1", "--json"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertTrue(doc["work_loop_ledger_open"])
            self.assertTrue(doc["satisfied"])

    def test_a_closed_ledger_does_not_satisfy_the_gate(self):
        # The gate requires `status == "open"`, not merely a file at the path. A closed ledger is
        # evidence of work that ENDED, which is not evidence that this session is tracking any.
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one"], completed=["a"], ledger_status="closed")
            proc = self.run_facade(root, ["route", "--root", root, "--session", "S1", "--json"])
            self.assertEqual(proc.returncode, todo.EXIT_FAIL)
            self.assertFalse(json.loads(proc.stdout)["work_loop_ledger_open"])

    def test_a_ledger_naming_another_session_does_not_satisfy_the_gate(self):
        # Matched on the ledger's OWN session field, never on the filename — a copied or spoofed
        # foreign ledger at the expected path must not pass, which is the hook's own rule.
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one"], completed=[], session="S1")
            path = os.path.join(root, ".claude", ".runtime", "work-loop", "S1.json")
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            doc["session"] = "SOMEONE-ELSE"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            proc = self.run_facade(root, ["route", "--root", root, "--session", "S1", "--json"])
            self.assertEqual(proc.returncode, todo.EXIT_FAIL)
            self.assertFalse(json.loads(proc.stdout)["work_loop_ledger_open"])

    def test_the_native_marker_alone_satisfies_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one"], completed=[], session="S1")
            os.remove(os.path.join(root, ".claude", ".runtime", "work-loop", "S1.json"))
            tasks = os.path.join(root, ".claude", ".runtime", "tasks")
            os.makedirs(tasks, exist_ok=True)
            open(os.path.join(tasks, "S1"), "w").close()
            proc = self.run_facade(root, ["route", "--root", root, "--session", "S1", "--json"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            doc = json.loads(proc.stdout)
            self.assertTrue(doc["task_create_marker"])
            self.assertTrue(doc["satisfied"])

    def test_neither_route_reports_both_and_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one"], completed=[], session="S1")
            os.remove(os.path.join(root, ".claude", ".runtime", "work-loop", "S1.json"))
            proc = self.run_facade(root, ["route", "--root", root, "--session", "S1"])
            self.assertEqual(proc.returncode, todo.EXIT_FAIL)
            self.assertIn("task gate satisfied:    NO", proc.stdout)

    def test_route_does_not_arm_the_thing_it_probes(self):
        # A probe that established a route would make every later reading of the gate agree with
        # it — read-only is a property of the effect, not of the intention.
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(tmp, items=["a: one"], completed=[], session="S1")
            os.remove(os.path.join(root, ".claude", ".runtime", "work-loop", "S1.json"))
            before = sorted(os.listdir(os.path.join(root, ".claude", ".runtime")))
            self.run_facade(root, ["route", "--root", root, "--session", "S1"])
            after = sorted(os.listdir(os.path.join(root, ".claude", ".runtime")))
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
