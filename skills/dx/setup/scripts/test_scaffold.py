#!/usr/bin/env python3
"""Offline tests for scaffold.py: machine names (a folder is named after one), week ids, drift.

Run: python3 skills/dx/setup/scripts/test_scaffold.py
Writes into a temp folder; no network.
"""
import datetime as dt
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scaffold  # noqa: E402

SCRIPT = os.path.abspath(scaffold.__file__)


class MachineNameTest(unittest.TestCase):
    def test_case_and_spaces_are_normalised(self):
        self.assertEqual(scaffold.machine_name("Nils-MBP.local"), "nils-mbp.local")
        self.assertEqual(scaffold.machine_name(" Work Laptop "), "work-laptop")

    def test_a_name_that_is_not_a_host_is_rejected(self):
        """Every folder is named after this value, so a path segment must never survive it."""
        for bad in ("..", ".", "", "/", "../../escaped", "a/b", "-x", "x-"):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                scaffold.machine_name(bad)

    def test_traversal_writes_nothing_outside_the_root(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "dx"
            root.mkdir(parents=True)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "../escaped"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["dx"])
            self.assertEqual(list(root.iterdir()), [])


class WeekTest(unittest.TestCase):
    def test_week_bounds_start_on_monday(self):
        week, start, end = scaffold.week_bounds(dt.date(2026, 9, 3))
        self.assertEqual(week, "2026-W36")
        self.assertEqual((start.isoformat(), end.isoformat()), ("2026-08-31", "2026-09-06"))


class WorkspaceTest(unittest.TestCase):
    def build(self, d, machine="example-machine"):
        root = Path(d) / "dx"
        subprocess.run([sys.executable, SCRIPT, "--root", str(root), machine],
                       capture_output=True, text=True, check=True)
        return root

    def test_a_fresh_workspace_checks_ok(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--check"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("ok", r.stdout)

    def test_an_empty_root_reports_the_missing_machine(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(Path(d) / "dx"), "--check"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("<hostname>", r.stdout)

    def test_a_template_section_the_file_lacks_is_reported(self):
        """create() never overwrites, so a template that gains a section must not fail silently."""
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            cfg = root / "machines" / "example-machine" / "config.md"
            cfg.write_text("# example-machine: machine facts\n\n## Where things live\n\n- project_roots: ~/code\n")
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--check"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("## History sources", r.stdout)

    def test_second_run_creates_nothing_and_keeps_edits(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            (root / "standards.md").write_text("# edited\n")
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine"],
                               capture_output=True, text=True, check=True)
            self.assertNotIn("created", r.stdout)
            self.assertEqual((root / "standards.md").read_text(), "# edited\n")

    def test_the_readme_table_lists_every_machine(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            subprocess.run([sys.executable, SCRIPT, "--root", str(root), "second-machine"],
                           capture_output=True, text=True, check=True)
            table = (root / "README.md").read_text()
            self.assertIn("| example-machine | `machines/example-machine/` | template |", table)
            self.assertIn("| second-machine | `machines/second-machine/` | template |", table)

    def test_ids_continue_within_the_week_and_the_trailer_matches(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            args = [sys.executable, SCRIPT, "--root", str(root), "example-machine", "--log", "--today", "2026-09-05"]
            first = subprocess.run(args, capture_output=True, text=True, check=True).stdout
            self.assertIn("next id: 2026-W36-01", first)
            self.assertIn("commit trailer: DX-Log: 2026-W36-01", first)
            week = root / "machines" / "example-machine" / "log" / "2026-W36.md"
            week.write_text(week.read_text() + "| 2026-W36-01 | disk.cache | ~/x | cleared | safe | 41 | applied | 2026-09-02 | 2026-09-16 | |\n")
            second = subprocess.run(args, capture_output=True, text=True, check=True).stdout
            self.assertIn("next id: 2026-W36-02", second)

    def test_due_lists_only_rows_past_their_verify_date(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine", "--log",
                            "--today", "2026-09-05"], capture_output=True, text=True, check=True)
            week = root / "machines" / "example-machine" / "log" / "2026-W36.md"
            week.write_text(week.read_text()
                            + "| 2026-W36-01 | disk.cache | ~/x | cleared | safe | 41 | applied | 2026-09-02 | 2026-09-16 | |\n"
                            + "| 2026-W36-02 | git.stash-old | ~/y | dropped | ask | 3 | applied | 2026-09-02 | 2026-09-04 | |\n")
            out = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine", "--due",
                                  "--today", "2026-09-05"], capture_output=True, text=True, check=True).stdout
            self.assertIn("2026-W36-02", out)
            self.assertNotIn("2026-W36-01", out)
            self.assertIn("1 due", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
