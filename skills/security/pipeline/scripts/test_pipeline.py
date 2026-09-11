#!/usr/bin/env python3
"""Offline tests for pipeline.py: the reader, the four checks, and the report contract.

Run: python3 skills/security/pipeline/scripts/test_pipeline.py
Every test writes its workflow files into a temporary directory; no network, no forge.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline  # noqa: E402

SCRIPT = os.path.abspath(pipeline.__file__)
NOW = "2026-09-09T12:00:00"


def workflows(d, **files):
    folder = Path(d) / ".github" / "workflows"
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (folder / f"{name}.yml").write_text(text, encoding="utf-8")
    return d


def run(root, *extra):
    args = [sys.executable, SCRIPT, "--json", "--now", NOW, "--root", str(root), *extra]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def item(out, cid, level=None):
    for i in out["items"]:
        if i["id"] == cid and (level is None or i["level"] == level):
            return i
    raise AssertionError(f"no {cid} ({level}) in {[i['id'] for i in out['items']]}")


def cost(out, cid):
    return item(out, cid)["measure"]["value"]


class ReaderTest(unittest.TestCase):
    def test_a_mapping_a_sequence_and_a_nested_block_are_read(self):
        got = pipeline.parse_yaml("name: a\njobs:\n  build:\n    steps:\n      - uses: x/y@v1\n"
                                  "      - run: echo hi\n")
        self.assertEqual(got["name"], "a")
        self.assertEqual(got["jobs"]["build"]["steps"][0]["uses"], "x/y@v1")
        self.assertEqual(got["jobs"]["build"]["steps"][1]["run"], "echo hi")

    def test_a_step_carries_the_keys_that_follow_its_dash(self):
        got = pipeline.parse_yaml("jobs:\n  b:\n    steps:\n      - name: checkout\n"
                                  "        uses: actions/checkout@v4\n        with:\n"
                                  "          ref: main\n")
        step = got["jobs"]["b"]["steps"][0]
        self.assertEqual(step["uses"], "actions/checkout@v4")
        self.assertEqual(step["with"]["ref"], "main")

    def test_a_block_scalar_keeps_every_line_of_the_script(self):
        got = pipeline.parse_yaml("jobs:\n  b:\n    steps:\n      - run: |\n          one\n"
                                  "          two: three\n")
        self.assertEqual(got["jobs"]["b"]["steps"][0]["run"], "one\ntwo: three")

    def test_a_script_keeps_what_stands_behind_a_hash(self):
        """The runner substitutes an expression before a shell sees the line, comment or not."""
        got = pipeline.parse_yaml("jobs:\n  b:\n    steps:\n      - run: |\n"
                                  "          echo hi  # ${{ github.event.issue.title }}\n")
        self.assertIn("github.event.issue.title", got["jobs"]["b"]["steps"][0]["run"])

    def test_a_flow_sequence_is_a_list(self):
        self.assertEqual(pipeline.parse_yaml("on: [push, pull_request]\n")["on"],
                         ["push", "pull_request"])

    def test_the_trigger_key_stays_the_word_it_is_written_as(self):
        """The format reads a bare `on` as a boolean elsewhere; here the key is what it says."""
        self.assertEqual(pipeline.triggers({"on": "push"}), ["push"])
        self.assertEqual(pipeline.triggers({"on": {"pull_request_target": None}}),
                         ["pull_request_target"])

    def test_a_comment_goes_and_a_hash_inside_quotes_stays(self):
        got = pipeline.parse_yaml('name: a  # the name\nrun: "echo #1"\n')
        self.assertEqual(got["name"], "a")
        self.assertEqual(got["run"], "echo #1")

    def test_an_anchor_and_a_tab_are_refused_rather_than_half_read(self):
        for text in ("base: &b\n  a: 1\n", "jobs:\n\tbuild: x\n", "a: 1\n---\nb: 2\n"):
            with self.assertRaises(pipeline.Unsupported):
                pipeline.parse_yaml(text)


class CheckoutTest(unittest.TestCase):
    def test_a_privileged_trigger_that_checks_out_the_fork_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on:\n  pull_request_target:\njobs:\n  b:\n    steps:\n"
                           "      - uses: actions/checkout@v4\n        with:\n"
                           "          ref: ${{ github.event.pull_request.head.sha }}\n")
            self.assertEqual(cost(run(d), "build.untrusted-checkout"), 1)

    def test_the_same_checkout_under_an_unprivileged_trigger_is_no_finding(self):
        """Under `pull_request` the job holds no secrets, so running the fork's code is the point."""
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [pull_request]\njobs:\n  b:\n    steps:\n"
                           "      - uses: actions/checkout@v4\n        with:\n"
                           "          ref: ${{ github.event.pull_request.head.sha }}\n")
            self.assertEqual(item(run(d), "build.untrusted-checkout")["level"], "PASS")

    def test_a_privileged_trigger_without_a_fork_checkout_is_no_finding(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on:\n  pull_request_target:\njobs:\n  b:\n    steps:\n"
                           "      - uses: actions/checkout@v4\n")
            self.assertEqual(cost(run(d), "build.untrusted-checkout"), 0)

    def test_one_workflow_counts_once_however_many_steps_check_out(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on:\n  pull_request_target:\njobs:\n  b:\n    steps:\n"
                           "      - uses: actions/checkout@v4\n        with:\n"
                           "          ref: ${{ github.head_ref }}\n"
                           "      - uses: actions/checkout@v4\n        with:\n"
                           "          ref: ${{ github.head_ref }}\n")
            self.assertEqual(cost(run(d), "build.untrusted-checkout"), 1)


