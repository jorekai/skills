#!/usr/bin/env python3
"""Offline tests for review.py: what makes a rule open, what closes it, and what cannot be used.

Run: python3 skills/security/review/scripts/test_review.py
Every test builds its rules and its code in a temporary directory; no network, no model.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review  # noqa: E402

SCRIPT = os.path.abspath(review.__file__)
NOW = "2026-09-09T12:00:00"


def rule(rid="vuln.injection-01", check="vuln.injection", path="src/*.py",
         sink=r"execute\(f\"", mitigation="", why="the value comes from the query string"):
    return {"id": rid, "check": check, "path": path, "sink": sink, "mitigation": mitigation,
            "why": why, "written": "2026-09-01", "commit": "abc1234"}


def workspace(d, rules=(), **files):
    root = Path(d) / "repo"
    rules_dir = Path(d) / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        p = root / name.replace("__", "/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(rules, 1):
        (rules_dir / f"rule-{i}.json").write_text(
            r if isinstance(r, str) else json.dumps(r), encoding="utf-8")
    return root, rules_dir


def run(root, rules_dir, *extra):
    args = [sys.executable, SCRIPT, "--json", "--now", NOW, "--root", str(root),
            "--rules-dir", str(rules_dir), *extra]
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


class LoadTest(unittest.TestCase):
    def test_a_rule_without_its_required_fields_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [{"id": "x", "check": "vuln.injection"}])
            out = run(root, rules)
            self.assertEqual(out["rules"], [])
            self.assertIn("no path, sink", out["unusable"][0]["why"])

    def test_a_pattern_that_does_not_compile_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule(sink="execute(")])
            self.assertIn("does not compile", run(root, rules)["unusable"][0]["why"])

    def test_a_check_this_pass_does_not_measure_cannot_be_used(self):
        """A rule naming another theme's id would write a row nothing here recomputes."""
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule(check="cred.tracked")])
            self.assertIn("not a check this pass measures", run(root, rules)["unusable"][0]["why"])

    def test_a_file_that_is_no_json_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, ["{not json"])
            self.assertIn("does not parse", run(root, rules)["unusable"][0]["why"])


class MatchTest(unittest.TestCase):
    CODE = 'def get(x):\n    cursor.execute(f"select * from t where id = {x}")\n'
    SAFE = 'def get(x):\n    cursor.execute("select * from t where id = %s", [x])\n'

    def test_a_sink_that_is_still_written_leaves_the_rule_open(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()], **{"src__a.py": self.CODE})
            out = run(root, rules)
            self.assertEqual(cost(out, "vuln.injection"), 1)
            self.assertEqual(item(out, "vuln.injection")["measure"]["by"], {"vuln.injection-01": 1})

    def test_a_sink_that_is_gone_closes_the_rule_and_the_measure_reads_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()], **{"src__a.py": self.SAFE})
            out = run(root, rules)
            self.assertEqual(cost(out, "vuln.injection"), 0)
            self.assertEqual(item(out, "vuln.injection")["level"], "PASS")

    def test_a_mitigation_beside_the_sink_closes_the_rule(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule(mitigation=r"# reviewed: bound below")],
                                    **{"src__a.py": "# reviewed: bound below\n" + self.CODE})
            self.assertEqual(cost(run(root, rules), "vuln.injection"), 0)

    def test_the_finding_names_the_file_and_the_line_it_is_on(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()], **{"src__a.py": self.CODE})
            self.assertIn("src/a.py:2", json.dumps(run(root, rules)))

    def test_a_rule_whose_path_matches_nothing_needs_a_person(self):
        """A file that was deleted and a flaw that was fixed look the same to a matcher."""
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule(path="gone/*.py")], **{"src__a.py": self.CODE})
            out = run(root, rules)
            self.assertEqual(cost(out, "vuln.injection"), 0)
            self.assertIn("matches no file today", json.dumps(out))

    def test_the_sentence_agrees_with_the_count_in_front_of_it(self):
        """One rule is, two rules are. A report that prints the other reads like a template."""
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()], **{"src__a.py": self.CODE})
            self.assertIn("1 rule of this class is still open",
                          item(run(root, rules), "vuln.injection")["message"])
            root, rules = workspace(d, [rule(), rule(rid="vuln.injection-02", sink=r"execute\(")],
                                    **{"src__a.py": self.CODE})
            self.assertIn("2 rules of this class are still open",
                          item(run(root, rules), "vuln.injection")["message"])

    def test_one_rule_counts_once_however_many_files_carry_the_sink(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()],
                                    **{"src__a.py": self.CODE, "src__b.py": self.CODE})
            self.assertEqual(cost(run(root, rules), "vuln.injection"), 1)

    def test_each_class_is_counted_on_its_own(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule(), rule(rid="vuln.ssrf-01", check="vuln.ssrf",
                                                     sink=r"requests\.get\(url")],
                                    **{"src__a.py": self.CODE + "requests.get(url)\n"})
            out = run(root, rules)
            self.assertEqual(cost(out, "vuln.injection"), 1)
            self.assertEqual(cost(out, "vuln.ssrf"), 1)

    def test_a_class_with_no_rule_is_not_reported_as_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()], **{"src__a.py": self.CODE})
            ids = [i["id"] for i in run(root, rules)["items"]]
            self.assertNotIn("vuln.crypto", ids)

    def test_a_binary_file_is_not_searched(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule(path="src/*.bin", sink="secret")])
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "a.bin").write_bytes(b"\0\0secret")
            out = run(root, rules)
            self.assertIn("matches no file today", json.dumps(out))


class AcceptTest(unittest.TestCase):
    def test_an_accepted_rule_leaves_the_count(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()], **{"src__a.py": MatchTest.CODE})
            out = run(root, rules, "--accept", "vuln.injection vuln.injection-01 agreed 2026-01-01")
            self.assertEqual(cost(out, "vuln.injection"), 0)
            self.assertIn("accepted", json.dumps(out))


class EmptyTest(unittest.TestCase):
    def test_without_a_rule_the_pass_measures_nothing_rather_than_passing(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [], **{"src__a.py": MatchTest.CODE})
            out = run(root, rules)
            self.assertEqual([i for i in out["items"] if i["level"] == "PASS"], [])
            self.assertIn("no rule has been written yet",
                          item(out, "vuln.injection", level="INFO")["message"])


class ContractTest(unittest.TestCase):
    def test_measures_prints_one_id_and_unit_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--measures"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, review.MEASURES)

    def test_the_text_report_says_what_it_measured_against_and_ends_on_a_next_step(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()], **{"src__a.py": MatchTest.CODE})
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--rules-dir",
                                str(rules), "--now", NOW], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured against", r.stdout)
            self.assertIn("\nnext  ", r.stdout)

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()])
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--rules-dir",
                                str(rules), "--now", NOW], capture_output=True, text=True)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            root, rules = workspace(d, [rule()], **{"src__a.py": MatchTest.CODE})
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--rules-dir",
                                str(rules), "--now", NOW], capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
