#!/usr/bin/env python3
"""Exercise the stack loop with real script output, from an audit to the monthly report.

Run: python3 skills/stack/grade/scripts/test_loop.py
Every workspace is temporary. No repository is generated and no network is used: the audits are
JSON files in the shape the measuring scripts write, so the loop is proved on its own files.
The workspace is scaffolded by `jorekai-stack:setup` when that script exists beside this theme,
and built by hand otherwise, so this test never waits for another skill.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

THEME = Path(__file__).resolve().parents[2]
SLUG = "example-repo"
SCAFFOLD = THEME / "setup" / "scripts" / "scaffold.py"
LOG_HEAD = """# 2026-W36 (2026-08-31 to 2026-09-06)

Repository: example-repo

## Outcomes of earlier actions

| id | Check | Target | Applied | Then | Now | Verdict |
|---|---|---|---|---|---|---|

## Actions

| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |
|---|---|---|---|---|---|---|---|---|---|
"""


def finding(cid, value, by=None, unit="count"):
    return {"id": cid, "level": "FAIL" if value else "PASS", "message": "m", "data": [],
            "measure": {"value": value, "unit": unit, "by": by or {}}}


class StackLoopTest(unittest.TestCase):
    def call(self, skill, script, *args):
        result = subprocess.run([sys.executable, str(THEME / skill / "scripts" / script),
                                 *map(str, args)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name) / "workspace"
        self.base = self.workspace / "repos" / SLUG
        if SCAFFOLD.is_file():
            self.call("setup", "scaffold.py", "--root", self.workspace, SLUG)
            self.scaffolded = True
        else:
            for sub in ("audits", "log/stack", "reports/stack", "proposals"):
                (self.base / sub).mkdir(parents=True)
            (self.base / "config.md").write_text("- role: stack\n", encoding="utf-8")
            (self.workspace / "standards.md").write_text("- verify_window_days: 7\n", encoding="utf-8")
            self.scaffolded = False
        self.audit("2026-08-31", finding("escape.type", 2, {"a.ts:3": 1, "b.ts:9": 1}))
        self.log = self.base / "log" / "stack" / "2026-W36.md"
        self.log.write_text(LOG_HEAD + "| 2026-W36-01 | escape.type |  | fix both lines | ask "
                            "| 2 count | applied | 2026-09-01 | 2026-09-08 |  |\n", encoding="utf-8")

    def audit(self, date, *items):
        data = {"tool": "guards", "target": SLUG, "generated": date,
                "counts": {}, "declaration": "read", "items": list(items)}
        (self.base / "audits" / f"{date}-guards.json").write_text(json.dumps(data), encoding="utf-8")

    def grade(self, date="2026-09-13"):
        text = self.call("grade", "grade.py", "--root", self.workspace, SLUG,
                         "--today", date, "--write", "--json")
        return json.loads(text)["repos"][SLUG]

    def report(self):
        text = self.call("report", "report.py", "--root", self.workspace, SLUG,
                         "--month", "2026-09", "--write", "--json")
        self.assertTrue((self.base / "reports" / "stack" / "2026-09.md").is_file())
        return json.loads(text)["repos"][SLUG]

    def test_a_measured_fix_closes_once_and_reaches_the_monthly_report(self):
        self.audit("2026-09-13", finding("escape.type", 0))
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
        movement = next(r for r in report["movement"] if r["check"] == "escape.type")
        self.assertEqual((movement["then"], movement["now"]), ("2 count", "0 count"))

    def test_a_measure_nobody_took_keeps_the_action_open(self):
        """A null is not a zero: the pass ran before a full gate, so the row waits."""
        self.audit("2026-09-13", finding("escape.type", None))
        before = self.log.read_text(encoding="utf-8")
        result = self.grade()
        self.assertEqual(result["graded"][0]["verdict"], "")
        self.assertEqual(result["written"], [])
        self.assertEqual(self.log.read_text(encoding="utf-8"), before)
        report = self.report()
        self.assertEqual(report["counts"]["won"], 0)
        self.assertEqual(len(report["open"]), 1)
        self.assertFalse(any(r["check"] == "escape.type" for r in report["movement"]))
        self.assertTrue(any("escape.type" in note and "incomplete measurement" in note
                            for note in report["notes"]))

    def test_a_suppression_that_came_back_is_returned(self):
        self.audit("2026-09-13", finding("escape.type", 3, {"a.ts:3": 1, "b.ts:9": 1, "c.ts:1": 1}))
        result = self.grade()
        self.assertEqual(result["graded"][0]["verdict"], "returned")
        self.assertEqual(self.report()["counts"]["returned"], 1)

    def test_the_status_reads_the_same_workspace(self):
        out = self.call("and-now", "status.py", "--root", self.workspace, SLUG, "--today", "2026-09-13")
        self.assertIn("grade 1 row", out)
        self.assertIn("stage", out)


if __name__ == "__main__":
    unittest.main()
