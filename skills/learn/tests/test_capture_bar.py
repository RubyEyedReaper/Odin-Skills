"""The capture bar — five refusal classes, one exit code each.

The primary testable core: a caller can tell *why* a record was refused from the exit
code alone. The break these cases exist to catch is five refusals sharing one non-zero
code, which is a bar that reports "no" and nothing else — a caller cannot strip a secret,
merge a duplicate and rewrite session chatter with the same remedy.

The second core is narrower and worse to get wrong: **a refusal must never echo the
matched credential.** That is asserted by running the engine and reading both streams,
never by grepping the engine for its own redaction logic — a check that reads the source
asserts the author's intention, not the program's behaviour.
"""
from __future__ import annotations

import os
import unittest

from . import _fixtures as fx
from scripts.capture_bar import (
    EXIT_ACCEPT,
    EXIT_CHATTER,
    EXIT_CREDENTIAL,
    EXIT_DERIVABLE,
    EXIT_DUPLICATE,
    EXIT_MALFORMED,
    EXIT_PERSONAL,
    EXIT_USAGE,
)


class DistinctExitCodes(unittest.TestCase):
    """Each refusal class exits with its own code, and the codes are all different."""

    def test_the_five_refusal_codes_are_distinct(self):
        codes = [
            EXIT_CREDENTIAL,
            EXIT_PERSONAL,
            EXIT_CHATTER,
            EXIT_DUPLICATE,
            EXIT_DERIVABLE,
        ]
        self.assertEqual(len(set(codes)), 5)
        self.assertNotIn(EXIT_ACCEPT, codes)
        self.assertNotIn(EXIT_USAGE, codes)
        self.assertNotIn(EXIT_MALFORMED, codes)


class Accept(unittest.TestCase):
    """The accept case. Without one, five refusals prove only that nothing passes."""

    def test_a_durable_finding_is_accepted(self):
        with fx.Root() as root:
            root.tracked("README.md", "# demo\n\nA repository used by the fixture.\n")
            code, out, _ = fx.check(root, **fx.a_finding())
            self.assertEqual(code, EXIT_ACCEPT, out)
            self.assertIn('"outcome": "record"', out)

    def test_the_accept_report_names_which_classes_it_evaluated(self):
        """A report that cannot say what it examined is indistinguishable from one that
        examined nothing — the failure this repository ships most often."""
        with fx.Root() as root:
            root.tracked("README.md", "# demo\n")
            _, out, _ = fx.check(root, **fx.a_finding())
            for name in ("credential", "personal", "chatter", "duplicate", "derivable"):
                self.assertIn(name, out)


class Credential(unittest.TestCase):
    """Refusal class 1 — and the value never reaches an output stream."""

    def test_a_credential_key_name_refuses(self):
        """The KEY branch on its own. The value here is innocuous, so nothing but the key
        name can produce this refusal — without that, disabling the key check entirely
        leaves the suite green, because the value branch catches the same fixture."""
        with fx.Root() as root:
            code, _, err = fx.check(
                root, **fx.a_finding(api_key="rotated on 2026-08-01, stored in the vault")
            )
            self.assertEqual(code, EXIT_CREDENTIAL)
            self.assertIn("api_key", err)

    def test_a_credential_shaped_value_refuses_even_under_an_innocent_key(self):
        with fx.Root() as root:
            code, out, err = fx.check(
                root, **fx.a_finding(body="the runner was configured with " + fx.FAKE_AWS_KEY)
            )
            self.assertEqual(code, EXIT_CREDENTIAL)
            self.assertIn("aws-access-key-id", err)
            self.assertNotIn(fx.FAKE_AWS_KEY, out + err)

    def test_the_refusal_never_prints_the_secret(self):
        """The whole point. Feed a synthetic secret; assert it is absent from BOTH streams.

        Run twice per secret: once under a credential-named key, and once under an
        innocent key so the VALUE branch is the one that produced the message. The two
        branches build their message separately, and a suite that only ever exercises the
        first cannot see the second start echoing what it matched.
        """
        for secret in (fx.FAKE_AWS_KEY, fx.FAKE_GH_TOKEN, fx.FAKE_API_KEY):
            for field in ("token", "body"):
                with self.subTest(secret=secret[:4] + "…", field=field):
                    with fx.Root() as root:
                        code, out, err = fx.check(
                            root, **fx.a_finding(**{field: "a value was pasted: " + secret})
                        )
                        self.assertEqual(code, EXIT_CREDENTIAL)
                        self.assertNotIn(secret, out)
                        self.assertNotIn(secret, err)

    def test_not_even_a_fragment_of_the_secret_is_printed(self):
        """A masked secret is still a secret in every log the caller writes."""
        for field in ("password", "body"):
            with self.subTest(field=field):
                with fx.Root() as root:
                    _, out, err = fx.check(
                        root, **fx.a_finding(**{field: "value: " + fx.FAKE_GH_TOKEN})
                    )
                    stream = out + err
                    for start in range(0, len(fx.FAKE_GH_TOKEN) - 8):
                        self.assertNotIn(fx.FAKE_GH_TOKEN[start:start + 8], stream)

    def test_a_record_about_credentials_is_not_itself_a_credential(self):
        """The negative control for this class: the word is not the thing."""
        with fx.Root() as root:
            root.tracked("README.md", "# demo\n")
            code, _, err = fx.check(
                root,
                **fx.a_finding(
                    title="Credential material never enters either memory tier",
                    body=(
                        "a secret surfaced during a task never enters operational recall; "
                        "the password, token and api key classes are excluded from both tiers."
                    ),
                ),
            )
            self.assertEqual(code, EXIT_ACCEPT, err)


