#!/usr/bin/env python3
"""Exercise the security loop with real script output, from review to the monthly report.

Run: python3 skills/security/grade/scripts/test_loop.py
Every repository and workspace is temporary. No network or external scanner is used.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

THEME = Path(__file__).resolve().parents[2]
SLUG = "example-repo"
RULE = "vuln.injection-01"
CODE = 'cursor.execute(f"select * from t where id = {value}")\n'
FIXED = 'cursor.execute("select * from t where id = %s", [value])\n'


class SecurityLoopTest(unittest.TestCase):
    def call(self, skill, script, *args):
        result = subprocess.run([sys.executable, str(THEME / skill / "scripts" / script),
                                 *map(str, args)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.workspace = root / "workspace"
        self.repo = root / SLUG
        self.source = self.repo / "src" / "handler.py"
        self.source.parent.mkdir(parents=True)
        self.source.write_text(CODE, encoding="utf-8")
        self.call("setup", "scaffold.py", "--root", self.workspace, SLUG)
        self.base = self.workspace / "repos" / SLUG
        rule = {"id": RULE, "check": "vuln.injection", "path": "src/*.py",
                "sink": r'execute\(f"', "why": "the query receives request input",
                "written": "2026-08-31", "commit": "abc1234"}
        self.rule_file = self.base / "rules" / (RULE + ".json")
        self.rule_file.write_text(json.dumps(rule), encoding="utf-8")
        before = self.audit("2026-08-31")
        measure = next(i["measure"] for i in before["items"] if i["id"] == "vuln.injection")
        self.assertEqual(measure["by"][RULE], 1)
        self.call("setup", "scaffold.py", "--root", self.workspace, SLUG, "--append-row",
                  "--check-id", "vuln.injection", "--target", RULE, "--action", "Bind the query value",
                  "--class", "confirm", "--then", f"{measure['by'][RULE]} {measure['unit']}",
                  "--status", "applied", "--today", "2026-09-01", "--verify-days", "7")
        self.log = next((self.base / "log" / "security").glob("*.md"))

    def audit(self, date):
        text = self.call("review", "review.py", "--root", self.repo,
                         "--rules-dir", self.base / "rules", "--now", date + "T12:00:00", "--json")
        (self.base / "audits" / f"{date}-review.json").write_text(text, encoding="utf-8")
        return json.loads(text)

    def grade(self, date="2026-09-13"):
        text = self.call("grade", "grade.py", "--root", self.workspace, SLUG,
                         "--today", date, "--write", "--json")
        return json.loads(text)["repos"][SLUG]

    def report(self):
        text = self.call("report", "report.py", "--root", self.workspace, SLUG,
                         "--month", "2026-09", "--write", "--json")
        self.assertTrue((self.base / "reports" / "security" / "2026-09.md").is_file())
        return json.loads(text)["repos"][SLUG]

    def test_a_measured_fix_closes_once_and_reaches_the_monthly_report(self):
        self.source.write_text(FIXED, encoding="utf-8")
        self.audit("2026-09-13")
        self.assertEqual(self.grade("2026-09-02")["graded"], [])
        settled = self.grade()
        self.assertEqual([g["verdict"] for g in settled["graded"]], ["won"])
        self.assertEqual(settled["graded"][0]["now"], "0 count")
        self.assertEqual(len(settled["written"]), 1)
        after = self.log.read_text(encoding="utf-8")
        self.assertEqual(self.grade()["written"], [])
        self.assertEqual(self.log.read_text(encoding="utf-8"), after)
        report = self.report()
        self.assertEqual(report["counts"]["won"], 1)
        self.assertEqual(report["open"], [])
        movement = next(r for r in report["movement"] if r["check"] == "vuln.injection")
        self.assertEqual((movement["then"], movement["now"]), ("1 count", "0 count"))

    def test_a_moved_file_never_becomes_a_win_or_a_measured_drop(self):
        self.source.rename(self.repo / "moved.py")
        self.audit("2026-09-13")
        before = self.log.read_text(encoding="utf-8")
        result = self.grade()
        self.assertEqual(result["graded"][0]["verdict"], "")
        self.assertEqual(result["written"], [])
        self.assertEqual(self.log.read_text(encoding="utf-8"), before)
        report = self.report()
        self.assertEqual(report["counts"]["won"], 0)
        self.assertEqual(len(report["open"]), 1)
        self.assertFalse(any(r["check"] == "vuln.injection" for r in report["movement"]))
        self.assertTrue(any("vuln.injection" in note and "incomplete measurement" in note
                            for note in report["notes"]))

    def test_a_broken_rule_keeps_the_action_open(self):
        self.rule_file.write_text("{not json", encoding="utf-8")
        self.audit("2026-09-13")
        result = self.grade()
        self.assertEqual(result["graded"][0]["verdict"], "")
        self.assertEqual(result["written"], [])
        self.assertEqual(self.report()["counts"]["won"], 0)

    def test_a_fixed_target_can_close_while_another_target_remains_unknown(self):
        other = json.loads(self.rule_file.read_text(encoding="utf-8"))
        other.update(id="vuln.injection-02", path="missing/*.py")
        (self.rule_file.parent / "other.json").write_text(json.dumps(other), encoding="utf-8")
        self.source.write_text(FIXED, encoding="utf-8")
        self.audit("2026-09-13")
        self.assertEqual(self.grade()["graded"][0]["verdict"], "won")
        report = self.report()
        self.assertEqual(report["counts"]["won"], 1)
        self.assertFalse(any(r["check"] == "vuln.injection" for r in report["movement"]))


if __name__ == "__main__":
    unittest.main()
