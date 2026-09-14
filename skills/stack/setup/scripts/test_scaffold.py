#!/usr/bin/env python3
"""Offline tests for scaffold.py: the workspace, the config reader, the flags, the log row, the snapshot.

Run: python3 skills/stack/setup/scripts/test_scaffold.py
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
TODAY = "2026-09-14"
SLUG = "example-app"


def run(*args, expect=0):
    r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    assert r.returncode == expect, f"exit {r.returncode}: {r.stdout}{r.stderr}"
    return r.stdout + r.stderr


def workspace(d, slug=SLUG, **standards):
    root = Path(d) / "stack"
    run("--root", str(root), slug)
    text = (root / "standards.md").read_text(encoding="utf-8")
    for key, v in standards.items():
        text = text.replace(f"- {key}: ", f"- {key}: {v} ", 1)
    (root / "standards.md").write_text(text, encoding="utf-8")
    return root


def set_path(root, slug, path):
    cfg = root / "repos" / slug / "config.md"
    text = cfg.read_text(encoding="utf-8").replace("- path: ", f"- path: {path} ", 1)
    cfg.write_text(text, encoding="utf-8")
    return cfg


class SlugTest(unittest.TestCase):
    def test_a_slug_is_lower_case_and_has_no_separator(self):
        self.assertEqual(scaffold.slug_name("Example App"), "example-app")
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
            p.write_text("- path: (the checkout this machine reads)\n- role: stack\n", encoding="utf-8")
            self.assertEqual(scaffold.value(p, "path"), "")
            self.assertEqual(scaffold.value(p, "role"), "stack")

    def test_a_value_keeps_its_content_and_loses_the_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "standards.md"
            p.write_text("- profile: standard (the bars choose starts from)\n", encoding="utf-8")
            self.assertEqual(scaffold.value(p, "profile"), "standard")

    def test_entries_that_carry_spaces_are_separated_by_semicolons(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.md"
            p.write_text("- accepted: escape.type a.ts:3 the driver 2026-01-01;"
                         " dead.dep lodash kept for the migration 2026-02-02\n", encoding="utf-8")
            self.assertEqual(len(scaffold.values(p, "accepted", sep=";")), 2)


class WorkspaceTest(unittest.TestCase):
    def test_creating_twice_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            (root / "config.md").write_text("# mine\n", encoding="utf-8")
            out = run("--root", str(root), SLUG)
            self.assertIn("exists", out)
            self.assertEqual((root / "config.md").read_text(encoding="utf-8"), "# mine\n")

    def test_check_names_what_is_missing_and_passes_on_a_full_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "stack"
            out = run("--root", str(root), "--check", expect=1)
            self.assertIn("missing", out)
            workspace(d)
            self.assertIn("ok", run("--root", str(root), "--check"))

    def test_a_folder_that_does_not_say_role_stack_is_not_measured(self):
        """A folder somebody made by hand is not this theme's business until it says so."""
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            other = root / "repos" / "not-stack"
            other.mkdir(parents=True)
            (other / "config.md").write_text("- role: notes\n", encoding="utf-8")
            self.assertIn("ok", run("--root", str(root), "--check"))

    def test_the_repository_folder_holds_the_four_directories_and_no_rules(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            base = root / "repos" / SLUG
            for name in ("audits", "log/stack", "reports/stack", "proposals"):
                self.assertTrue((base / name).is_dir(), name)
            self.assertFalse((base / "rules").exists())
            self.assertFalse((root / "cache").exists())


class FlagsTest(unittest.TestCase):
    def test_flags_carry_the_checkout_path_the_date_and_the_accepted_entries(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            cfg = set_path(root, SLUG, d)
            text = cfg.read_text(encoding="utf-8")
            text = text.replace("- accepted: ", "- accepted: escape.type a.ts:3 agreed 2026-01-01 ", 1)
            cfg.write_text(text, encoding="utf-8")
            out = run("--root", str(root), "--flags", SLUG, "--today", TODAY)
            self.assertIn(f"guards: --root {d} --today {TODAY}", out)
            self.assertIn(f"drift: --root {d} --today {TODAY}", out)
            self.assertIn("--accept 'escape.type a.ts:3 agreed 2026-01-01'", out)
            self.assertIn(f"new: --root {d}", out)
            self.assertNotIn("--snapshot ", out)

    def test_flags_carry_the_snapshot_once_it_exists(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            set_path(root, SLUG, d)
            (Path(d) / "stack.yaml").write_text("name: x\n", encoding="utf-8")
            run("--root", str(root), SLUG, "--snapshot")
            out = run("--root", str(root), "--flags", SLUG)
            self.assertIn(f"--snapshot {root / 'repos' / SLUG / 'stack.yaml'}", out)

    def test_a_blank_path_says_so_instead_of_printing_a_flag_that_names_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            out = run("--root", str(root), "--flags", SLUG)
            self.assertIn("path is blank", out)
            self.assertIn("no repository path is recorded", out)


class SnapshotTest(unittest.TestCase):
    def test_the_snapshot_copies_the_declaration_into_the_repository_folder(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            set_path(root, SLUG, d)
            (Path(d) / "stack.yaml").write_text("name: example\n", encoding="utf-8")
            out = run("--root", str(root), SLUG, "--snapshot")
            self.assertIn("snapshot:", out)
            copy = root / "repos" / SLUG / "stack.yaml"
            self.assertEqual(copy.read_text(encoding="utf-8"), "name: example\n")

    def test_the_snapshot_refuses_without_a_path_or_without_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            self.assertIn("path is blank", run("--root", str(root), SLUG, "--snapshot", expect=1))
            set_path(root, SLUG, d)
            self.assertIn("no stack.yaml", run("--root", str(root), SLUG, "--snapshot", expect=1))


class RowTest(unittest.TestCase):
    def test_a_row_carries_an_id_a_measure_and_a_verify_date(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            out = run("--root", str(root), SLUG, "--append-row", "--today", TODAY,
                      "--check-id", "escape.unenforced", "--target", "gate",
                      "--action", "make the gate a required check", "--class", "ask",
                      "--then", "1 count", "--status", "applied")
            self.assertIn("2026-W38-01", out)
            self.assertIn("verify after: 2026-09-28", out)
            log = (root / f"repos/{SLUG}/log/stack/2026-W38.md").read_text(encoding="utf-8")
            self.assertIn("| 1 count |", log)

    def test_a_second_row_takes_the_next_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            args = ["--root", str(root), SLUG, "--append-row", "--today", TODAY,
                    "--check-id", "escape.type", "--target", "a.ts:3", "--action", "fix the type",
                    "--class", "ask", "--then", "1 count", "--status", "applied"]
            run(*args)
            self.assertIn("2026-W38-02", run(*args))

    def test_a_unit_outside_the_closed_set_is_refused_when_the_row_is_written(self):
        """A measure nothing recomputes is discovered now, not at the verify date."""
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            out = run("--root", str(root), SLUG, "--append-row", "--today", TODAY,
                      "--check-id", "escape.type", "--target", "a.ts:3", "--action", "fix",
                      "--class", "ask", "--then", "3 findings", expect=1)
            self.assertIn("not a measure", out)

    def test_a_check_id_and_a_class_are_both_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            base = ["--root", str(root), SLUG, "--append-row", "--today", TODAY,
                    "--target", "a.ts", "--action", "fix", "--then", "1 count"]
            self.assertIn("not a check id",
                          run(*base, "--check-id", "Escape Type", "--class", "ask", expect=1))
            self.assertIn("not a risk class",
                          run(*base, "--check-id", "escape.type", "--class", "maybe", expect=1))

    def test_safe_runs_as_confirm_until_the_workspace_allows_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            out = run("--root", str(root), SLUG, "--append-row", "--today", TODAY,
                      "--check-id", "dead.export", "--target", "packages/ui", "--action", "delete",
                      "--class", "safe", "--then", "1 count", "--status", "applied")
            self.assertIn("runs as confirm", out)
            log = (root / f"repos/{SLUG}/log/stack/2026-W38.md").read_text(encoding="utf-8")
            self.assertIn("| confirm |", log)

    def test_without_a_verify_window_the_row_is_refused_rather_than_undatable(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            out = run("--root", str(root), SLUG, "--append-row", "--today", TODAY,
                      "--check-id", "escape.type", "--target", "a.ts", "--action", "fix",
                      "--class", "ask", "--then", "1 count", "--status", "applied", expect=1)
            self.assertIn("verify_window_days", out)

    def test_due_lists_a_row_past_its_date_and_nothing_before_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d, verify_window_days=14)
            run("--root", str(root), SLUG, "--append-row", "--today", TODAY,
                "--check-id", "escape.type", "--target", "a.ts", "--action", "fix",
                "--class", "ask", "--then", "1 count", "--status", "applied")
            self.assertIn("nothing due", run("--root", str(root), SLUG, "--due",
                                             "--today", "2026-09-20"))
            self.assertIn("2026-W38-01", run("--root", str(root), SLUG, "--due",
                                             "--today", "2026-09-29"))

    def test_the_log_command_prints_the_trailer_of_this_theme(self):
        with tempfile.TemporaryDirectory() as d:
            root = workspace(d)
            out = run("--root", str(root), SLUG, "--log", "--today", TODAY)
            self.assertIn("Stack-Log: 2026-W38-01", out)
            self.assertNotIn("Security-Log", out)


class CellTest(unittest.TestCase):
    def test_a_pipe_inside_a_cell_survives_the_round_trip(self):
        cell = scaffold.escape("a | b")
        self.assertEqual(scaffold.split_cells(f"| {cell} | x |")[0], "a | b")

    def test_a_row_for_a_column_the_table_lacks_is_refused(self):
        with self.assertRaises(SystemExit):
            scaffold.insert_row("## Actions\n\n| id |\n|---|\n", "## Actions", {"nope": "x"})


class ContractTest(unittest.TestCase):
    def test_help_prints_the_docstring(self):
        self.assertIn("Scaffold and inspect the stack workspace", run("--help"))

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn("\033[", run("--root", str(Path(d) / "stack"), SLUG))

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(Path(d) / "stack"), SLUG],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
