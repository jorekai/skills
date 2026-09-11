#!/usr/bin/env python3
"""Offline tests for grade.py: the arithmetic of a verdict, and the rows it refuses to grade.

Run: python3 skills/security/grade/scripts/test_grade.py
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
    (base / "log" / "security").mkdir(parents=True)
    (base / "audits").mkdir(parents=True)
    (base / "config.md").write_text("- role: code\n", encoding="utf-8")
    lines = "".join("| " + " | ".join(r) + " |\n" for r in rows)
    (base / "log" / "security" / "2026-W36.md").write_text(
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
    return subprocess.run([sys.executable, SCRIPT, "--root", str(root), SLUG,
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
        it = item("cred.tracked", 3, "count", {"a.py": 2, "b.py": 1})
        self.assertEqual(grade.measure_now(it, "b.py")[0], 1)

    def test_a_row_without_a_target_is_graded_against_the_total(self):
        it = item("cred.tracked", 3, "count", {"a.py": 2, "b.py": 1})
        self.assertEqual(grade.measure_now(it, "")[0], 3)

    def test_a_target_the_finding_no_longer_names_costs_nothing(self):
        """The whole point of the check id: the file left the finding, so the action held."""
        value, _, note = grade.measure_now(item("cred.tracked", 2, "count", {"a.py": 2}), "b.py")
        self.assertEqual(value, 0)
        self.assertIn("no longer appears", note)

    def test_a_check_that_passes_costs_nothing_for_every_target(self):
        """A passing check names no target, and that silence is the answer, not a missing number."""
        value, _, note = grade.measure_now(item("cred.tracked", 0, "count", {}, level="PASS"), "b.py")
        self.assertEqual(value, 0)
        self.assertEqual(note, "")


class OwnershipTest(unittest.TestCase):
    """Every namespace this theme owns names the tool that recomputes it, and no other."""

    def test_every_namespace_names_the_tool_that_measures_it(self):
        self.assertEqual(grade.tool_for("cred.history"), "secrets")
        self.assertEqual(grade.tool_for("build.action-unpinned"), "pipeline")
        self.assertEqual(grade.tool_for("dep.known-exploited"), "deps")
        self.assertEqual(grade.tool_for("vuln.injection"), "review")

    def test_a_namespace_another_theme_owns_is_disowned_rather_than_guessed_at(self):
        """`secret` belongs to the ops theme and `repo` to dx; nothing here recomputes either."""
        for cid in ("secret.in-repo", "repo.secret-exposed"):
            got = grade.grade_row({"id": "x", "check": cid, "target": "",
                                   "then": "1 count", "applied": "2026-09-05"}, {})
            self.assertIn("no tool owns", got["note"])

    def test_namespaces_prints_one_namespace_and_tool_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--namespaces"], capture_output=True, text=True)
        self.assertEqual(dict(line.split() for line in r.stdout.splitlines() if line.strip()),
                         grade.TOOL_OF)


class EndToEndTest(unittest.TestCase):
    def test_a_due_row_gets_a_verdict_from_the_newest_audit_of_its_tool(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "cred.tracked", "a.py", "3 count")],
                      {"2026-09-15-secrets.json": audit("secrets", item("cred.tracked", 0, "count", {})),
                       "2026-09-10-secrets.json": audit("secrets", item("cred.tracked", 3, "count", {"a.py": 3}))})
            got = run(d)
            self.assertIn("won", got.stdout)
            self.assertIn("2026-09-15-secrets.json", got.stdout)

    def test_an_audit_older_than_the_action_grades_nothing(self):
        """A measure taken before the action says nothing about whether the action held."""
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "build.token-broad", "", "2 count")],
                      {"2026-09-01-pipeline.json": audit("pipeline", item("build.token-broad", 0, "count"))})
            got = run(d)
            self.assertIn("open", got.stdout)
            self.assertIn("older than the action", got.stdout)

    def test_a_check_missing_from_the_audit_grades_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "build.action-unpinned", "", "2 count")],
                      {"2026-09-15-pipeline.json": audit("pipeline", item("build.token-broad", 0, "count"))})
            got = run(d)
            self.assertIn("open", got.stdout)
            self.assertIn("same flags", got.stdout)

    def test_no_audit_of_that_tool_names_the_tool_to_run(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "dep.vulnerable", "", "1 count")], {})
            self.assertIn("no deps audit", run(d).stdout)

    def test_two_units_of_different_families_do_not_compare(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "cred.tracked", "", "40 GB")],
                      {"2026-09-15-secrets.json": audit("secrets", item("cred.tracked", 4, "count"))})
            self.assertIn("do not compare", run(d).stdout)

    def test_a_row_that_is_not_due_yet_is_left_alone_until_only_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "cred.tracked", "", "3 count", after="2026-12-01")],
                      {"2026-09-15-secrets.json": audit("secrets", item("cred.tracked", 0, "count"))})
            self.assertIn("nothing due", run(d).stdout)
            self.assertIn("won", run(d, "--only", "2026-W36-01").stdout)

    def test_a_row_that_was_never_applied_is_never_graded(self):
        with tempfile.TemporaryDirectory() as d:
            workspace(d, [row("2026-W36-01", "cred.tracked", "", "3 count", status="todo")],
                      {"2026-09-15-secrets.json": audit("secrets", item("cred.tracked", 0, "count"))})
            self.assertIn("nothing due", run(d, "--only", "2026-W36-01").stdout)

    def test_write_adds_an_outcome_row_and_closes_the_action_row(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W36-01", "cred.tracked", "", "3 count")],
                             {"2026-09-15-secrets.json": audit("secrets", item("cred.tracked", 0, "count"))})
            run(d, "--write")
            text = (base / "log" / "security" / "2026-W36.md").read_text(encoding="utf-8")
            outcomes, actions = text.split("## Actions")
            self.assertIn("| 2026-W36-01 | cred.tracked |  | 2026-09-05 | 3 count | 0 count | won |", outcomes)
            self.assertIn("| won |", actions)
            self.assertIn("| now 0 count |", actions)
            # The row is closed, so the same verdict is never written twice.
            self.assertIn("nothing due", run(d).stdout)

    def test_write_leaves_a_row_it_could_not_grade_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [row("2026-W36-01", "cred.tracked", "", "a lot")],
                             {"2026-09-15-secrets.json": audit("secrets", item("cred.tracked", 0, "count"))})
            before = (base / "log" / "security" / "2026-W36.md").read_text(encoding="utf-8")
            got = run(d, "--write")
            self.assertIn("needs a person", got.stdout)
            self.assertEqual(before, (base / "log" / "security" / "2026-W36.md").read_text(encoding="utf-8"))

    def test_a_pipe_in_a_target_stays_inside_its_cell(self):
        with tempfile.TemporaryDirectory() as d:
            base = workspace(d, [["2026-W36-01", "vuln.injection", "src/a.py \\| 12", "do the thing",
                                  "ask", "2 count", "applied", "2026-09-05", "2026-09-12", ""]],
                             {"2026-09-15-review.json": audit(
                                 "review", item("vuln.injection", 1, "count", {"src/a.py | 12": 1}))})
            run(d, "--write")
            text = (base / "log" / "security" / "2026-W36.md").read_text(encoding="utf-8")
            self.assertIn("| 2026-W36-01 | vuln.injection | src/a.py \\| 12 | 2026-09-05 "
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
            self.assertIn("jorekai-security:setup", r.stdout)


class ReportShapeTest(unittest.TestCase):
    """The console report says what can be settled and what still needs a person."""

    def report(self):
        graded = [{"id": "2026-W36-01", "check": "cred.tracked", "target": "a.py",
                   "applied": "2026-09-01", "then": "3 count", "now": "0 count", "verdict": "won",
                   "note": "", "audit": "2026-09-15-secrets.json"},
                  {"id": "2026-W36-02", "check": "vuln.ssrf", "target": "", "applied": "",
                   "then": "1 count", "now": "", "verdict": "",
                   "note": "no review audit in the workspace", "audit": ""}]
        return grade.report(SLUG, graded, dt.date(2026, 9, 16))

    def test_the_header_says_which_repository_and_which_day(self):
        self.assertIn(f"grade  {SLUG}  2026-09-16", self.report())

    def test_the_counting_line_is_a_bar_of_the_four_verdicts(self):
        self.assertIn("2 due · 1 won · 0 returned · 0 no-change", self.report())

    def test_a_row_is_one_line_of_verdict_row_id_check_id_then_and_now(self):
        text = self.report()
        self.assertRegex(text, r"\nwon {9}2026-W36-01  cred\.tracked {18}3 count  0 count\n")
        self.assertRegex(text, r"\nopen {8}2026-W36-02  vuln\.ssrf {21}1 count  -\n")
        self.assertNotIn("->", text)

    def test_nothing_due_says_why_there_is_nothing(self):
        self.assertIn("nothing due, no log row has reached its verify date",
                      grade.report(SLUG, [], dt.date(2026, 9, 16)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
