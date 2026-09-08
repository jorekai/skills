#!/usr/bin/env python3
"""Offline tests for grade.py: the arithmetic of a verdict, and the rows it refuses to grade.

Run: python3 skills/ops/grade/scripts/test_grade.py
Writes into a temp folder; no network, no host access.
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
HOST = "example-host"
ACTIONS = ("| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |\n"
           "|---|---|---|---|---|---|---|---|---|---|\n")
OUTCOMES = ("| id | Check | Target | Applied | Then | Now | Verdict |\n"
            "|---|---|---|---|---|---|---|\n")


def workspace(root, rows, audits, host=HOST):
    """A workspace holding one log file and the audits a verdict is measured from."""
    base = Path(root) / "machines" / host
    (base / "log" / "ops").mkdir(parents=True)
    (base / "audits").mkdir(parents=True)
    (base / "config.md").write_text("- role: server\n", encoding="utf-8")
    lines = "".join("| " + " | ".join(r) + " |\n" for r in rows)
    (base / "log" / "ops" / "2026-W36.md").write_text(
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
    return [rid, check, target, "do the thing", "ask", then, status, applied, after, ""]


def run(root, *args):
    return subprocess.run([sys.executable, SCRIPT, "--root", str(root), HOST,
                           "--today", "2026-09-20", *args], capture_output=True, text=True)


class VerdictTest(unittest.TestCase):
    """The four verdicts follow from two numbers, so every case here is arithmetic."""

    def test_a_cost_that_fell_past_the_tolerance_won(self):
        self.assertEqual(grade.verdict_for(100.0, 10.0, "bytes"), "won")

    def test_a_cost_that_reached_zero_won(self):
        self.assertEqual(grade.verdict_for(4.0, 0.0, "count"), "won")

    def test_a_count_compares_exactly_because_it_does_not_drift(self):
        self.assertEqual(grade.verdict_for(2.0, 1.0, "count"), "won")
        self.assertEqual(grade.verdict_for(2.0, 3.0, "count"), "returned")
        self.assertEqual(grade.verdict_for(2.0, 2.0, "count"), "no-change")

    def test_a_row_that_started_at_zero_can_only_stay_or_return(self):
        self.assertEqual(grade.verdict_for(0.0, 0.0, "count"), "no-change")
        self.assertEqual(grade.verdict_for(0.0, 3.0, "count"), "returned")


class TargetTest(unittest.TestCase):
    def test_a_row_with_a_target_is_graded_against_that_target(self):
        it = item("key.orphan", 3, "count", {"root": 2, "deploy": 1})
        self.assertEqual(grade.measure_now(it, "deploy")[0], 1)

    def test_a_row_without_a_target_is_graded_against_the_total(self):
        it = item("key.orphan", 3, "count", {"root": 2, "deploy": 1})
        self.assertEqual(grade.measure_now(it, "")[0], 3)

    def test_a_target_the_finding_no_longer_names_costs_nothing(self):
        """The whole point of the check id: the key left the finding, so the action held."""
        value, _, note = grade.measure_now(item("key.orphan", 2, "count", {"root": 2}), "deploy")
        self.assertEqual(value, 0)
        self.assertIn("no longer appears", note)

    def test_a_check_that_passes_costs_nothing_for_every_target(self):
        """A passing check names no target, and that silence is the answer, not a missing number."""
        value, _, note = grade.measure_now(item("key.orphan", 0, "count", {}, level="PASS"), "deploy")
        self.assertEqual(value, 0)
        self.assertEqual(note, "")


class OwnershipTest(unittest.TestCase):
    """Every namespace this theme owns is either measured today or named as waiting."""

    def test_a_shipped_namespace_names_the_tool_that_measures_it(self):
        self.assertEqual(grade.tool_for("ssh.password-auth"), "access")
        self.assertEqual(grade.tool_for("timer.missed"), "availability")
        self.assertEqual(grade.tool_for("tls.expiring"), "exposure")
        self.assertEqual(grade.tool_for("backup.stale"), "recovery")

    def test_a_planned_namespace_waits_for_its_tool_instead_of_being_disowned(self):
        got = grade.grade_row({"id": "x", "check": "pkg.security", "target": "",
                               "then": "1 count", "applied": "2026-09-05"}, {})
        self.assertEqual(got["verdict"], "")
        self.assertIn("waits for its tool", got["note"])

    def test_a_namespace_no_theme_owns_is_disowned(self):
        got = grade.grade_row({"id": "x", "check": "disk.cache", "target": "",
                               "then": "1 count", "applied": "2026-09-05"}, {})
        self.assertIn("no tool owns", got["note"])

    def test_namespaces_prints_one_namespace_and_tool_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--namespaces"], capture_output=True, text=True)
        self.assertEqual(dict(line.split() for line in r.stdout.splitlines() if line.strip()),
                         grade.TOOL_OF)


class EndToEndTest(unittest.TestCase):
    def test_a_due_row_gets_a_verdict_from_the_newest_audit_of_its_tool(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "key.orphan", "deploy", "3 count")],
                      {"2026-09-15-access.json": audit("access", item("key.orphan", 0, "count", {})),
                       "2026-09-10-access.json": audit("access", item("key.orphan", 3, "count", {"deploy": 3}))})
            got = run(d)
            self.assertIn("verdict won", got.stdout)
            self.assertIn("2026-09-15-access.json", got.stdout)

    def test_an_audit_older_than_the_action_grades_nothing(self):
        """A measure taken before the action says nothing about whether the action held."""
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "ssh.password-auth", "", "2 count")],
                      {"2026-09-01-access.json": audit("access", item("ssh.password-auth", 0, "count"))})
            got = run(d)
            self.assertIn("no verdict", got.stdout)
            self.assertIn("older than the action", got.stdout)

    def test_a_check_missing_from_the_audit_grades_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "user.unlisted", "", "2 count")],
                      {"2026-09-15-access.json": audit("access", item("key.orphan", 0, "count"))})
            got = run(d)
            self.assertIn("no verdict", got.stdout)
            self.assertIn("same flags", got.stdout)

    def test_no_audit_of_that_tool_names_the_tool_to_run(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "service.down", "", "1 count")], {})
            self.assertIn("no availability audit", run(d).stdout)

    def test_two_units_of_different_families_do_not_compare(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "key.orphan", "", "40 GB")],
                      {"2026-09-15-access.json": audit("access", item("key.orphan", 4, "count"))})
            self.assertIn("do not compare", run(d).stdout)

    def test_a_row_that_is_not_due_yet_is_left_alone_until_only_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "key.orphan", "", "3 count", after="2026-12-01")],
                      {"2026-09-15-access.json": audit("access", item("key.orphan", 0, "count"))})
            self.assertIn("nothing due", run(d).stdout)
            self.assertIn("verdict won", run(d, "--only", "2026-W36-01").stdout)

    def test_a_row_that_was_never_applied_is_never_graded(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "key.orphan", "", "3 count", status="todo")],
                      {"2026-09-15-access.json": audit("access", item("key.orphan", 0, "count"))})
            self.assertIn("nothing due", run(d, "--only", "2026-W36-01").stdout)

    def test_write_adds_an_outcome_row_and_closes_the_action_row(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W36-01", "key.orphan", "", "3 count")],
                             {"2026-09-15-access.json": audit("access", item("key.orphan", 0, "count"))})
            run(d, "--write")
            text = (base / "log" / "ops" / "2026-W36.md").read_text(encoding="utf-8")
            outcomes, actions = text.split("## Actions")
            self.assertIn("| 2026-W36-01 | key.orphan |  | 2026-09-05 | 3 count | 0 count | won |", outcomes)
            self.assertIn("| won |", actions)
            self.assertIn("| now 0 count |", actions)
            # The row is closed, so the same verdict is never written twice.
            self.assertIn("nothing due", run(d).stdout)

    def test_write_leaves_a_row_it_could_not_grade_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W36-01", "key.orphan", "", "a lot")],
                             {"2026-09-15-access.json": audit("access", item("key.orphan", 0, "count"))})
            before = (base / "log" / "ops" / "2026-W36.md").read_text(encoding="utf-8")
            got = run(d, "--write")
            self.assertIn("needs a person", got.stdout)
            self.assertEqual(before, (base / "log" / "ops" / "2026-W36.md").read_text(encoding="utf-8"))

    def test_a_pipe_in_a_target_stays_inside_its_cell(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [["2026-W36-01", "sudo.nopasswd", "ops-admin \\| 12", "do the thing",
                                  "ask", "2 count", "applied", "2026-09-05", "2026-09-12", ""]],
                             {"2026-09-15-access.json": audit(
                                 "access", item("sudo.nopasswd", 1, "count", {"ops-admin | 12": 1}))})
            run(d, "--write")
            text = (base / "log" / "ops" / "2026-W36.md").read_text(encoding="utf-8")
            self.assertIn("| 2026-W36-01 | sudo.nopasswd | ops-admin \\| 12 | 2026-09-05 "
                          "| 2 count | 1 count | won |", text)

    def test_a_host_name_that_is_a_path_is_rejected(self):
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
            self.assertIn("jorekai-ops:setup", r.stdout)


class ReportShapeTest(unittest.TestCase):
    """The console report says what can be settled and what still needs a person."""

    def report(self):
        graded = [{"id": "2026-W36-01", "check": "key.orphan", "target": "deploy",
                   "applied": "2026-09-01", "then": "3 count", "now": "0 count", "verdict": "won",
                   "note": "", "audit": "2026-09-15-access.json"},
                  {"id": "2026-W36-02", "check": "tls.expired", "target": "", "applied": "",
                   "then": "1 count", "now": "", "verdict": "",
                   "note": "tls.expired waits for its tool", "audit": ""}]
        return grade.report(HOST, graded, dt.date(2026, 9, 16))

    def test_the_header_says_which_host_and_which_day(self):
        self.assertIn(f"grade  {HOST}  2026-09-16", self.report())

    def test_the_counting_line_separates_settled_rows_from_the_rest(self):
        self.assertIn("1 of 2 rows due can be settled, 1 needs a person", self.report())

    def test_a_verdict_is_printed_with_the_reason_behind_it(self):
        self.assertIn("verdict won: the cost fell or reached zero", self.report())

    def test_nothing_due_says_why_there_is_nothing(self):
        self.assertIn("nothing due, no log row has reached its verify date",
                      grade.report(HOST, [], dt.date(2026, 9, 16)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