class InjectionTest(unittest.TestCase):
    def test_a_title_from_outside_in_a_shell_step_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [issues]\njobs:\n  b:\n    steps:\n"
                           "      - run: echo ${{ github.event.issue.title }}\n")
            self.assertEqual(cost(run(d), "build.script-injection"), 1)

    def test_the_same_value_through_an_environment_variable_is_no_finding(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [issues]\njobs:\n  b:\n    steps:\n"
                           "      - env:\n          TITLE: ${{ github.event.issue.title }}\n"
                           "        run: echo \"$TITLE\"\n")
            self.assertEqual(cost(run(d), "build.script-injection"), 0)

    def test_a_value_that_needs_write_access_to_set_is_trusted(self):
        """Starting a manual run already needs write access, so its input is not from outside."""
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [workflow_dispatch]\njobs:\n  b:\n    steps:\n"
                           "      - run: echo ${{ github.event.inputs.name }}\n")
            self.assertEqual(cost(run(d), "build.script-injection"), 0)


class TokenTest(unittest.TestCase):
    def test_a_workflow_with_no_rights_anywhere_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    steps:\n      - run: echo hi\n")
            self.assertEqual(cost(run(d), "build.token-broad"), 1)

    def test_rights_at_the_top_settle_the_whole_file(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\npermissions:\n  contents: read\njobs:\n  b:\n"
                           "    steps:\n      - run: echo hi\n")
            self.assertEqual(cost(run(d), "build.token-broad"), 0)

    def test_rights_on_every_job_settle_the_file_and_one_job_short_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    permissions:\n      contents: read\n"
                           "    steps:\n      - run: echo hi\n")
            self.assertEqual(cost(run(d), "build.token-broad"), 0)
            workflows(d, a="on: [push]\njobs:\n  b:\n    permissions:\n      contents: read\n"
                           "    steps:\n      - run: echo hi\n  c:\n    steps:\n      - run: echo hi\n")
            self.assertEqual(cost(run(d), "build.token-broad"), 1)


