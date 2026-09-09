#!/usr/bin/env python3
"""Offline tests for scaffold.py: the workspace, the trust-model reader, and the log row.

Run: python3 skills/security/setup/scripts/test_scaffold.py
Every test builds its own workspace in a temporary directory; no network, no shared state.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scaffold  # noqa: E402

SCRIPT = os.path.abspath(scaffold.__file__)
TODAY = "2026-09-09"


def run(*args, expect=0):
    r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    assert r.returncode == expect, f"exit {r.returncode}: {r.stdout}{r.stderr}"
    return r.stdout + r.stderr


def workspace(d, slug="example-repo", **standards):
    root = Path(d) / "sec"
    run("--root", str(root), slug)
    text = (root / "standards.md").read_text(encoding="utf-8")
    for key, v in standards.items():
        text = text.replace(f"- {key}: ", f"- {key}: {v} ", 1)
    (root / "standards.md").write_text(text, encoding="utf-8")
    return root


class SlugTest(unittest.TestCase):
    def test_a_slug_is_lower_case_and_has_no_separator(self):
        self.assertEqual(scaffold.slug_name("Example Repo"), "example-repo")
        with self.assertRaises(SystemExit):
            scaffold.slug_name("../etc")
        with self.assertRaises(SystemExit):
            scaffold.slug_name("")

    def test_a_missing_argument_falls_back_to_the_current_directory(self):
        self.assertEqual(scaffold.slug_name(), Path.cwd().name.lower().replace(" ", "-"))


class ValueTest(unittest.TestCase):
    def test_a_template_hint_reads_as_blank(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.md"
            p.write_text("- path: (the checkout this machine reads)\n- role: code\n", encoding="utf-8")
            self.assertEqual(scaffold.value(p, "path"), "")
            self.assertEqual(scaffold.value(p, "role"), "code")

    def test_a_value_keeps_its_content_and_loses_the_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "standards.md"
            p.write_text("- allow_safe: no (yes lets a safe fix run)\n", encoding="utf-8")
            self.assertEqual(scaffold.value(p, "allow_safe"), "no")

    def test_entries_that_carry_commas_are_separated_by_semicolons(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.md"
            p.write_text("- accepted: build.token-broad a.yml agreed, with the owner 2026-01-01;"
                         " cred.tracked b.py a test value 2026-02-02\n", encoding="utf-8")
            self.assertEqual(len(scaffold.values(p, "accepted", sep=";")), 2)


class WorkspaceTest(unittest.TestCase):
    def test_creating_twice_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            (root / "config.md").write_text("# mine\n", encoding="utf-8")
            out = run("--root", str(root), "example-repo")
            self.assertIn("exists", out)
            self.assertEqual((root / "config.md").read_text(encoding="utf-8"), "# mine\n")

    def test_check_names_what_is_missing_and_passes_on_a_full_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "sec"
            out = run("--root", str(root), "--check", expect=1)
            self.assertIn("missing", out)
            workspace(d)
            self.assertIn("ok", run("--root", str(root), "--check"))

    def test_a_folder_that_does_not_say_role_code_is_not_measured(self):
        """A folder somebody made by hand is not this theme's business until it says so."""
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            other = root / "repos" / "not-code"
            other.mkdir(parents=True)
            (other / "config.md").write_text("- role: notes\n", encoding="utf-8")
            self.assertIn("ok", run("--root", str(root), "--check"))

    def test_the_repository_folder_holds_a_rules_directory(self):
        """review writes its rules there, and a pass with no rules folder measures nothing."""
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            self.assertTrue((root / "repos" / "example-repo" / "rules").is_dir())


class FlagsTest(unittest.TestCase):
    def test_flags_carry_the_checkout_path_and_the_accepted_entries(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            cfg = root / "repos" / "example-repo" / "config.md"
            text = cfg.read_text(encoding="utf-8")
            text = text.replace("- path: ", f"- path: {d} ", 1)
            text = text.replace("- accepted: ", "- accepted: build.token-broad a.yml agreed 2026-01-01 ", 1)
            cfg.write_text(text, encoding="utf-8")
            out = run("--root", str(root), "--flags", "example-repo")
            self.assertIn(f"--root {d}", out)
            self.assertIn("--accept 'build.token-broad a.yml agreed 2026-01-01'", out)
            self.assertIn("--rules-dir", out)

    def test_the_bar_the_review_keeps_is_printed_beside_the_flags(self):
        """review.py takes no bar, so the value reaches the skill through this line."""
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, confidence_floor=8)
            self.assertIn("confidence floor: 8", run("--root", str(root), "--flags", "example-repo"))

    def test_a_blank_path_says_so_instead_of_printing_a_flag_that_names_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            out = run("--root", str(root), "--flags", "example-repo")
            self.assertIn("path is blank", out)
            self.assertIn("no repository path is recorded", out)


