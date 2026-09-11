#!/usr/bin/env python3
"""Offline tests for secrets.py: what counts as a credential, the history, and the rotation ledger.

Run: python3 skills/security/secrets/scripts/test_secrets.py
Every test builds its own repository in a temporary directory; no network, no scanner required.
The values these tests use are assembled at run time, so no line of this file reads like a secret.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secrets as scan  # noqa: E402

SCRIPT = os.path.abspath(scan.__file__)
NOW = "2026-09-09T12:00:00"
# Assembled from parts so this file never carries a line that reads like a credential itself.
TOKEN = "Ab3x9Qz7" + "Kd2Lm5Pt" + "8Rv1Nw6Y"
OTHER = "Zc7k1Vb4" + "Nq8Wd3Xs" + "5Tf2Jh9M"
NAME = "api" + "_key"
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, env=ENV,
                   capture_output=True, text=True)


def repository(d, **files):
    """A git repository holding one commit per call, so the history has something to walk."""
    root = Path(d) / "repo"
    if not root.exists():
        root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, env=ENV,
                       capture_output=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "change")
    return root


def run(root, *extra):
    args = [sys.executable, SCRIPT, "--json", "--now", NOW, "--root", str(root), "--no-tool", *extra]
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


class ValueTest(unittest.TestCase):
    def test_a_random_value_scores_higher_than_a_word(self):
        self.assertGreater(scan.entropy(TOKEN), scan.entropy("changeme"))

    def test_a_fingerprint_is_short_stable_and_not_the_value(self):
        self.assertEqual(scan.fingerprint(TOKEN), scan.fingerprint(TOKEN))
        self.assertEqual(len(scan.fingerprint(TOKEN)), 10)
        self.assertNotIn(TOKEN, scan.fingerprint(TOKEN))

    def test_a_named_value_that_looks_random_is_a_candidate(self):
        self.assertIsNotNone(scan.named_value(f"{NAME} = {TOKEN}", 3.5))

    def test_a_name_alone_is_no_candidate(self):
        """The name proves nothing: the value carries the decision."""
        for line in (f"{NAME} = short", f"{NAME} = changeme_please_now",
                     f"{NAME} = /usr/bin/systemctl-service", f"{NAME} = abcdefghijklmnopqrst",
                     f"{NAME} = ${{{{ secrets.API }}}}", f"{NAME} = os.environ['API_KEY_NAME']"):
            self.assertIsNone(scan.named_value(line, 3.5), line)

    def test_a_literal_escape_ends_the_value(self):
        """A line of source that embeds a file holds the next setting after it, not more value."""
        self.assertIsNone(scan.named_value(r"DB_PASSWORD=hunter2\nExecStart=/usr/bin/app", 3.5))

    def test_a_provider_format_is_found_without_any_name_beside_it(self):
        found = scan.candidates("-----BEGIN PRIVATE KEY-----", 3.5)
        self.assertEqual(found[0][0], "private key block")

    def test_the_entropy_floor_moves_what_counts(self):
        self.assertIsNone(scan.named_value(f"{NAME} = {TOKEN}", 9.0))


class TreeTest(unittest.TestCase):
    def test_a_credential_in_a_tracked_file_is_a_finding_and_names_no_value(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"settings.py": f"{NAME} = '{TOKEN}'\n"})
            out = run(root, "--no-history")
            self.assertEqual(cost(out, "cred.tracked"), 1)
            self.assertNotIn(TOKEN, json.dumps(out))

    def test_the_finding_is_measured_per_file_so_a_row_grades_against_that_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": f"{NAME} = '{TOKEN}'\n",
                                    "b.py": f"{NAME} = '{OTHER}'\n"})
            out = run(root, "--no-history")
            self.assertEqual(item(out, "cred.tracked")["measure"]["by"], {"a.py": 1, "b.py": 1})

    def test_a_file_that_is_not_tracked_is_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": "x = 1\n"})
            (root / "untracked.py").write_text(f"{NAME} = '{TOKEN}'\n", encoding="utf-8")
            self.assertEqual(cost(run(root, "--no-history"), "cred.tracked"), 0)

    def test_a_binary_file_is_skipped_rather_than_decoded(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": "x = 1\n"})
            (root / "blob.bin").write_bytes(b"\0\0" + TOKEN.encode())
            git(root, "add", "-A")
            git(root, "commit", "-qm", "blob")
            self.assertEqual(cost(run(root, "--no-history"), "cred.tracked"), 0)


class HistoryTest(unittest.TestCase):
    def test_a_value_the_tree_no_longer_carries_is_still_reachable(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"settings.py": f"{NAME} = '{TOKEN}'\n"})
            repository(d, **{"settings.py": f"{NAME} = os.environ['API_KEY_NAME']\n"})
            out = run(root)
            self.assertEqual(cost(out, "cred.tracked"), 0)
            self.assertEqual(cost(out, "cred.history"), 1)

    def test_a_value_in_both_is_counted_once_in_the_tree(self):
        """The history check is what is left after the tree, so nothing is counted twice."""
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"settings.py": f"{NAME} = '{TOKEN}'\n"})
            out = run(root)
            self.assertEqual(cost(out, "cred.tracked"), 1)
            self.assertEqual(cost(out, "cred.history"), 0)

    def test_without_the_history_the_check_carries_a_note_and_no_number(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": "x = 1\n"})
            out = run(root, "--no-history")
            note = item(out, "cred.history", level="INFO")
            self.assertIsNone(note["measure"])
            self.assertIn("was not read", note["message"])

    def test_a_folder_that_is_no_repository_reads_the_tree_and_says_nothing_about_a_history(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.py").write_text(f"{NAME} = '{TOKEN}'\n", encoding="utf-8")
            out = run(d)
            self.assertEqual(cost(out, "cred.tracked"), 1)
            self.assertFalse(out["history_read"])


class RotationTest(unittest.TestCase):
    def test_every_finding_starts_unrotated(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": f"{NAME} = '{TOKEN}'\n"})
            self.assertEqual(cost(run(root, "--no-history"), "cred.unrotated"), 1)

    def test_a_recorded_rotation_settles_that_value_and_no_other(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": f"{NAME} = '{TOKEN}'\n",
                                    "b.py": f"{NAME} = '{OTHER}'\n"})
            spec = f"{scan.fingerprint(TOKEN)} provider 2026-09-01"
            out = run(root, "--no-history", "--rotated", spec)
            self.assertEqual(cost(out, "cred.unrotated"), 1)
            self.assertEqual(cost(out, "cred.tracked"), 2)

    def test_one_value_in_two_files_is_one_rotation(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": f"{NAME} = '{TOKEN}'\n",
                                    "b.py": f"other_{NAME} = '{TOKEN}'\n"})
            out = run(root, "--no-history")
            self.assertEqual(cost(out, "cred.tracked"), 2)
            self.assertEqual(cost(out, "cred.unrotated"), 1)


class AcceptTest(unittest.TestCase):
    def test_an_accepted_file_leaves_the_count_and_is_named_as_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": f"{NAME} = '{TOKEN}'\n"})
            out = run(root, "--no-history", "--accept", "cred.tracked a.py a test value 2026-01-01")
            self.assertEqual(cost(out, "cred.tracked"), 0)
            self.assertIn("1 finding is recorded as accepted", json.dumps(out))

    def test_accepting_the_tree_finding_does_not_hand_the_value_to_the_history(self):
        """Which check a value lands in is settled before the accepted list is applied. A value the
        tree carries is a tree finding, and accepting it must not surface it as a history one."""
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"settings.py": f"{NAME} = \'{TOKEN}\'\n"})
            out = run(root, "--accept", "cred.tracked settings.py a test value 2026-01-01")
            self.assertEqual(cost(out, "cred.tracked"), 0)
            self.assertEqual(cost(out, "cred.history"), 0)
            self.assertEqual(cost(out, "cred.unrotated"), 0)

    def test_an_entry_another_pass_owns_is_not_counted_here(self):
        """One accepted list reaches every pass, and a check id belongs to exactly one of them."""
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": "x = 1\n"})
            out = run(root, "--no-history", "--accept",
                      "build.action-unpinned .github/workflows/a.yml agreed 2026-01-01")
            self.assertNotIn("recorded as accepted", json.dumps(out))


class NameTest(unittest.TestCase):
    """The name half of an assignment is repository text and passes no filter of its own.

    Only the value is measured for length, character classes, a placeholder and entropy, so the
    name never carries the decision and must never carry into the report either.
    """

    def test_the_report_names_the_credential_word_and_not_what_the_file_wrote(self):
        with tempfile.TemporaryDirectory() as d:
            name = "Xy9Kd2Lm5Pt" + "8Rv1Nw6YQz3Hf7"
            root = repository(d, **{"conf.ini": f"{name}-secret = '{TOKEN}'\n"})
            out = run(root, "--no-history")
            self.assertEqual(cost(out, "cred.tracked"), 1)
            self.assertNotIn(name.lower(), json.dumps(out).lower())
            self.assertIn("value named by secret", json.dumps(out))

    def test_a_customer_name_in_a_setting_does_not_reach_the_audit(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"conf.ini": f"acme-corp.example.api_key = '{TOKEN}'\n"})
            out = run(root, "--no-history")
            self.assertEqual(cost(out, "cred.tracked"), 1)
            self.assertNotIn("acme-corp", json.dumps(out))


class ScannerTest(unittest.TestCase):
    def test_a_captured_scanner_report_is_merged_into_the_same_shape(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": "x = 1\n"})
            report = Path(d) / "report.json"
            report.write_text(json.dumps([{"File": "a.py", "StartLine": 1, "RuleID": "some-rule",
                                           "Secret": OTHER, "Commit": ""}]), encoding="utf-8")
            out = run(root, "--no-history", "--gitleaks-file", str(report))
            self.assertEqual(cost(out, "cred.tracked"), 1)
            self.assertTrue(out["scanner"])
            self.assertNotIn(OTHER, json.dumps(out))

    def test_the_scanner_and_this_pass_on_one_line_are_one_credential(self):
        """The scanner answers with an absolute path, this pass with a relative one. The place is
        what deduplicates them, so both have to write it the same way (decisions/0014)."""
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": f"{NAME} = '{TOKEN}'\n"})
            report = Path(d) / "report.json"
            report.write_text(json.dumps([{"File": str(root / "a.py"), "StartLine": 1,
                                           "RuleID": "some-rule", "Secret": OTHER, "Commit": ""}]),
                              encoding="utf-8")
            out = run(root, "--no-history", "--gitleaks-file", str(report))
            self.assertEqual(cost(out, "cred.tracked"), 1)
            self.assertEqual(cost(out, "cred.unrotated"), 1)
            self.assertNotIn(str(root), json.dumps(out))

    def test_without_a_scanner_the_pass_says_which_coverage_is_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": "x = 1\n"})
            out = run(root, "--no-history")
            self.assertIn("no scanner is installed",
                          " ".join(i["message"] for i in out["items"] if i["level"] == "INFO"))


class ContractTest(unittest.TestCase):
    def test_measures_prints_one_id_and_unit_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--measures"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, scan.MEASURES)

    def test_the_text_report_says_what_it_measured_against_and_ends_on_a_next_step(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": f"{NAME} = '{TOKEN}'\n"})
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--now", NOW,
                                "--no-tool", "--no-history"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured against", r.stdout)
            self.assertIn("\nnext  ", r.stdout)
            self.assertNotIn(TOKEN, r.stdout)

    def test_the_counting_line_is_a_bar_and_the_cost_stands_in_its_own_column(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": f"{NAME} = '{TOKEN}'\n"})
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--now", NOW,
                                "--no-tool", "--no-history"], capture_output=True, text=True)
            self.assertRegex(r.stdout, r"\n\d+ FAIL · \d+ WARN · \d+ notes? · \d+ passed\n")
            self.assertRegex(r.stdout, r"\nFAIL  cred\.tracked {18}1 credential\n")
            self.assertNotIn("(costs", r.stdout)
            self.assertIn("\n      gate: cred.*", r.stdout)

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": "x = 1\n"})
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--now", NOW,
                                "--no-tool", "--no-history"], capture_output=True, text=True)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            root = repository(d, **{"a.py": "x = 1\n"})
            env = dict(ENV, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--now", NOW,
                                "--no-tool", "--no-history"], capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
