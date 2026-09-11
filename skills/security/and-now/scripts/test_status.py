#!/usr/bin/env python3
"""Offline tests for the security status: stage, the ladder order, and unknown ids.

Run: python3 skills/security/and-now/scripts/test_status.py
Builds a workspace in a temp folder; no repository is read, no network.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status  # noqa: E402

SCRIPT = os.path.abspath(status.__file__)
TODAY = dt.date(2026, 9, 9)
HEAD = ("## Actions\n\n"
        "| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n")


def workspace(d, role="code", path="~/code/example-repo", entrypoints="http@src/api.py",
              store="the password manager", profile="baseline"):
    root = Path(d) / "sec"
    base = root / "repos" / "example-repo"
    for sub in ("audits", "log/security", "proposals", "rules"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    (base / "config.md").write_text(
        f"# example-repo\n\n## Ecosystem\n\n- role: {role}\n- path: {path}\n"
        f"- entrypoints: {entrypoints}\n- secret_store: {store}\n", encoding="utf-8")
    (root / "standards.md").write_text(
        f"# S\n\n## Security profile\n\n- profile: {profile}\n- verify_window_days: 14\n",
        encoding="utf-8")
    return root, base


def rows(base, *lines):
    p = base / "log" / "security" / "2026-W36.md"
    p.write_text("# 2026-W36\n\n" + HEAD + "".join(lines), encoding="utf-8")


def row(rid, check, status_="todo", after="", applied=""):
    return (f"| {rid} | {check} | a.py | do a thing | ask | 1 count | {status_} "
            f"| {applied} | {after} |  |\n")


def audit(base, kind, date, items):
    (base / "audits" / f"{date}-{kind}.json").write_text(
        json.dumps({"tool": kind, "items": items}), encoding="utf-8")


def fail(cid):
    return {"id": cid, "level": "FAIL", "message": "m", "data": [],
            "measure": {"value": 1, "unit": "count", "by": {}}}


def state(root):
    return status.read_repo(root, "example-repo", TODAY)


class StageTest(unittest.TestCase):
    def test_an_empty_workspace_is_still_in_setup(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d, path="", entrypoints="", store="", profile="")
            stage, now, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "setup")
            self.assertTrue(all("setup" in n for n in now))

    def test_a_folder_that_does_not_say_code_is_not_this_theme_s_business(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d, role="notes")
            stage, now, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "setup")
            self.assertIn("does not say `role: code`", now[0])

    def test_an_unfinished_setup_is_an_item_and_not_a_gate(self):
        """A repository that already has an audit is in the loop, whatever setup still lacks."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d, entrypoints="")
            audit(base, "secrets", "2026-09-08", [fail("cred.tracked")])
            stage, now, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "measure")
            self.assertIn("cred.tracked", now[0])
            self.assertTrue(any("no entry point is recorded" in n for n in now))

    def test_without_an_audit_the_first_step_is_the_pass_that_finds_what_is_already_out(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            stage, now, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "measure")
            self.assertIn("jorekai-security:secrets", now[0])

    def test_with_only_rows_open_the_stage_is_the_loop(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "secrets", "2026-09-08", [])
            audit(base, "pipeline", "2026-09-08", [])
            rows(base, row("2026-W36-01", "cred.tracked", "applied", "2026-09-08", "2026-08-25"))
            stage, _, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "loop")


class OrderTest(unittest.TestCase):
    def test_a_row_past_its_verify_date_comes_before_every_finding(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "deps", "2026-09-08", [fail("dep.known-exploited")])
            rows(base, row("2026-W36-01", "cred.tracked", "applied", "2026-09-01", "2026-08-25"))
            _, now, _ = status.decide(state(root), TODAY)
            self.assertIn("grade 1 row", now[0])

    def test_findings_come_in_ladder_order_and_not_in_the_order_of_the_audits(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "deps", "2026-09-08", [fail("dep.unresolved")])
            audit(base, "secrets", "2026-09-08", [fail("cred.history")])
            _, now, _ = status.decide(state(root), TODAY)
            self.assertIn("cred.history", now[0])
            self.assertIn("dep.unresolved", now[1])

    def test_every_id_of_the_ladder_names_the_skill_that_fixes_it(self):
        for cid in status.LADDER:
            self.assertTrue(status.skill_for(cid), cid)

    def test_a_row_naming_an_id_of_another_theme_is_named_as_such(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "secrets", "2026-09-08", [])
            rows(base, row("2026-W36-01", "secret.in-repo"))
            _, now, _ = status.decide(state(root), TODAY)
            self.assertTrue(any("does not own" in n for n in now))

    def test_the_then_line_names_the_next_verify_date_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "secrets", "2026-09-08", [])
            rows(base, row("2026-W36-01", "cred.tracked", "applied", "2026-12-01", "2026-09-01"))
            _, _, then = status.decide(state(root), TODAY)
            self.assertEqual(len(then), 1)
            self.assertIn("2026-12-01", then[0])

    def test_a_review_audit_without_a_rule_says_the_finding_earned_no_row(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "secrets", "2026-09-08", [])
            audit(base, "review", "2026-09-08", [])
            _, now, _ = status.decide(state(root), TODAY)
            self.assertTrue(any("earns no log row" in n for n in now))

    def test_a_rule_on_disk_settles_that_item(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "secrets", "2026-09-08", [])
            audit(base, "review", "2026-09-08", [])
            (base / "rules" / "vuln.injection-01.json").write_text("{}", encoding="utf-8")
            _, now, _ = status.decide(state(root), TODAY)
            self.assertFalse(any("earns no log row" in n for n in now))


class ReportTest(unittest.TestCase):
    def test_the_report_names_the_stage_the_items_and_the_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "secrets", "2026-09-08", [fail("cred.tracked")])
            text = status.report(state(root), TODAY)
            self.assertIn("stage", text)
            self.assertIn("now", text)
            self.assertIn("rules      0 rules", text)

    def test_a_workspace_that_does_not_exist_says_which_skill_makes_one(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", os.path.join(d, "nothing")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("jorekai-security:setup", r.stdout)

    def test_a_repository_name_that_is_a_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "../escaped"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

    def test_now_lines_carry_the_skill_as_their_own_aligned_column(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            text = status.report(state(root), TODAY)
            self.assertRegex(text, r"\n  1\. jorekai-security:secrets {2}nothing has measured")
            self.assertNotIn("`jorekai-security:secrets`: nothing", text)

    def test_the_then_line_is_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "secrets", "2026-09-08", [])
            rows(base, row("2026-W36-01", "cred.tracked", "applied", "2026-12-01", "2026-09-01"))
            text = status.report(state(root), TODAY)
            self.assertIn("\nthen  2026-12-01", text)
            self.assertEqual(text.count("\nthen"), 1)

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--today", "2026-09-09"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