class PinTest(unittest.TestCase):
    def test_a_tag_counts_and_a_commit_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    steps:\n      - uses: owner/act@v4\n")
            self.assertEqual(cost(run(d), "build.action-unpinned"), 1)
            workflows(d, a="on: [push]\njobs:\n  b:\n    steps:\n      - uses: owner/act@"
                           + "a" * 40 + "\n")
            self.assertEqual(cost(run(d), "build.action-unpinned"), 0)

    def test_an_action_of_this_repository_and_a_trusted_owner_need_no_pin(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    steps:\n      - uses: ./.github/actions/x\n"
                           "      - uses: mine/act@v1\n")
            self.assertEqual(cost(run(d, "--trusted-owner", "mine"), "build.action-unpinned"), 0)

    def test_a_job_that_calls_another_workflow_is_an_action_reference_too(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    uses: owner/repo/.github/workflows/w.yml@main\n")
            self.assertEqual(cost(run(d), "build.action-unpinned"), 1)

    def test_a_reference_without_any_version_moves_with_every_push(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    steps:\n      - uses: owner/act\n")
            self.assertEqual(cost(run(d), "build.action-unpinned"), 1)


class AcceptTest(unittest.TestCase):
    def test_an_accepted_finding_leaves_the_count_and_is_named_as_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    steps:\n      - run: echo hi\n")
            out = run(d, "--accept", "build.token-broad .github/workflows/a.yml agreed 2026-01-01")
            self.assertEqual(cost(out, "build.token-broad"), 0)
            self.assertIn("1 finding is recorded as accepted", json.dumps(out))

    def test_an_entry_another_pass_owns_is_not_counted_here(self):
        """One accepted list reaches every pass, and a check id belongs to exactly one of them, so
        a credential somebody accepted must not stand as a note under a build check."""
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\npermissions: {}\njobs:\n  b:\n    steps:\n      - run: echo hi\n")
            out = run(d, "--accept", "cred.tracked settings.py a test value 2026-01-01")
            self.assertNotIn("recorded as accepted", json.dumps(out))

    def test_the_header_counts_only_the_entries_this_pass_owns(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\npermissions: {}\njobs:\n  b:\n    steps:\n      - run: echo hi\n")
            args = [sys.executable, SCRIPT, "--now", NOW, "--root", str(d),
                    "--accept", "cred.tracked settings.py a test value 2026-01-01"]
            r = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("0 accepted findings", r.stdout)


class UnreadTest(unittest.TestCase):
    def test_a_file_that_does_not_parse_is_a_note_and_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\nbase: &anchor\n  x: 1\n")
            out = run(d)
            note = item(out, "build.token-broad", level="INFO")
            self.assertIsNone(note["measure"])
            self.assertIn("could not be read", note["message"])

    def test_a_repository_without_workflows_measures_nothing_rather_than_passing(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d)
            self.assertIn("measures nothing", item(out, "build.token-broad", level="INFO")["message"])
            self.assertEqual([i for i in out["items"] if i["level"] == "PASS"], [])


class ContractTest(unittest.TestCase):
    def test_measures_prints_one_id_and_unit_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--measures"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, pipeline.MEASURES)

    def test_the_text_report_says_what_it_measured_against_and_ends_on_a_next_step(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    steps:\n      - uses: owner/act@v1\n")
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured against", r.stdout)
            self.assertIn("\nnext  ", r.stdout)

    def test_the_counting_line_is_a_bar_and_the_cost_stands_in_its_own_column(self):
        with tempfile.TemporaryDirectory() as d:
            workflows(d, a="on: [push]\njobs:\n  b:\n    steps:\n      - uses: owner/act@v1\n")
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW],
                               capture_output=True, text=True)
            self.assertRegex(r.stdout, r"\n\d+ FAIL · \d+ WARN · \d+ notes? · \d+ passed\n")
            self.assertRegex(r.stdout, r"\nWARN  build\.token-broad {13}1 workflow\n")
            self.assertNotIn("(costs", r.stdout)

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW],
                               capture_output=True, text=True)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
