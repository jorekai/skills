#!/usr/bin/env python3
"""Offline tests for scaffold.py: machine names (a folder is named after one), week ids, drift.

Run: python3 skills/dx/setup/scripts/test_scaffold.py
Writes into a temp folder; no network.
"""
import datetime as dt
import os
import re
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
            week = root / "machines" / "example-machine" / "log" / "dx" / "2026-W36.md"
            week.write_text(week.read_text() + "| 2026-W36-01 | disk.cache | ~/x | cleared | safe | 41 | applied | 2026-09-02 | 2026-09-16 | |\n")
            second = subprocess.run(args, capture_output=True, text=True, check=True).stdout
            self.assertIn("next id: 2026-W36-02", second)

    def test_due_lists_only_rows_past_their_verify_date(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine", "--log",
                            "--today", "2026-09-05"], capture_output=True, text=True, check=True)
            week = root / "machines" / "example-machine" / "log" / "dx" / "2026-W36.md"
            week.write_text(week.read_text()
                            + "| 2026-W36-01 | disk.cache | ~/x | cleared | safe | 41 | applied | 2026-09-02 | 2026-09-16 | |\n"
                            + "| 2026-W36-02 | git.stash-old | ~/y | dropped | ask | 3 | applied | 2026-09-02 | 2026-09-04 | |\n")
            out = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine", "--due",
                                  "--today", "2026-09-05"], capture_output=True, text=True, check=True).stdout
            self.assertIn("2026-W36-02", out)
            self.assertNotIn("2026-W36-01", out)
            self.assertIn("1 due", out)


class FlagsTest(unittest.TestCase):
    """Standards become the arguments the measuring scripts take, so no step has to retype them."""

    def build(self, d, **values):
        root = Path(d) / "dx"
        subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine"],
                       capture_output=True, text=True, check=True)
        for relpath, pairs in values.items():
            p = root / relpath.replace("MACHINE", "machines/example-machine")
            text = p.read_text()
            for key, val in pairs.items():
                text = re.sub(rf"^- {key}:.*$", f"- {key}: {val}", text, count=1, flags=re.M)
            p.write_text(text)
        return root

    def flags(self, root):
        out = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine", "--flags"],
                             capture_output=True, text=True, check=True).stdout
        return dict(line.split(":", 1) for line in out.splitlines() if ":" in line)

    def test_a_blank_workspace_says_so_instead_of_inventing_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            got = self.flags(self.build(d))
            self.assertIn("project_roots is blank", got["paths"])
            self.assertIn("own defaults", got["repos"])
            self.assertIn("no history source", got["friction"])

    def test_every_standard_becomes_the_flag_that_carries_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(
                d,
                **{"config.md": {"git_email": "someone@example.com"},
                   "standards.md": {"branch_stale_days": "90", "stash_stale_days": "60",
                                    "disk_free_min_gb": "20", "slow_command_seconds": "45",
                                    "verify_window_days": "14"},
                   "MACHINE/config.md": {"project_roots": "~/code", "scan_max_depth": "4",
                                         "shell_history": "~/.history", "container_runtime": "podman"}})
            got = self.flags(root)
            self.assertEqual(got["paths"].strip(), "~/code")
            self.assertIn("--stale-days 90", got["repos"])
            self.assertIn("--stash-days 60", got["repos"])
            self.assertIn("--depth 4", got["repos"])
            self.assertIn("--expect-email someone@example.com", got["repos"])
            self.assertIn("--min-free-gb 20", got["machine"])
            self.assertIn("--runtime podman", got["machine"])
            self.assertIn("--history ~/.history", got["friction"])
            self.assertIn("--slow-seconds 45", got["friction"])
            self.assertIn("14 days", got["verify after"])

    def test_a_machine_limit_overrides_the_shared_standard(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d, **{"standards.md": {"disk_free_min_gb": "20"},
                                    "MACHINE/config.md": {"disk_free_min_gb": "50"}})
            self.assertIn("--min-free-gb 50", self.flags(root)["machine"])

    def test_a_blank_key_leaves_its_flag_out_rather_than_guessing(self):
        """A blank value turns that check off, which is an answer, not a gap to fill in."""
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d, **{"standards.md": {"branch_stale_days": "90"}})
            repos = self.flags(root)["repos"]
            self.assertIn("--stale-days 90", repos)
            self.assertNotIn("--stash-days", repos)
            self.assertNotIn("--expect-email", repos)


