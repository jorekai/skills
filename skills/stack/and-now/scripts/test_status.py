#!/usr/bin/env python3
"""Offline tests for the stack status: stage, the ladder order, the snapshot, and unknown ids.

Run: python3 skills/stack/and-now/scripts/test_status.py
Builds a workspace in a temp folder; no repository is read, no network.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status  # noqa: E402

SCRIPT = os.path.abspath(status.__file__)
FIXES = Path(SCRIPT).resolve().parents[2] / "stack" / "references" / "fixes.md"
TODAY = dt.date(2026, 9, 14)
HEAD = ("## Actions\n\n"
        "| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n")
SNAPSHOT = """name: example
oss_level: pragmatic
target: vercel
open_decisions:
  - what: blog
    recommend: a content collection
    until: {decided}
human_steps:
  - what: make the gate a required check on the default branch
    done: "{done}"
"""


def workspace(d, role="stack", path="~/code/example-repo", state="new", profile="standard",
              snapshot=True, decided="2026-12-01", done="2026-09-10"):
    root = Path(d) / "stack"
    base = root / "repos" / "example-repo"
    for sub in ("audits", "log/stack", "proposals"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    (base / "config.md").write_text(
        f"# example-repo\n\n- role: {role}\n- path: {path}\n- state: {state}\n", encoding="utf-8")
    (root / "standards.md").write_text(
        f"# S\n\n## Stack profile\n\n- profile: {profile}\n- verify_window_days: 14\n",
        encoding="utf-8")
    if snapshot:
        (base / "stack.yaml").write_text(SNAPSHOT.format(decided=decided, done=done),
                                         encoding="utf-8")
    return root, base


def rows(base, *lines):
    p = base / "log" / "stack" / "2026-W37.md"
    p.write_text("# 2026-W37\n\n" + HEAD + "".join(lines), encoding="utf-8")


def row(rid, check, status_="todo", after="", applied=""):
    return (f"| {rid} | {check} | a.ts | do a thing | ask | 1 count | {status_} "
            f"| {applied} | {after} |  |\n")


def audit(base, kind, date, items):
    (base / "audits" / f"{date}-{kind}.json").write_text(
        json.dumps({"tool": kind, "items": items}), encoding="utf-8")


def fail(cid):
    return {"id": cid, "level": "FAIL", "message": "m", "data": [],
            "measure": {"value": 1, "unit": "count", "by": {}}}


def state(root):
    return status.read_repo(root, "example-repo", TODAY)


class LadderTest(unittest.TestCase):
    def test_the_ladder_holds_thirty_ids(self):
        self.assertEqual(len(status.LADDER), 30)

    def test_the_ladder_equals_the_rung_column_of_the_fixes_table(self):
        table = {}
        for line in FIXES.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\|\s*`([a-z]+\.[a-z-]+)`\s*\|(?:[^|]*\|)+?\s*(\d+)\s*\|[^|]*\|\s*$", line)
            if m:
                table[m.group(1)] = int(m.group(2))
        self.assertEqual(table, status.LADDER)

    def test_every_id_of_the_ladder_names_the_skill_that_fixes_it(self):
        for cid in status.LADDER:
            self.assertTrue(status.skill_for(cid), cid)


class StageTest(unittest.TestCase):
    def test_an_empty_workspace_is_still_in_setup(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d, path="", state="", profile="", snapshot=False)
            stage, now, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "setup")
            self.assertTrue(all("setup" in n for n in now))

    def test_a_folder_that_does_not_say_stack_is_not_this_theme_s_business(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d, role="code")
            stage, now, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "setup")
            self.assertIn("does not say `role: stack`", now[0])

    def test_an_unfinished_setup_is_an_item_and_not_a_gate(self):
        """A repository that already has an audit is in the loop, whatever setup still lacks."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d, state="")
            audit(base, "guards", "2026-09-13", [fail("escape.type")])
            stage, now, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "measure")
            self.assertIn("escape.type", now[0])
            self.assertTrue(any("`state` is blank" in n for n in now))

    def test_without_an_audit_the_first_step_is_the_pass_that_finds_the_escapes(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            stage, now, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "measure")
            self.assertIn("jorekai-stack:guards", now[0])

    def test_with_only_rows_open_the_stage_is_the_loop(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "guards", "2026-09-13", [])
            audit(base, "drift", "2026-09-13", [])
            rows(base, row("2026-W37-01", "escape.type", "applied", "2026-09-30", "2026-09-10"))
            stage, _, _ = status.decide(state(root), TODAY)
            self.assertEqual(stage, "loop")


