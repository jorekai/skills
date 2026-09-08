#!/usr/bin/env python3
"""Offline tests for report.py: the month window, what moved, what was done, what stays open.

Run: python3 skills/dx/report/scripts/test_report.py
Builds a workspace in a temporary directory: audits as JSON, log weeks as markdown. Nothing is
measured, so no machine is touched.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report  # noqa: E402

SCRIPT = os.path.abspath(report.__file__)
MACHINE = "example-machine"
MONTH = "2026-09"
LOG_HEAD = """# 2026-W37 (2026-09-07 to 2026-09-13)

Machine: example-machine

## Outcomes of earlier actions

| id | Check | Target | Applied | Then | Now | Verdict |
|---|---|---|---|---|---|---|
{outcomes}

## Actions

| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |
|---|---|---|---|---|---|---|---|---|---|
{actions}
"""


def workspace(d):
    root = Path(d) / "dx"
    base = root / "machines" / MACHINE
    (base / "audits").mkdir(parents=True)
    (base / "log" / "dx").mkdir(parents=True)
    (base / "config.md").write_text("- role: laptop\n", encoding="utf-8")
    return root, base


def audit(base, date, tool, items):
    path = base / "audits" / f"{date}-{tool}.json"
    path.write_text(json.dumps({"tool": tool, "items": items}), encoding="utf-8")
    return path


def measured(cid, value, unit="GB"):
    return {"id": cid, "level": "WARN", "message": "x", "data": [],
            "measure": {"value": value, "unit": unit, "by": {}}}


def log(base, actions=(), outcomes=(), name="2026-W37.md"):
    (base / "log" / "dx" / name).write_text(
        LOG_HEAD.format(actions="\n".join(actions), outcomes="\n".join(outcomes)),
        encoding="utf-8")


def action(row_id, check, status="applied", applied="2026-09-08", target="~/x", verify="2026-09-22"):
    return (f"| {row_id} | {check} | {target} | cleared it | confirm | 10 GB | {status} "
            f"| {applied} | {verify} |  |")


def run(root, extra=()):
    args = [sys.executable, SCRIPT, "--root", str(root), MACHINE, "--month", MONTH, "--json"]
    r = subprocess.run(args + list(extra), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)["machines"][MACHINE]


class WindowTest(unittest.TestCase):
    def test_a_month_gives_its_first_and_last_day(self):
        self.assertEqual(report.month_bounds("2026-02"),
                         (__import__("datetime").date(2026, 2, 1),
                          __import__("datetime").date(2026, 2, 28)))

    def test_a_month_that_is_not_one_is_refused(self):
        with self.assertRaises(SystemExit):
            report.month_bounds("september")

    def test_a_week_file_gives_the_days_it_covers(self):
        start, end = report.week_bounds("2026-W37")
        self.assertEqual(start.isoformat(), "2026-09-07")
        self.assertEqual(end.isoformat(), "2026-09-13")

    def test_a_file_that_is_not_a_week_is_no_window(self):
        self.assertIsNone(report.week_bounds("notes"))


class ActionTest(unittest.TestCase):
    def test_an_action_belongs_to_the_month_it_was_applied_in(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W37-01", "disk.cache"),
                               action("2026-W37-02", "disk.low", applied="2026-08-30")])
            out = run(root)
            self.assertEqual([r["id"] for r in out["actions"]], ["2026-W37-01"])

    def test_a_week_that_straddles_two_months_counts_where_most_of_its_days_are(self):
        """An action counted in both months would be reported as done twice."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W36-01", "disk.cache", applied="")],
                name="2026-W36.md")
            self.assertEqual([r["id"] for r in run(root)["actions"]], ["2026-W36-01"])
            log(base, actions=[action("2026-W40-01", "disk.cache", applied="")],
                name="2026-W40.md")
            self.assertEqual(sorted(r["id"] for r in run(root)["actions"]), ["2026-W36-01"])

    def test_a_verdict_written_by_the_grade_skill_is_counted(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W37-01", "disk.cache", status="won"),
                               action("2026-W37-02", "disk.low", status="returned")])
            counts = run(root)["counts"]
            self.assertEqual((counts["won"], counts["returned"]), (1, 1))

    def test_a_verdict_that_only_stands_in_the_outcomes_table_is_read_there(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W37-01", "disk.cache", status="verify")],
                outcomes=["| 2026-W37-01 | disk.cache | ~/x | 2026-09-08 | 10 GB | 2 GB | won |"])
            out = run(root)
            self.assertEqual(out["counts"]["won"], 1)

    def test_an_open_action_is_listed_whatever_month_it_comes_from(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W30-01", "git.dirty", status="todo", applied="")],
                name="2026-W30.md")
            self.assertEqual([r["id"] for r in run(root)["open"]], ["2026-W30-01"])

    def test_the_open_rows_come_in_ladder_order_and_the_first_three_are_the_next_steps(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W37-01", "git.stale-branch", status="todo"),
                               action("2026-W37-02", "git.dirty", status="todo"),
                               action("2026-W37-03", "disk.low", status="todo"),
                               action("2026-W37-04", "disk.cache", status="todo")])
            out = run(root)
            self.assertEqual([r["check"] for r in out["open"]][:3],
                             ["git.dirty", "disk.low", "disk.cache"])


    def test_a_row_nobody_has_carried_out_does_not_read_as_measuring(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W37-01", "disk.cache", status="todo"),
                               action("2026-W37-02", "disk.low", status="applied")])
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), MACHINE,
                                "--month", MONTH], capture_output=True, text=True)
            self.assertIn("not done yet", r.stdout)
            self.assertIn("still measuring", r.stdout)