class AppendRowTest(unittest.TestCase):
    """A row written by hand is one miscounted column away from being skipped in silence."""

    def build(self, d, verify_days="14"):
        root = Path(d) / "dx"
        subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine"],
                       capture_output=True, text=True, check=True)
        std = root / "standards.md"
        std.write_text(std.read_text(encoding="utf-8").replace(
            "- verify_window_days: (days between an applied action and its verdict)",
            f"- verify_window_days: {verify_days}"), encoding="utf-8")
        return root

    def add(self, root, *args):
        return subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine",
                               "--append-row", "--today", "2026-09-05", *args],
                              capture_output=True, text=True)

    def log_text(self, root):
        return (root / "machines" / "example-machine" / "log" / "dx" / "2026-W36.md").read_text(encoding="utf-8")

    def row(self, root):
        return [l for l in self.log_text(root).splitlines() if l.startswith("| 2026-W36-")][0]

    def test_the_cells_land_in_the_order_the_table_header_names(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            got = self.add(root, "--check-id", "disk.cache", "--target", "/tmp/cache",
                           "--action", "empty the biggest ones", "--class", "safe", "--then", "42 GB")
            self.assertEqual(got.returncode, 0, got.stderr)
            self.assertIn("| 2026-W36-01 | disk.cache | /tmp/cache | empty the biggest ones "
                          "| safe | 42 GB | todo |  |  |  |", self.log_text(root))

    def test_a_second_row_takes_the_next_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            self.add(root, "--check-id", "disk.cache", "--target", "/tmp/a", "--action", "x",
                     "--class", "safe", "--then", "1 GB")
            got = self.add(root, "--check-id", "disk.cache", "--target", "/tmp/b", "--action", "y",
                           "--class", "safe", "--then", "2 GB")
            self.assertIn("id: 2026-W36-02", got.stdout)

    def test_applied_sets_the_date_and_the_verify_date_from_the_standard(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            self.add(root, "--check-id", "disk.cache", "--target", "/tmp/a", "--action", "x",
                     "--class", "safe", "--then", "1 GB", "--status", "applied")
            self.assertIn("| applied | 2026-09-05 | 2026-09-19 |", self.row(root))

    def test_an_applied_date_makes_the_row_applied(self):
        """A date without the status is a row that is never due, so it is never graded."""
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            self.add(root, "--check-id", "disk.cache", "--target", "/tmp/a", "--action", "x",
                     "--class", "safe", "--then", "1 GB", "--applied", "2026-09-01")
            self.assertIn("| applied | 2026-09-01 | 2026-09-15 |", self.row(root))

    def test_verify_days_beats_the_standard(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            self.add(root, "--check-id", "disk.cache", "--target", "/tmp/a", "--action", "x",
                     "--class", "safe", "--then", "1 GB", "--status", "applied", "--verify-days", "3")
            self.assertIn("2026-09-08", self.row(root))

    def test_an_applied_row_without_a_verify_window_is_refused(self):
        """A row nobody can grade is worse than no row: it looks like work that was checked."""
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d, verify_days="")
            got = self.add(root, "--check-id", "disk.cache", "--target", "/tmp/a", "--action", "x",
                           "--class", "safe", "--then", "1 GB", "--status", "applied")
            self.assertNotEqual(got.returncode, 0)
            self.assertIn("verify_window_days", got.stderr)

    def test_a_measure_a_script_cannot_recompute_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            for bad in ("41 gigs", "a lot", "", "12", "half"):
                with self.subTest(bad=bad):
                    got = self.add(root, "--check-id", "disk.cache", "--target", "/tmp/a",
                                   "--action", "x", "--class", "safe", "--then", bad)
                    self.assertNotEqual(got.returncode, 0)
                    self.assertIn("not a measure", got.stderr)

    def test_a_check_id_or_class_outside_the_table_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            bad_id = self.add(root, "--check-id", "Disk Cache", "--target", "/tmp/a", "--action", "x",
                              "--class", "safe", "--then", "1 GB")
            self.assertIn("not a check id", bad_id.stderr)
            bad_class = self.add(root, "--check-id", "disk.cache", "--target", "/tmp/a", "--action", "x",
                                 "--class", "maybe", "--then", "1 GB")
            self.assertIn("not a risk class", bad_class.stderr)

    def test_an_action_without_a_sentence_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            got = self.add(root, "--check-id", "disk.cache", "--target", "/tmp/a", "--action", "",
                           "--class", "safe", "--then", "1 GB")
            self.assertNotEqual(got.returncode, 0)

    def test_a_pipe_and_a_line_break_stay_inside_the_cell(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            self.add(root, "--check-id", "friction.slow-command", "--target", "build | test",
                     "--action", "write one\ncommand", "--class", "safe", "--then", "600 seconds")
            row = self.row(root)
            self.assertIn("build \\| test", row)
            self.assertEqual(row.count(" | "), 9)


class MigrateLogTest(unittest.TestCase):
    """The log moved to log/<theme>/ (decisions/0015). A week file left flat is read by nobody."""

    def build(self, d):
        root = Path(d) / "dx"
        subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-machine"],
                       capture_output=True, text=True, check=True)
        return root

    def flat(self, root, name="2026-W35.md", body="# 2026-W35\n"):
        old = root / "machines" / "example-machine" / "log"
        old.mkdir(parents=True, exist_ok=True)
        p = old / name
        p.write_text(body, encoding="utf-8")
        return p

    def test_a_flat_week_file_moves_down_one_level(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            old = self.flat(root)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--migrate-log",
                                "example-machine"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(old.exists())
            moved = root / "machines" / "example-machine" / "log" / "dx" / "2026-W35.md"
            self.assertEqual(moved.read_text(encoding="utf-8"), "# 2026-W35\n")

    def test_a_name_that_already_exists_below_is_left_alone(self):
        """Two files of the same week are two records. Overwriting one loses a week of rows."""
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            old = self.flat(root, body="# old\n")
            below = root / "machines" / "example-machine" / "log" / "dx" / "2026-W35.md"
            below.parent.mkdir(parents=True, exist_ok=True)
            below.write_text("# new\n", encoding="utf-8")
            subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--migrate-log",
                            "example-machine"], capture_output=True, text=True, check=True)
            self.assertEqual(old.read_text(encoding="utf-8"), "# old\n")
            self.assertEqual(below.read_text(encoding="utf-8"), "# new\n")

    def test_check_names_a_flat_week_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.build(d)
            self.flat(root)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--check"],
                               capture_output=True, text=True)
            self.assertIn("--migrate-log", r.stdout)
            self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
