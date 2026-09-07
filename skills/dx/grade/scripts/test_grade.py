#!/usr/bin/env python3
"""Offline tests for grade.py: the arithmetic of a verdict, and the rows it refuses to grade.

Run: python3 skills/dx/grade/scripts/test_grade.py
Writes into a temp folder; no network, no machine access.
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
import grade  # noqa: E402

SCRIPT = os.path.abspath(grade.__file__)
ACTIONS = ("| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |\n"
           "|---|---|---|---|---|---|---|---|---|---|\n")
OUTCOMES = ("| id | Check | Target | Applied | Then | Now | Verdict |\n"
            "|---|---|---|---|---|---|---|\n")


def workspace(root, rows, audits, machine="example-machine"):
    """A workspace holding one log file and the audits a verdict is measured from."""
    base = Path(root) / "machines" / machine
    (base / "log" / "dx").mkdir(parents=True)
    (base / "audits").mkdir(parents=True)
    (base / "config.md").write_text("- project_roots: ~/dev\n", encoding="utf-8")
    lines = "".join("| " + " | ".join(r) + " |\n" for r in rows)
    (base / "log" / "dx" / "2026-W36.md").write_text(
        "# 2026-W36\n\n## Outcomes of earlier actions\n\n" + OUTCOMES +
        "\n## Actions\n\n" + ACTIONS + lines, encoding="utf-8")
    for name, data in audits.items():
        (base / "audits" / name).write_text(json.dumps(data), encoding="utf-8")
    return base


def item(cid, value, unit, by=None, level="WARN"):
    return {"id": cid, "level": level, "message": "m", "data": [],
            "measure": None if value is None else {"value": value, "unit": unit, "by": by or {}}}


def audit(tool, *items):
    return {"tool": tool, "target": "t", "counts": {}, "items": list(items)}


def row(rid, check, target, then, status="applied", applied="2026-09-05", after="2026-09-12"):
    return [rid, check, target, "do the thing", "safe", then, status, applied, after, ""]


def run(root, *args):
    r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine",
                        "--today", "2026-09-20", *args], capture_output=True, text=True)
    return r


class VerdictTest(unittest.TestCase):
    """The four verdicts follow from two numbers, so every case here is arithmetic."""

    def test_a_cost_that_fell_past_the_tolerance_won(self):
        self.assertEqual(grade.verdict_for(100.0, 10.0, "bytes"), "won")

    def test_a_cost_that_reached_zero_won(self):
        self.assertEqual(grade.verdict_for(4.0, 0.0, "count"), "won")

    def test_a_move_inside_five_percent_of_a_continuous_measure_is_no_change(self):
        self.assertEqual(grade.verdict_for(100.0, 103.0, "bytes"), "no-change")
        self.assertEqual(grade.verdict_for(100.0, 97.0, "bytes"), "no-change")

    def test_a_count_compares_exactly_because_it_does_not_drift(self):
        self.assertEqual(grade.verdict_for(20.0, 19.0, "count"), "won")
        self.assertEqual(grade.verdict_for(20.0, 21.0, "count"), "returned")
        self.assertEqual(grade.verdict_for(20.0, 20.0, "count"), "no-change")

    def test_a_cost_that_rose_past_the_tolerance_returned(self):
        self.assertEqual(grade.verdict_for(100.0, 200.0, "bytes"), "returned")

    def test_a_row_that_started_at_zero_can_only_stay_or_return(self):
        self.assertEqual(grade.verdict_for(0.0, 0.0, "count"), "no-change")
        self.assertEqual(grade.verdict_for(0.0, 3.0, "count"), "returned")


class MeasureTest(unittest.TestCase):
    def test_units_of_one_family_compare_after_conversion(self):
        self.assertEqual(grade.base(*grade.parse_measure("1 GB")), ("bytes", 1024 ** 3))
        self.assertEqual(grade.base(*grade.parse_measure("1024 MB")), ("bytes", 1024 ** 3))

    def test_a_unit_outside_the_closed_set_is_not_a_measure(self):
        for bad in ("41 gigs", "a lot", "", "GB", "12", "12 %"):
            with self.subTest(bad=bad):
                self.assertIsNone(grade.parse_measure(bad))

    def test_a_measure_reads_back_in_the_unit_the_row_was_written_in(self):
        self.assertEqual(grade.show(4 * 1024 ** 3, "GB"), "4 GB")

    def test_namespaces_prints_one_namespace_and_tool_per_line(self):
        """scripts/check.sh reads this against the fixes table, so the two must not drift."""
        r = subprocess.run([sys.executable, SCRIPT, "--namespaces"], capture_output=True, text=True)
        self.assertEqual(dict(line.split() for line in r.stdout.splitlines() if line.strip()),
                         grade.TOOL_OF)

    def test_a_target_matches_whether_or_not_the_home_folder_is_spelled_out(self):
        self.assertTrue(grade.same_target("~/dev/foo", str(Path.home() / "dev/foo")))
        self.assertFalse(grade.same_target("~/dev/foo", "~/dev/bar"))


class TargetTest(unittest.TestCase):
    def test_a_row_with_a_target_is_graded_against_that_target(self):
        it = item("git.dirty", 3, "count", {"/a": 12, "/b": 40})
        self.assertEqual(grade.measure_now(it, "/b")[0], 40)

    def test_a_row_without_a_target_is_graded_against_the_total(self):
        it = item("git.dirty", 3, "count", {"/a": 12, "/b": 40})
        self.assertEqual(grade.measure_now(it, "")[0], 3)

    def test_a_target_the_finding_no_longer_names_costs_nothing(self):
        """The whole point of the check id: the target left the finding, so the action held."""
        value, _, note = grade.measure_now(item("git.dirty", 3, "count", {"/a": 12}), "/b")
        self.assertEqual(value, 0)
        self.assertIn("no longer appears", note)

    def test_a_check_that_passes_costs_nothing_for_every_target(self):
        """A passing check names no target, and that silence is the answer, not a missing number."""
        value, _, note = grade.measure_now(item("git.dirty", 0, "count", {}, level="PASS"), "/b")
        self.assertEqual(value, 0)
        self.assertEqual(note, "")

    def test_a_finding_without_a_measure_is_not_graded(self):
        value, _, note = grade.measure_now(item("git.dirty", None, "count"), "/b")
        self.assertIsNone(value)
        self.assertIn("no measure", note)


class EndToEndTest(unittest.TestCase):
    def test_a_due_row_gets_a_verdict_from_the_newest_audit_of_its_tool(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "disk.cache", "/tmp/cache", "40 GB")],
                      {"2026-09-15-machine.json": audit("machine", item("disk.cache", 0, "bytes", {"/tmp/cache": 0})),
                       "2026-09-10-machine.json": audit("machine", item("disk.cache", 40 * 1024 ** 3, "bytes"))})
            got = run(d)
            self.assertIn("verdict won", got.stdout)
            self.assertIn("2026-09-15-machine.json", got.stdout)

    def test_an_audit_older_than_the_action_grades_nothing(self):
        """A measure taken before the action says nothing about whether the action held."""
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "disk.cache", "", "40 GB")],
                      {"2026-09-01-machine.json": audit("machine", item("disk.cache", 0, "bytes"))})
            got = run(d)
            self.assertIn("no verdict", got.stdout)
            self.assertIn("older than the action", got.stdout)

    def test_a_check_missing_from_the_audit_grades_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "git.identity", "", "2 count")],
                      {"2026-09-15-repos.json": audit("repos", item("git.dirty", 0, "count"))})
            got = run(d)
            self.assertIn("no verdict", got.stdout)
            self.assertIn("same flags", got.stdout)

    def test_no_audit_of_that_tool_names_the_skill_to_run(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "friction.slow-command", "", "600 seconds")], {})
            got = run(d)
            self.assertIn("no friction audit", got.stdout)

    def test_two_units_of_different_families_do_not_compare(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "disk.cache", "", "40 GB")],
                      {"2026-09-15-machine.json": audit("machine", item("disk.cache", 4, "count"))})
            got = run(d)
            self.assertIn("do not compare", got.stdout)

    def test_a_row_that_is_not_due_yet_is_left_alone_until_only_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "disk.cache", "", "40 GB", after="2026-12-01")],
                      {"2026-09-15-machine.json": audit("machine", item("disk.cache", 0, "bytes"))})
            self.assertIn("nothing due", run(d).stdout)
            self.assertIn("verdict won", run(d, "--only", "2026-W36-01").stdout)

    def test_a_row_that_was_never_applied_is_never_graded(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "disk.cache", "", "40 GB", status="todo")],
                      {"2026-09-15-machine.json": audit("machine", item("disk.cache", 0, "bytes"))})
            self.assertIn("nothing due", run(d, "--only", "2026-W36-01").stdout)

    def test_write_adds_an_outcome_row_and_closes_the_action_row(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W36-01", "disk.cache", "", "40 GB")],
                             {"2026-09-15-machine.json": audit("machine", item("disk.cache", 0, "bytes"))})
            run(d, "--write")
            text = (base / "log" / "dx" / "2026-W36.md").read_text(encoding="utf-8")
            outcomes, actions = text.split("## Actions")
            self.assertIn("| 2026-W36-01 | disk.cache |  | 2026-09-05 | 40 GB | 0 GB | won |", outcomes)
            self.assertIn("| won |", actions)
            self.assertIn("| now 0 GB |", actions)
            # The row is closed, so the same verdict is never written twice.
            self.assertIn("nothing due", run(d).stdout)

    def test_write_leaves_a_row_it_could_not_grade_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W36-01", "disk.cache", "", "a lot")],
                             {"2026-09-15-machine.json": audit("machine", item("disk.cache", 0, "bytes"))})
            before = (base / "log" / "dx" / "2026-W36.md").read_text(encoding="utf-8")
            got = run(d, "--write")
            self.assertIn("needs a person", got.stdout)
            self.assertEqual(before, (base / "log" / "dx" / "2026-W36.md").read_text(encoding="utf-8"))

    def test_a_pipe_in_a_target_stays_inside_its_cell(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [["2026-W36-01", "friction.slow-command", "build \\| test", "do the thing",
                                  "safe", "600 seconds", "applied", "2026-09-05", "2026-09-12", ""]],
                             {"2026-09-15-friction.json": audit(
                                 "friction", item("friction.slow-command", 60, "seconds", {"build | test": 60}))})
            run(d, "--write")
            text = (base / "log" / "dx" / "2026-W36.md").read_text(encoding="utf-8")
            self.assertIn("| 2026-W36-01 | friction.slow-command | build \\| test | 2026-09-05 "
                          "| 600 seconds | 60 seconds | won |", text)

    def test_a_machine_name_that_is_a_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [], {})
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "../escaped"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

    def test_a_workspace_that_does_not_exist_says_which_skill_makes_one(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", os.path.join(d, "nothing")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("jorekai-dx:setup", r.stdout)


class ReportShapeTest(unittest.TestCase):
    """The console report says what can be settled and what still needs a person."""

    def report(self):
        graded = [{"id": "2026-W36-01", "check": "disk.cache", "target": "/x/one",
                   "applied": "2026-09-01", "then": "40 GB", "now": "10 GB", "verdict": "won",
                   "note": "", "audit": "2026-09-15-machine.json"},
                  {"id": "2026-W36-02", "check": "auth.stale", "target": "", "applied": "",
                   "then": "1 count", "now": "", "verdict": "", "note": "no tool owns auth.stale",
                   "audit": ""}]
        return grade.report("test-machine", graded, dt.date(2026, 9, 16))

    def test_the_header_says_which_machine_and_which_day(self):
        self.assertIn("grade  test-machine  2026-09-16", self.report())

    def test_the_counting_line_separates_settled_rows_from_the_rest(self):
        self.assertIn("1 of 2 rows due can be settled, 1 needs a person", self.report())

    def test_a_verdict_is_printed_with_the_reason_behind_it(self):
        self.assertIn("verdict won: the cost fell or reached zero", self.report())

    def test_writing_the_verdicts_is_named_as_the_next_step(self):
        self.assertIn("next  run the same command with --write", self.report())

    def test_nothing_due_says_why_there_is_nothing(self):
        self.assertIn("nothing due, no log row has reached its verify date",
                      grade.report("test-machine", [], dt.date(2026, 9, 16)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