class MovementTest(unittest.TestCase):
    def test_a_cost_that_fell_between_two_audits_is_the_movement(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "2026-08-30", "machine", [measured("disk.cache", 40)])
            audit(base, "2026-09-20", "machine", [measured("disk.cache", 12)])
            moved = run(root)["movement"]
            self.assertEqual(moved[0]["check"], "disk.cache")
            self.assertEqual((moved[0]["then"], moved[0]["now"]), ("40 GB", "12 GB"))
            self.assertLess(moved[0]["change"], 0)

    def test_two_units_of_the_same_family_still_compare(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "2026-08-30", "machine", [measured("disk.cache", 2, "GB")])
            audit(base, "2026-09-20", "machine", [measured("disk.cache", 512, "MB")])
            moved = run(root)["movement"]
            self.assertEqual((moved[0]["then"], moved[0]["now"]), ("2 GB", "0.5 GB"))

    def test_two_units_of_different_families_are_left_out(self):
        """A count against a size compares nothing, and a report that prints it invents a change."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "2026-08-30", "machine", [measured("disk.cache", 40, "GB")])
            audit(base, "2026-09-20", "machine", [measured("disk.cache", 3, "count")])
            self.assertEqual(run(root)["movement"], [])

    def test_a_month_with_no_audit_inside_it_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "2026-08-30", "machine", [measured("disk.cache", 40)])
            out = run(root)
            self.assertEqual(out["movement"], [])
            self.assertTrue(any("no machine audit inside the month" in n for n in out["notes"]))

    def test_one_audit_and_nothing_before_it_opens_the_next_report(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "2026-09-20", "machine", [measured("disk.cache", 40)])
            out = run(root)
            self.assertEqual(out["movement"], [])
            self.assertTrue(any("none before it" in n for n in out["notes"]))

    def test_the_headline_names_the_biggest_fall(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "2026-08-30", "machine", [measured("disk.cache", 40)])
            audit(base, "2026-09-20", "machine", [measured("disk.cache", 12)])
            self.assertIn("disk.cache", run(root)["headline"])


    def test_an_audit_of_another_theme_is_not_read_into_this_report(self):
        """One folder holds both themes, so a report that takes every file tells the wrong story."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "2026-08-30", "recovery", [measured("backup.stale", 4)])
            audit(base, "2026-09-20", "recovery", [measured("backup.stale", 1)])
            out = run(root)
            self.assertEqual(out["movement"], [])
            self.assertTrue(any("another theme" in n for n in out["notes"]))

    def test_a_row_with_a_verdict_is_not_still_open(self):
        """A settled action in the open table becomes a next step nobody has to take again."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W37-01", "disk.cache", status="verify")],
                outcomes=["| 2026-W37-01 | disk.cache | ~/x | 2026-09-08 | 10 GB | 2 GB | won |"])
            out = run(root)
            self.assertEqual(out["counts"]["won"], 1)
            self.assertEqual(out["open"], [])


class WriteTest(unittest.TestCase):
    def test_the_written_report_holds_no_placeholder(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "2026-08-30", "machine", [measured("disk.cache", 40)])
            audit(base, "2026-09-20", "machine", [measured("disk.cache", 12)])
            log(base, actions=[action("2026-W37-01", "disk.cache", status="won")])
            out = run(root, extra=["--write"])
            path = Path(out["written"])
            self.assertTrue(path.is_file())
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("{{", text)
            self.assertIn("2026-W37-01", text)
            self.assertIn("disk.cache", text)

    def test_a_month_with_nothing_in_it_still_writes_a_report(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            out = run(root, extra=["--write"])
            text = Path(out["written"]).read_text(encoding="utf-8")
            self.assertNotIn("{{", text)
            self.assertIn("Nothing was logged this month", text)

    def test_a_machine_name_that_is_a_path_is_refused(self):
        """Every write stays inside --root, so a name with a slash never becomes one."""
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "../etc",
                                "--month", MONTH], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)

    def test_a_workspace_that_is_not_there_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(Path(d) / "nope"),
                                "--month", MONTH], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("no workspace", r.stdout)


    def test_the_last_line_names_the_file_once_it_was_written(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), MACHINE,
                                "--month", MONTH, "--write"], capture_output=True, text=True)
            self.assertIn(MONTH + ".md", r.stdout.rsplit("next", 1)[-1])


class ConsoleTest(unittest.TestCase):
    def test_the_console_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W37-01", "disk.cache")])
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--month", MONTH],
                               capture_output=True, text=True)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            log(base, actions=[action("2026-W37-01", "disk.cache")])
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--month", MONTH],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)

    def test_the_month_defaults_to_the_one_that_ended(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--today",
                                "2026-10-03"], capture_output=True, text=True)
            self.assertIn("2026-09", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