class RowTest(unittest.TestCase):
    def test_a_row_carries_an_id_a_measure_and_a_verify_date(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            out = run("--root", str(root), "example-repo", "--append-row", "--today", TODAY,
                      "--check-id", "build.action-unpinned", "--target", ".github/workflows/a.yml",
                      "--action", "pin the actions", "--class", "confirm", "--then", "4 count",
                      "--status", "applied")
            self.assertIn("2026-W37-01", out)
            self.assertIn("verify after: 2026-09-23", out)
            log = (root / "repos/example-repo/log/security/2026-W37.md").read_text(encoding="utf-8")
            self.assertIn("| 4 count |", log)

    def test_a_second_row_takes_the_next_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            args = ["--root", str(root), "example-repo", "--append-row", "--today", TODAY,
                    "--check-id", "cred.tracked", "--target", "a.py", "--action", "rotate",
                    "--class", "ask", "--then", "1 count", "--status", "applied"]
            run(*args)
            self.assertIn("2026-W37-02", run(*args))

    def test_a_unit_outside_the_closed_set_is_refused_when_the_row_is_written(self):
        """A measure nothing recomputes is discovered now, not at the verify date."""
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            out = run("--root", str(root), "example-repo", "--append-row", "--today", TODAY,
                      "--check-id", "cred.tracked", "--target", "a.py", "--action", "rotate",
                      "--class", "ask", "--then", "3 findings", expect=1)
            self.assertIn("not a measure", out)

    def test_a_check_id_and_a_class_are_both_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            base = ["--root", str(root), "example-repo", "--append-row", "--today", TODAY,
                    "--target", "a.py", "--action", "rotate", "--then", "1 count"]
            self.assertIn("not a check id",
                          run(*base, "--check-id", "Cred Tracked", "--class", "ask", expect=1))
            self.assertIn("not a risk class",
                          run(*base, "--check-id", "cred.tracked", "--class", "maybe", expect=1))

    def test_safe_runs_as_confirm_until_the_workspace_allows_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            out = run("--root", str(root), "example-repo", "--append-row", "--today", TODAY,
                      "--check-id", "build.token-broad", "--target", "a.yml", "--action", "add rights",
                      "--class", "safe", "--then", "1 count", "--status", "applied")
            self.assertIn("runs as confirm", out)
            log = (root / "repos/example-repo/log/security/2026-W37.md").read_text(encoding="utf-8")
            self.assertIn("| confirm |", log)

    def test_without_a_verify_window_the_row_is_refused_rather_than_undatable(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            out = run("--root", str(root), "example-repo", "--append-row", "--today", TODAY,
                      "--check-id", "cred.tracked", "--target", "a.py", "--action", "rotate",
                      "--class", "ask", "--then", "1 count", "--status", "applied", expect=1)
            self.assertIn("verify_window_days", out)

    def test_due_lists_a_row_past_its_date_and_nothing_before_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            run("--root", str(root), "example-repo", "--append-row", "--today", TODAY,
                "--check-id", "cred.tracked", "--target", "a.py", "--action", "rotate",
                "--class", "ask", "--then", "1 count", "--status", "applied")
            self.assertIn("nothing due", run("--root", str(root), "example-repo", "--due",
                                             "--today", "2026-09-20"))
            self.assertIn("2026-W37-01", run("--root", str(root), "example-repo", "--due",
                                             "--today", "2026-09-24"))

    def test_the_log_command_prints_the_trailer_of_this_theme(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            out = run("--root", str(root), "example-repo", "--log", "--today", TODAY)
            self.assertIn("Security-Log: 2026-W37-01", out)


class CellTest(unittest.TestCase):
    def test_a_pipe_inside_a_cell_survives_the_round_trip(self):
        cell = scaffold.escape("a | b")
        self.assertEqual(scaffold.split_cells(f"| {cell} | x |")[0], "a | b")

    def test_a_row_for_a_column_the_table_lacks_is_refused(self):
        with self.assertRaises(SystemExit):
            scaffold.insert_row("## Actions\n\n| id |\n|---|\n", "## Actions", {"nope": "x"})


class ContractTest(unittest.TestCase):
    def test_help_prints_the_docstring(self):
        self.assertIn("Scaffold and inspect the security workspace", run("--help"))

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn("\033[", run("--root", str(Path(d) / "sec"), "example-repo"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