class PersonalData(unittest.TestCase):
    """Refusal class 2. Reported by class name, for the same reason as class 1."""

    def test_an_email_address_refuses(self):
        with fx.Root() as root:
            code, out, err = fx.check(
                root, **fx.a_finding(body="reported by someone at person@example.invalid")
            )
            self.assertEqual(code, EXIT_PERSONAL)
            self.assertIn("email-address", err)
            self.assertNotIn("person@example.invalid", out + err)

    def test_a_national_id_shape_refuses(self):
        with fx.Root() as root:
            code, _, err = fx.check(root, **fx.a_finding(body="the id was 123-45-6789"))
            self.assertEqual(code, EXIT_PERSONAL)
            self.assertIn("national-id", err)

    def test_a_version_string_is_not_a_national_id(self):
        with fx.Root() as root:
            root.tracked("README.md", "# demo\n")
            code, _, err = fx.check(
                root, **fx.a_finding(body="gitleaks is pinned at 8.24.3 by version and checksum")
            )
            self.assertEqual(code, EXIT_ACCEPT, err)


class TaskChatter(unittest.TestCase):
    """Refusal class 3 — true only inside the conversation that produced it."""

    def test_session_deixis_refuses(self):
        with fx.Root() as root:
            code, _, err = fx.check(
                root,
                **fx.a_finding(
                    title="Next step",
                    body="as discussed above, the branch is rebased and the suite is green.",
                ),
            )
            self.assertEqual(code, EXIT_CHATTER)
            self.assertIn("chatter", err)

    def test_the_refusal_names_the_marker_it_found(self):
        with fx.Root() as root:
            _, _, err = fx.check(
                root, **fx.a_finding(body="this session left the worktree dirty.")
            )
            self.assertIn("this session", err)

    def test_a_durable_fact_that_mentions_a_session_is_not_chatter(self):
        """`session` is harness vocabulary. The marker is deixis, not the noun."""
        with fx.Root() as root:
            root.tracked("README.md", "# demo\n")
            code, _, err = fx.check(
                root,
                **fx.a_finding(
                    title="An autonomous posture ticket is scoped to one session",
                    body=(
                        "a workspace-wide unattended flag blocks the human working in the "
                        "same tree, so the claim is bound to a single session process tree."
                    ),
                ),
            )
            self.assertEqual(code, EXIT_ACCEPT, err)


class Duplicate(unittest.TestCase):
    """Refusal class 4 — a record the corpus already holds."""

    def test_a_near_duplicate_of_an_existing_record_refuses(self):
        with fx.Root() as root:
            root.record(
                "shadow.md",
                "prisma migrate diff destroys whatever database URL is handed to its shadow "
                "flag, so the guard requires the target be named shadow rather than trusting "
                "the caller to have nominated a scratch database.",
            )
            code, _, err = fx.check(root, **fx.a_finding())
            self.assertEqual(code, EXIT_DUPLICATE)
            self.assertIn("shadow.md", err)

    def test_an_unrelated_corpus_does_not_refuse(self):
        with fx.Root() as root:
            root.tracked("README.md", "# demo\n")
            root.record("other.md", "The memory index is read whole into every session in scope.")
            code, _, err = fx.check(root, **fx.a_finding())
            self.assertEqual(code, EXIT_ACCEPT, err)

    def test_an_absent_corpus_is_announced_rather_than_silently_passed(self):
        """A check that quietly passes when its subject is missing is indistinguishable
        from one that agrees with every input."""
        with fx.Root() as root:
            root.tracked("README.md", "# demo\n")
            code, out, err = fx.check(root, corpus=False, **fx.a_finding())
            self.assertEqual(code, EXIT_ACCEPT)
            self.assertIn("duplicate", err)
            self.assertIn('"skipped"', out)