class OrderTest(unittest.TestCase):
    def test_a_row_past_its_verify_date_comes_before_every_finding(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "guards", "2026-09-13", [fail("escape.unenforced")])
            rows(base, row("2026-W37-01", "escape.type", "applied", "2026-09-01", "2026-08-25"))
            _, now, _ = status.decide(state(root), TODAY)
            self.assertIn("grade 1 row", now[0])

    def test_findings_come_in_ladder_order_and_not_in_the_order_of_the_audits(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "drift", "2026-09-13", [fail("boundary.crossed")])
            audit(base, "guards", "2026-09-13", [fail("escape.unowned"), fail("dead.export")])
            _, now, _ = status.decide(state(root), TODAY)
            self.assertIn("escape.unowned", now[0])
            self.assertIn("boundary.crossed", now[1])
            self.assertIn("dead.export", now[2])

    def test_a_row_naming_an_id_of_another_theme_is_named_as_such(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "guards", "2026-09-13", [])
            rows(base, row("2026-W37-01", "cred.tracked"))
            _, now, _ = status.decide(state(root), TODAY)
            self.assertTrue(any("does not own" in n and "cred.tracked" in n for n in now))

    def test_without_a_guards_audit_the_report_says_the_escapes_are_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "drift", "2026-09-13", [])
            _, now, _ = status.decide(state(root), TODAY)
            self.assertTrue(any("no `jorekai-stack:guards` audit" in n for n in now))

    def test_the_then_line_names_the_next_verify_date_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "guards", "2026-09-13", [])
            rows(base, row("2026-W37-01", "escape.type", "applied", "2026-12-01", "2026-09-01"))
            _, _, then = status.decide(state(root), TODAY)
            self.assertEqual(len(then), 1)
            self.assertIn("2026-12-01", then[0])


class SnapshotTest(unittest.TestCase):
    def test_an_undone_human_step_is_an_item_for_the_generator_skill(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d, done="")
            audit(base, "guards", "2026-09-13", [])
            _, now, _ = status.decide(state(root), TODAY)
            self.assertTrue(any(n.startswith("`jorekai-stack:new`: make the gate") for n in now))

    def test_a_done_human_step_is_no_item(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "guards", "2026-09-13", [])
            _, now, _ = status.decide(state(root), TODAY)
            self.assertFalse(any("is still open" in n for n in now))

    def test_a_decision_past_its_date_is_an_item_for_the_choose_skill(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d, decided="2026-09-01")
            audit(base, "guards", "2026-09-13", [])
            _, now, _ = status.decide(state(root), TODAY)
            self.assertTrue(any("jorekai-stack:choose" in n and "blog" in n for n in now))

    def test_a_missing_snapshot_is_one_item_naming_the_setup_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d, snapshot=False)
            audit(base, "guards", "2026-09-13", [])
            _, now, _ = status.decide(state(root), TODAY)
            hits = [n for n in now if "--snapshot" in n and "jorekai-stack:setup" in n]
            self.assertEqual(len(hits), 1)

    def test_an_unread_snapshot_says_so_instead_of_reading_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            (base / "stack.yaml").write_text("a: &x 1\n", encoding="utf-8")
            audit(base, "guards", "2026-09-13", [])
            s = state(root)
            self.assertTrue(s["snapshot"]["unread"])
            _, now, _ = status.decide(s, TODAY)
            self.assertTrue(any("could not be read" in n for n in now))


class ReportTest(unittest.TestCase):
    def test_the_report_names_the_stage_the_items_and_the_setup_line(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "guards", "2026-09-13", [fail("escape.type")])
            text = status.report(state(root), TODAY)
            self.assertIn("stage", text)
            self.assertIn("now", text)
            self.assertIn("profile standard · state new", text)
            self.assertIn("snapshot   0 human steps open, 0 decisions past the date", text)

    def test_a_workspace_that_does_not_exist_says_which_skill_makes_one(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", os.path.join(d, "nothing")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("jorekai-stack:setup", r.stdout)

    def test_a_folder_without_the_role_exits_two_when_nothing_else_is_there(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d, role="code")
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)

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
            self.assertRegex(text, r"\n  1\. jorekai-stack:guards {2}nothing has measured")
            self.assertNotIn("`jorekai-stack:guards`: nothing", text)

    def test_the_then_line_is_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "guards", "2026-09-13", [])
            rows(base, row("2026-W37-01", "escape.type", "applied", "2026-12-01", "2026-09-01"))
            text = status.report(state(root), TODAY)
            self.assertIn("\nthen  2026-12-01", text)
            self.assertEqual(text.count("\nthen"), 1)

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--today", "2026-09-14"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--today", "2026-09-14"],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
