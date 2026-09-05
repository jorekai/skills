#!/usr/bin/env python3
"""Offline tests for status.py: one fake workspace walked through every stage of the loop.

Run: python3 skills/dx/and-now/scripts/test_status.py
Uses setup/scripts/scaffold.py for the folders so the templates stay the single source of truth.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAFFOLD = HERE.parent.parent / "setup" / "scripts" / "scaffold.py"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status  # noqa: E402

TODAY = dt.date(2026, 9, 5)
MACHINE = "example-machine"
ROW = ("| {id} | {check} | {target} | {action} | {cls} | {then} | {st} | {applied} | {after} | |")


class Workspace:
    def __init__(self, d):
        self.root = Path(d) / "dx"
        subprocess.run([sys.executable, str(SCAFFOLD), "--root", str(self.root), MACHINE],
                       capture_output=True, text=True, check=True)
        self.base = self.root / "machines" / MACHINE

    def set_key(self, relpath, key, val):
        """Replace a template placeholder in place, the way a person filling the file does."""
        p = self.root / relpath
        text = re.sub(rf"^- {re.escape(key)}:.*$", f"- {key}: {val}", p.read_text(), count=1, flags=re.M)
        p.write_text(text)

    def machine_filled(self):
        self.set_key(f"machines/{MACHINE}/config.md", "project_roots", "~/code")

    def standards_filled(self):
        self.set_key("standards.md", "verify_window_days", "14")

    def config_filled(self):
        self.set_key("config.md", "forge", "example.com")

    def audit(self, name="2026-09-01-repos.json", fail=0, ids=()):
        items = [{"id": i, "level": "FAIL", "message": i} for i in ids]
        (self.base / "audits" / name).write_text(json.dumps(
            {"tool": "repos", "target": MACHINE, "counts": {"FAIL": fail, "WARN": 0}, "items": items}))

    def rows(self, *rows):
        subprocess.run([sys.executable, str(SCAFFOLD), "--root", str(self.root), MACHINE,
                        "--log", "--today", TODAY.isoformat()], capture_output=True, text=True, check=True)
        p = self.base / "log" / "2026-W36.md"
        p.write_text(p.read_text() + "\n".join(rows) + "\n")

    def read(self):
        return status.read_machine(self.root, MACHINE, TODAY)

    def decide(self):
        return status.decide(self.read(), TODAY)


class StageTest(unittest.TestCase):
    def test_a_fresh_workspace_is_setup_with_one_item(self):
        with tempfile.TemporaryDirectory() as d:
            stage, now, _ = Workspace(d).decide()
            self.assertEqual(stage, "setup")
            self.assertEqual(len(now), 1)
            self.assertIn("jorekai-dx:setup", now[0])

    def test_setup_items_are_listed_not_gated_once_the_loop_started(self):
        """A machine with an audit is in the loop; its open setup work is an item, not a wall."""
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.audit()
            stage, now, _ = w.decide()
            self.assertNotEqual(stage, "setup")
            self.assertTrue(any("standards.md is still the template" in i for i in now))

    def test_no_audit_yet_asks_for_a_measurement(self):
        """Setup is complete and nothing has measured yet: the machine is unknown, not unset."""
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.config_filled()
            stage, now, _ = w.decide()
            self.assertEqual(stage, "measure")
            self.assertIn("no audit on this machine yet", now[0])

    def test_a_row_past_its_verify_date_outranks_the_audit(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit(fail=2, ids=("git.dirty", "disk.low"))
            w.rows(ROW.format(id="2026-W36-01", check="disk.cache", target="~/x", action="cleared",
                              cls="safe", then="41", st="applied", applied="2026-08-20", after="2026-09-03"))
            _, now, _ = w.decide()
            self.assertIn("past their verify date", now[0])
            self.assertIn("2 FAIL", now[1])

    def test_a_future_verify_date_becomes_the_then_line(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit()
            w.rows(ROW.format(id="2026-W36-01", check="disk.cache", target="~/x", action="cleared",
                              cls="safe", then="41", st="applied", applied="2026-09-02", after="2026-09-16"))
            _, now, then = w.decide()
            self.assertEqual(then, ["2026-09-16: first verify date reached, grade the row it belongs to"])
            self.assertFalse(any("past their verify date" in i for i in now))

    def test_an_open_row_and_a_proposal_are_both_listed(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit()
            w.rows(ROW.format(id="2026-W36-01", check="git.stale-branch", target="example-app",
                              action="delete four merged branches", cls="confirm", then="4", st="todo",
                              applied="", after=""))
            (w.base / "proposals" / "shell-alias.md").write_text("# idea\n")
            _, now, _ = w.decide()
            self.assertTrue(any("open row 2026-W36-01" in i for i in now))
            self.assertTrue(any("proposals/shell-alias.md" in i for i in now))

    def test_a_stale_audit_is_reported_even_with_zero_fail(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit(name="2026-06-01-repos.json")
            _, now, _ = w.decide()
            self.assertTrue(any("old: measure again" in i for i in now))

    def test_a_settled_machine_says_nothing_is_open(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.config_filled()
            w.audit()
            _, now, _ = w.decide()
            self.assertEqual(now, ["nothing open: measure again when the newest audit ages out"])

    def test_a_broken_audit_file_does_not_crash_the_report(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            (w.base / "audits" / "2026-09-01-repos.json").write_text("{not json")
            out = status.report(w.read(), TODAY)
            self.assertIn("2026-09-01-repos.json", out)


class CliTest(unittest.TestCase):
    def test_no_workspace_exits_2_and_names_the_skill(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(Path(d) / "dx")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("jorekai-dx:setup", r.stdout)

    def test_a_machine_name_with_a_separator_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(w.root), "../escaped"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

    def test_the_report_prints_stage_and_a_numbered_now_list(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(w.root),
                                "--today", TODAY.isoformat()], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("stage: ", r.stdout)
            self.assertIn("now:\n  1. ", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
