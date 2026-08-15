"""Tests for scripts/plancheck.py — the mechanical gate on a construction plan.

plancheck catches only what a script can catch: a step nobody could execute cold.
Judgment stays with the plan-depth rubric. Written before the implementation.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.plancheck import check_text, codes  # noqa: E402

GOOD = """# Widget Implementation Plan

**Goal:** Ship the widget endpoint.

### Task 1: Widget model

**Files:**
- Create: `src/widget.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Write the failing test**

```python
def test_widget_defaults():
    assert Widget().size == 1
```

- [ ] **Step 2: Run it**

Run: `pytest tests/test_widget.py -q`
Expected: FAIL with "Widget not defined"

**Exit criteria:** `pytest tests/test_widget.py -q` passes.

### Task 2: Widget endpoint

**Files:**
- Modify: `src/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Add the route**

Run: `pytest tests/test_api.py -q`
Expected: PASS

**Exit criteria:** `GET /widget` returns 200 with the model from Task 1.

## Done criteria

1. Both test files pass.
"""


def _without(section):
    return GOOD.replace(section, "")


class TestCleanPlan(unittest.TestCase):
    def test_well_formed_plan_passes(self):
        findings = check_text(GOOD)
        self.assertEqual(findings, [], "clean plan should produce no findings")

    def test_two_tasks_are_found(self):
        self.assertEqual(codes(check_text(GOOD)), [])


class TestStructuralFindings(unittest.TestCase):
    def test_task_without_files_block_fails(self):
        text = GOOD.replace("**Files:**\n- Create: `src/widget.py`\n- Test: `tests/test_widget.py`\n", "")
        self.assertIn("no-files", codes(check_text(text)))

    def test_task_without_verification_command_fails(self):
        text = GOOD.replace("Run: `pytest tests/test_api.py -q`\nExpected: PASS\n", "")
        self.assertIn("no-verification", codes(check_text(text)))

    def test_task_without_exit_criteria_fails(self):
        text = GOOD.replace(
            "**Exit criteria:** `GET /widget` returns 200 with the model from Task 1.\n", ""
        )
        self.assertIn("no-exit-criteria", codes(check_text(text)))

    def test_plan_without_goal_fails(self):
        text = GOOD.replace("**Goal:** Ship the widget endpoint.\n", "")
        self.assertIn("no-goal", codes(check_text(text)))

    def test_em_dash_task_headings_are_recognised(self):
        """Real plans write 'Task 1 — thing'; requiring a colon reports a false no-tasks."""
        text = GOOD.replace("### Task 1:", "### Task 1 —").replace("### Task 2:", "### Task 2 —")
        self.assertNotIn("no-tasks", codes(check_text(text)))

    def test_plan_with_no_tasks_fails(self):
        self.assertIn("no-tasks", codes(check_text("# Empty Plan\n\n**Goal:** nothing.\n")))


class TestPlaceholders(unittest.TestCase):
    def test_tbd_is_a_finding(self):
        text = GOOD.replace("- Modify: `src/api.py`", "- Modify: TBD")
        self.assertIn("placeholder", codes(check_text(text)))

    def test_todo_is_a_finding(self):
        text = GOOD.replace("**Exit criteria:** `GET /widget`", "**Exit criteria:** TODO `GET /widget`")
        self.assertIn("placeholder", codes(check_text(text)))

    def test_similar_to_task_is_a_finding(self):
        text = GOOD.replace("- [ ] **Step 1: Add the route**", "- [ ] **Step 1: Similar to Task 1**")
        self.assertIn("placeholder", codes(check_text(text)))

    def test_vague_error_handling_is_a_finding(self):
        text = GOOD.replace("- [ ] **Step 1: Add the route**", "- [ ] **Step 1: Add appropriate error handling**")
        self.assertIn("placeholder", codes(check_text(text)))

    def test_a_checkbox_list_is_not_a_placeholder(self):
        self.assertNotIn("placeholder", codes(check_text(GOOD)))

    def test_finding_names_the_task_and_line(self):
        text = GOOD.replace("- Modify: `src/api.py`", "- Modify: TBD")
        finding = next(f for f in check_text(text) if f["code"] == "placeholder")
        self.assertEqual(finding["task"], "Task 2: Widget endpoint")
        self.assertGreater(finding["line"], 0)


class TestOrdering(unittest.TestCase):
    def test_backward_reference_is_fine(self):
        """Task 2 may rely on Task 1 — that is the normal direction."""
        self.assertNotIn("forward-dependency", codes(check_text(GOOD)))

    def test_forward_reference_is_a_finding(self):
        text = GOOD.replace(
            "**Exit criteria:** `pytest tests/test_widget.py -q` passes.",
            "**Exit criteria:** matches the schema from Task 2.",
        )
        self.assertIn("forward-dependency", codes(check_text(text)))

    def test_reference_to_a_nonexistent_task_is_a_finding(self):
        text = GOOD.replace(
            "**Exit criteria:** `pytest tests/test_widget.py -q` passes.",
            "**Exit criteria:** as defined in Task 9.",
        )
        self.assertIn("unknown-task", codes(check_text(text)))


class TestFileEntry(unittest.TestCase):
    def test_missing_file_is_an_error(self):
        from scripts.plancheck import main
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main([os.path.join(tmp, "nope.md")]), 2)

    def test_clean_plan_exits_zero(self):
        from scripts.plancheck import main
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "plan.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(GOOD)
            self.assertEqual(main([path]), 0)

    def test_dirty_plan_exits_one(self):
        from scripts.plancheck import main
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "plan.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(GOOD.replace("- Modify: `src/api.py`", "- Modify: TBD"))
            self.assertEqual(main([path]), 1)


if __name__ == "__main__":
    unittest.main()