class Derivable(unittest.TestCase):
    """Refusal class 5 — a restatement of a line the repository already carries."""

    def test_a_restatement_of_a_tracked_line_refuses(self):
        with fx.Root() as root:
            root.tracked(
                "CLAUDE.md",
                "# Contract\n\n"
                "Work happens on a short-lived topic branch cut from main, named by change class.\n",
            )
            code, _, err = fx.check(
                root,
                **fx.a_finding(
                    title="Topic branches",
                    body="Work happens on a short-lived topic branch cut from main, "
                    "named by change class.",
                ),
            )
            self.assertEqual(code, EXIT_DERIVABLE)
            self.assertIn("CLAUDE.md", err)

    def test_a_genuine_finding_about_the_repository_is_accepted(self):
        """The negative control. A check that fires on everything is a false positive,
        and a finding *about* the harness necessarily carries the harness's vocabulary."""
        with fx.Root() as root:
            root.tracked(
                "CLAUDE.md",
                "# Contract\n\n"
                "Work happens on a short-lived topic branch cut from main, named by change class.\n"
                "Rebase onto main, land by fast-forward, delete the branch.\n",
            )
            code, _, err = fx.check(
                root,
                **fx.a_finding(
                    title="Branch landedness is a question about content",
                    body=(
                        "after a rebase merge the topic branch shares no commit with main, so "
                        "ancestry answers no and git cherry answers yes; fifty-six of a hundred "
                        "and ten branches were already landed and still listed."
                    ),
                ),
            )
            self.assertEqual(code, EXIT_ACCEPT, err)

    def test_an_absent_root_is_announced(self):
        with fx.Root() as root:
            code, out, err = fx.run_cli(
                "check", "--candidate", root.candidate(**fx.a_finding()),
                "--corpus", root.corpus,
            )
            self.assertEqual(code, EXIT_ACCEPT)
            self.assertIn("derivable", err)
            self.assertIn('"skipped"', out)


class RefusalOrder(unittest.TestCase):
    """Highest harm first. A record that is both a secret and a duplicate is a secret."""

    def test_credential_outranks_every_other_class(self):
        with fx.Root() as root:
            root.record("dup.md", "the runner was configured with a key")
            code, out, err = fx.check(
                root,
                **fx.a_finding(
                    api_key=fx.FAKE_API_KEY,
                    body="as discussed above, the runner was configured with a key. "
                    "reported by person@example.invalid",
                ),
            )
            self.assertEqual(code, EXIT_CREDENTIAL)
            self.assertNotIn(fx.FAKE_API_KEY, out + err)


class Malformed(unittest.TestCase):
    """Usage and malformed input are separated from every refusal."""

    def test_a_candidate_without_a_body_is_malformed(self):
        with fx.Root() as root:
            code, _, err = fx.check(root, title="a title and nothing else")
            self.assertEqual(code, EXIT_MALFORMED)
            self.assertIn("body", err)

    def test_a_candidate_that_is_not_json_is_malformed(self):
        with fx.Root() as root:
            path = root.scratch("broken.json", "{not json")
            code, _, _ = fx.run_cli("check", "--candidate", path, "--root", root.repo)
            self.assertEqual(code, EXIT_MALFORMED)

    def test_a_missing_candidate_file_is_a_usage_error(self):
        with fx.Root() as root:
            code, _, _ = fx.run_cli(
                "check", "--candidate", os.path.join(root.path, "absent.json"),
                "--root", root.repo,
            )
            self.assertEqual(code, EXIT_USAGE)

    def test_no_subcommand_is_a_usage_error(self):
        code, _, _ = fx.run_cli()
        self.assertEqual(code, EXIT_USAGE)


class NeverAsks(unittest.TestCase):
    """No outcome path waits for a human — asserted at the source level.

    Absence of a stop cannot be observed by running the program: the case that would
    prove it is the one that hangs. ADR-0103 settled the same question for the loop
    engine the same way. This is the one intent-level assertion in the suite, and it is
    here because behaviour cannot reach it.
    """

    def test_the_engine_contains_no_blocking_call(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "scripts", "capture_bar.py"), encoding="utf-8") as handle:
            source = handle.read()
        for forbidden in ("input(", "AskUserQuestion", "sys.stdin", "raw_input("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
