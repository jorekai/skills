#!/usr/bin/env python3
"""Offline tests for grade.py: the arithmetic of a verdict, and the rows it refuses to grade.

Run: python3 skills/stack/grade/scripts/test_grade.py
Writes into a temp folder; no network, and no repository is read.
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
SLUG = "example-repo"
ACTIONS = ("| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |\n"
           "|---|---|---|---|---|---|---|---|---|---|\n")
OUTCOMES = ("| id | Check | Target | Applied | Then | Now | Verdict |\n"
            "|---|---|---|---|---|---|---|\n")


def workspace(root, rows, audits, slug=SLUG):
    """A workspace holding one log file and the audits a verdict is measured from."""
    base = Path(root) / "repos" / slug
    (base / "log" / "stack").mkdir(parents=True)
    (base / "audits").mkdir(parents=True)
    (base / "config.md").write_text("- role: stack\n", encoding="utf-8")
    lines = "".join("| " + " | ".join(r) + " |\n" for r in rows)
    (base / "log" / "stack" / "2026-W37.md").write_text(
        "# 2026-W37\n\n## Outcomes of earlier actions\n\n" + OUTCOMES +
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
    return subprocess.run([sys.executable, SCRIPT, "--root", str(root), SLUG,
                           "--today", "2026-09-20", *args], capture_output=True, text=True)


class VerdictTest(unittest.TestCase):
    """The four verdicts follow from two numbers, so every case here is arithmetic."""

    def test_a_cost_that_fell_past_the_tolerance_won(self):
        self.assertEqual(grade.verdict_for(100.0, 10.0, "seconds"), "won")

    def test_a_cost_that_reached_zero_won(self):
        self.assertEqual(grade.verdict_for(4.0, 0.0, "count"), "won")

    def test_a_count_compares_exactly_because_it_does_not_drift(self):
        self.assertEqual(grade.verdict_for(2.0, 1.0, "count"), "won")
        self.assertEqual(grade.verdict_for(2.0, 3.0, "count"), "returned")
        self.assertEqual(grade.verdict_for(2.0, 2.0, "count"), "no-change")

    def test_percent_and_seconds_allow_five_percent_of_the_starting_value(self):
        """A coverage shortfall and a gate time move under a tree that is being worked on."""
        self.assertEqual(grade.verdict_for(10.0, 10.4, "percent"), "no-change")
        self.assertEqual(grade.verdict_for(10.0, 9.6, "percent"), "no-change")
        self.assertEqual(grade.verdict_for(10.0, 9.0, "percent"), "won")
        self.assertEqual(grade.verdict_for(30.0, 32.0, "seconds"), "returned")
        self.assertEqual(grade.verdict_for(30.0, 20.0, "seconds"), "won")

    def test_a_row_that_started_at_zero_can_only_stay_or_return(self):
        self.assertEqual(grade.verdict_for(0.0, 0.0, "count"), "no-change")
        self.assertEqual(grade.verdict_for(0.0, 3.0, "count"), "returned")


class TargetTest(unittest.TestCase):
    def test_a_null_total_keeps_the_row_open(self):
        """A measure nobody took is not zero: the gate has to run before the row can settle."""
        it = item("guard.coverage", 0, "percent")
        it["measure"]["value"] = None
        value, _, note = grade.measure_now(it, "")
        self.assertIsNone(value)
        self.assertIn("was not taken", note)

    def test_a_null_target_keeps_the_row_open_while_another_target_grades(self):
        it = item("escape.type", 1, "count", {"a.ts:3": None, "b.ts:9": 1})
        self.assertIsNone(grade.measure_now(it, "a.ts:3")[0])
        self.assertEqual(grade.measure_now(it, "b.ts:9")[0], 1)

    def test_a_row_with_a_target_is_graded_against_that_target(self):
        it = item("escape.type", 3, "count", {"a.ts:3": 2, "b.ts:9": 1})
        self.assertEqual(grade.measure_now(it, "b.ts:9")[0], 1)

    def test_a_row_without_a_target_is_graded_against_the_total(self):
        it = item("escape.type", 3, "count", {"a.ts:3": 2, "b.ts:9": 1})
        self.assertEqual(grade.measure_now(it, "")[0], 3)

    def test_a_target_the_finding_no_longer_names_costs_nothing(self):
        value, _, note = grade.measure_now(item("escape.type", 2, "count", {"a.ts:3": 2}), "b.ts:9")
        self.assertEqual(value, 0)
        self.assertIn("no longer appears", note)

    def test_a_check_that_passes_costs_nothing_for_every_target(self):
        value, _, note = grade.measure_now(item("escape.type", 0, "count", {}, level="PASS"), "b.ts:9")
        self.assertEqual(value, 0)
        self.assertEqual(note, "")


class OwnershipTest(unittest.TestCase):
    """Every namespace this theme owns names the tool that recomputes it, and no other."""

    def test_every_namespace_names_the_tool_that_measures_it(self):
        for cid, tool in (("decl.absent", "drift"), ("boundary.cycle", "drift"),
                          ("adapter.missing", "drift"), ("lock.runtime", "drift"),
                          ("escape.type", "guards"), ("guard.slow", "guards"),
                          ("dead.dep", "guards")):
            self.assertEqual(grade.tool_for(cid), tool)

    def test_a_namespace_another_theme_owns_is_disowned_rather_than_guessed_at(self):
        """`cred` belongs to security, `repo` to dx and `secret` to ops; nothing here recomputes them."""
        for cid in ("cred.tracked", "repo.no-ci", "secret.in-repo"):
            got = grade.grade_row({"id": "x", "check": cid, "target": "",
                                   "then": "1 count", "applied": "2026-09-05"}, {})
            self.assertIn("no tool owns", got["note"])

    def test_namespaces_prints_one_namespace_and_tool_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--namespaces"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, grade.TOOL_OF)
        self.assertEqual(len(pairs), 7)


class EndToEndTest(unittest.TestCase):
    def test_a_due_row_gets_a_verdict_from_the_newest_audit_of_its_tool(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "escape.type", "a.ts:3", "3 count")],
                      {"2026-09-15-guards.json": audit("guards", item("escape.type", 0, "count", {})),
                       "2026-09-10-guards.json": audit("guards", item("escape.type", 3, "count", {"a.ts:3": 3}))})
            got = run(d)
            self.assertIn("won", got.stdout)
            self.assertIn("2026-09-15-guards.json", got.stdout)

    def test_a_coverage_row_is_graded_in_percent_with_the_tolerance(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "guard.coverage", "", "10 percent")],
                      {"2026-09-15-guards.json": audit("guards", item("guard.coverage", 10.3, "percent"))})
            self.assertIn("no-change", run(d).stdout)

    def test_a_slow_gate_row_is_graded_in_seconds(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "guard.slow", "", "30 seconds")],
                      {"2026-09-15-guards.json": audit("guards", item("guard.slow", 12, "seconds"))})
            self.assertIn("won", run(d).stdout)

    def test_a_null_measure_keeps_the_row_open_and_names_the_gate(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "dead.export", "", "3 count")],
                      {"2026-09-15-guards.json": audit("guards", item("dead.export", None, "count"))})
            got = run(d)
            self.assertIn("open", got.stdout)
            self.assertIn("carries no measure", got.stdout)

    def test_an_audit_older_than_the_action_grades_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "boundary.crossed", "", "2 count")],
                      {"2026-09-01-drift.json": audit("drift", item("boundary.crossed", 0, "count"))})
            got = run(d)
            self.assertIn("open", got.stdout)
            self.assertIn("older than the action", got.stdout)

    def test_a_check_missing_from_the_audit_grades_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "boundary.cycle", "", "2 count")],
                      {"2026-09-15-drift.json": audit("drift", item("boundary.crossed", 0, "count"))})
            got = run(d)
            self.assertIn("open", got.stdout)
            self.assertIn("same flags", got.stdout)

    def test_no_audit_of_that_tool_names_the_tool_to_run(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "lock.incomplete", "", "1 count")], {})
            self.assertIn("no drift audit", run(d).stdout)

    def test_two_units_of_different_families_do_not_compare(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "guard.slow", "", "4 count")],
                      {"2026-09-15-guards.json": audit("guards", item("guard.slow", 4, "seconds"))})
            self.assertIn("do not compare", run(d).stdout)

    def test_a_row_that_is_not_due_yet_is_left_alone_until_only_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "escape.type", "", "3 count", after="2026-12-01")],
                      {"2026-09-15-guards.json": audit("guards", item("escape.type", 0, "count"))})
            self.assertIn("nothing due", run(d).stdout)
            self.assertIn("won", run(d, "--only", "2026-W37-01").stdout)

    def test_a_row_that_was_never_applied_is_never_graded(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "escape.type", "", "3 count", status="todo")],
                      {"2026-09-15-guards.json": audit("guards", item("escape.type", 0, "count"))})
            self.assertIn("nothing due", run(d, "--only", "2026-W37-01").stdout)

    def test_write_adds_an_outcome_row_and_closes_the_action_row(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W37-01", "escape.type", "", "3 count")],
                             {"2026-09-15-guards.json": audit("guards", item("escape.type", 0, "count"))})
            run(d, "--write")
            text = (base / "log" / "stack" / "2026-W37.md").read_text(encoding="utf-8")
            outcomes, actions = text.split("## Actions")
            self.assertIn("| 2026-W37-01 | escape.type |  | 2026-09-05 | 3 count | 0 count | won |", outcomes)
            self.assertIn("| won |", actions)
            self.assertIn("| now 0 count |", actions)
            # The row is closed, so the same verdict is never written twice.
            self.assertIn("nothing due", run(d).stdout)

    def test_write_leaves_a_row_it_could_not_grade_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W37-01", "escape.type", "", "a lot")],
                             {"2026-09-15-guards.json": audit("guards", item("escape.type", 0, "count"))})
            before = (base / "log" / "stack" / "2026-W37.md").read_text(encoding="utf-8")
            got = run(d, "--write")
            self.assertIn("needs a person", got.stdout)
            self.assertEqual(before, (base / "log" / "stack" / "2026-W37.md").read_text(encoding="utf-8"))

    def test_a_pipe_in_a_target_stays_inside_its_cell(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [["2026-W37-01", "boundary.crossed", "packages/ui \\| 12", "do the thing",
                                  "ask", "2 count", "applied", "2026-09-05", "2026-09-12", ""]],
                             {"2026-09-15-drift.json": audit(
                                 "drift", item("boundary.crossed", 1, "count", {"packages/ui | 12": 1}))})
            run(d, "--write")
            text = (base / "log" / "stack" / "2026-W37.md").read_text(encoding="utf-8")
            self.assertIn("| 2026-W37-01 | boundary.crossed | packages/ui \\| 12 | 2026-09-05 "
                          "| 2 count | 1 count | won |", text)

    def test_a_repository_name_that_is_a_path_is_rejected(self):
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
            self.assertIn("jorekai-stack:setup", r.stdout)

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "escape.type", "", "3 count")],
                      {"2026-09-15-guards.json": audit("guards", item("escape.type", 0, "count"))})
            self.assertNotIn("\033[", run(d).stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "escape.type", "", "3 count")],
                      {"2026-09-15-guards.json": audit("guards", item("escape.type", 0, "count"))})
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, SLUG, "--today", "2026-09-20"],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


class UnreadableRowTest(unittest.TestCase):
    """A row nobody can parse is graded as ungradable, never silently dropped (decisions/0030)."""

    def test_a_malformed_row_is_listed_as_ungradable_with_its_file_and_line(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W37-01", "decl.absent", "", "3 count")],
                             {"2026-09-15-drift.json": audit("drift", item("decl.absent", 0, "count"))})
            p = base / "log" / "stack" / "2026-W37.md"
            p.write_text(p.read_text(encoding="utf-8") + "| broken row too few cells |\n",
                        encoding="utf-8")
            got = run(d)
            self.assertIn("ungradable", got.stdout)
            self.assertIn("cells against a header of", got.stdout)

    def test_a_row_with_an_invalid_verify_after_is_listed_as_ungradable(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "decl.absent", "", "3 count", after="not-a-date")], {})
            got = run(d)
            self.assertIn("ungradable", got.stdout)
            self.assertIn("not-a-date", got.stdout)

    def test_the_json_output_carries_the_ungradable_rows(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W37-01", "decl.absent", "", "3 count", after="not-a-date")], {})
            out = json.loads(run(d, "--json").stdout)
            graded = out["repos"][SLUG]["graded"]
            self.assertTrue(any(g["note"].startswith("ungradable") for g in graded), graded)
            self.assertTrue(any("line" in g for g in graded), graded)


class ReportShapeTest(unittest.TestCase):
    """The console report says what can be settled and what still needs a person."""

    def report(self):
        graded = [{"id": "2026-W37-01", "check": "escape.type", "target": "a.ts:3",
                   "applied": "2026-09-01", "then": "3 count", "now": "0 count", "verdict": "won",
                   "note": "", "audit": "2026-09-15-guards.json"},
                  {"id": "2026-W37-02", "check": "lock.runtime", "target": "", "applied": "",
                   "then": "1 count", "now": "", "verdict": "",
                   "note": "no drift audit in the workspace", "audit": ""}]
        return grade.report(SLUG, graded, dt.date(2026, 9, 16))

    def test_the_header_says_which_repository_and_which_day(self):
        self.assertIn(f"grade  {SLUG}  2026-09-16", self.report())

    def test_the_counting_line_is_a_bar_of_the_four_verdicts(self):
        self.assertIn("2 due · 1 won · 0 returned · 0 no-change", self.report())

    def test_a_row_is_one_line_of_verdict_row_id_check_id_then_and_now(self):
        text = self.report()
        self.assertRegex(text, r"\nwon {9}2026-W37-01  escape\.type {19}3 count  0 count\n")
        self.assertRegex(text, r"\nopen {8}2026-W37-02  lock\.runtime {18}1 count  -\n")
        self.assertNotIn("->", text)

    def test_nothing_due_says_why_there_is_nothing(self):
        self.assertIn("nothing due, no log row has reached its verify date",
                      grade.report(SLUG, [], dt.date(2026, 9, 16)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
