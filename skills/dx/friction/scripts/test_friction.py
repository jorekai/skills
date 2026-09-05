#!/usr/bin/env python3
"""Offline tests for friction.py: redaction, command shapes, units, thresholds, what gets printed.

Run: python3 skills/dx/friction/scripts/test_friction.py
Builds a throwaway history in a temp folder; no real history is read and no network is used.
"""
import contextlib
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import friction  # noqa: E402

NOW = 1_757_030_400


class RedactionTest(unittest.TestCase):
    def test_known_credential_shapes_never_survive(self):
        for secret in ("ghp_" + "a" * 30, "sk-" + "b" * 32, "AKIA" + "C" * 16,
                       "xoxb-" + "1" * 20, "f" * 40, "Bearer " + "z" * 20):
            with self.subTest(secret=secret[:8]):
                self.assertNotIn(secret, friction.redact(f"curl -H '{secret}' https://example.com"))

    def test_a_credential_flag_keeps_its_name_and_loses_its_value(self):
        got = friction.redact("mysql --password=hunter2 --host db")
        self.assertIn("--password=<redacted>", got)
        self.assertNotIn("hunter2", got)

    def test_an_assignment_that_names_a_secret_is_redacted(self):
        got = friction.redact("GITHUB_TOKEN=abcdefghijklmnop gh pr list")
        self.assertIn("GITHUB_TOKEN=<redacted>", got)
        self.assertNotIn("abcdefghijklmnop", got)

    def test_an_address_and_a_url_credential_are_removed(self):
        self.assertIn("<address>", friction.redact("git config user.email someone@example.com"))
        self.assertNotIn("secret", friction.redact("git clone https://user:secret@example.com/x.git"))

    def test_the_home_directory_becomes_a_tilde(self):
        got = friction.redact(f"cd {Path.home()}/projects/app")
        self.assertNotIn(str(Path.home()), got)
        self.assertTrue(got.endswith("~/projects/app"), got)


class ShapeTest(unittest.TestCase):
    def test_the_program_and_its_subcommand_survive_and_arguments_do_not(self):
        self.assertEqual(friction.shape("git commit -m 'a message'"), "git commit")
        self.assertEqual(friction.shape("/usr/local/bin/npm run dev"), "npm run dev")
        self.assertEqual(friction.shape("docker compose up -d"), "docker compose up")

    def test_a_wrapper_is_not_the_command(self):
        self.assertEqual(friction.shape("sudo apt install"), "apt install")
        self.assertEqual(friction.shape("time make build"), "make build")

    def test_two_words_after_the_program_are_kept(self):
        """`npm run dev` and `npm run build` are different work, so the third token stays."""
        self.assertEqual(friction.shape("npm run build"), "npm run build")
        self.assertEqual(friction.shape("apt install curl"), "apt install curl")

    def test_a_path_or_flag_ends_the_shape(self):
        self.assertEqual(friction.shape("python3 scripts/run.py"), "python3")
        self.assertEqual(friction.shape("rg --hidden pattern"), "rg")

    def test_a_line_that_is_not_a_command_has_no_shape(self):
        """A history file stores a multi-line command as several lines; the tail is not a program."""
        for fragment in ('" then done', "", "   ", "| grep x", "&& make"):
            self.assertEqual(friction.shape(fragment), "", fragment)


class UnitTest(unittest.TestCase):
    def test_the_divisor_comes_from_the_timestamp_range(self):
        self.assertEqual(friction._divisor(1_757_030_400), 1)                      # seconds
        self.assertEqual(friction._divisor(1_757_030_400_000), 1000)               # milliseconds
        self.assertEqual(friction._divisor(1_757_030_400_000_000_000), 1_000_000_000)

    def test_a_duration_uses_the_same_divisor_as_the_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "history.db"
            con = sqlite3.connect(db)
            con.execute("create table history (id text primary key, timestamp integer, duration integer,"
                        " exit integer, command text, cwd text, session text)")
            con.execute("insert into history values ('1', ?, ?, 0, 'make build', '/x', 's1')",
                        (NOW * 10 ** 9, 90 * 10 ** 9))
            con.commit(); con.close()
            entry = friction.read_db(db)[0]
            self.assertEqual(entry.when, NOW)
            self.assertEqual(entry.duration, 90)

    def test_an_unreadable_database_yields_nothing_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "broken.db").write_text("not a database")
            self.assertEqual(friction.read_db(Path(d) / "broken.db"), [])
            self.assertEqual(friction.read_db(Path(d) / "missing.db"), [])


class HistoryFileTest(unittest.TestCase):
    def read(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "history"
            p.write_text(text)
            return friction.read_history_file(p)

    def test_the_extended_format_gives_a_time_and_a_duration(self):
        got = self.read(f": {NOW}:12;make build\n")
        self.assertEqual((got[0].when, got[0].duration, got[0].command), (NOW, 12, "make build"))

    def test_a_plain_line_is_a_command_without_a_time(self):
        got = self.read("make build\n")
        self.assertEqual((got[0].when, got[0].command), (None, "make build"))

    def test_a_missing_file_yields_nothing(self):
        self.assertEqual(friction.read_history_file(Path("/no/such/history")), [])


class FailureTest(unittest.TestCase):
    def test_only_a_positive_exit_code_is_a_failure(self):
        """A negative code means the source recorded no result, not that the command failed."""
        self.assertTrue(friction.failed(friction.Entry(NOW, "x", exit_code=1)))
        self.assertTrue(friction.failed(friction.Entry(NOW, "x", exit_code=130)))
        self.assertFalse(friction.failed(friction.Entry(NOW, "x", exit_code=0)))
        self.assertFalse(friction.failed(friction.Entry(NOW, "x", exit_code=-1)))
        self.assertFalse(friction.failed(friction.Entry(NOW, "x", exit_code=None)))


class AnalyseTest(unittest.TestCase):
    def items(self, entries, min_count=3, slow_seconds=60, examples=2):
        rep = friction.Report()
        friction.analyse(entries, rep, min_count, slow_seconds, examples)
        return {i["id"]: i for i in rep.items}

    def entries(self, spec):
        out = []
        for i, (command, code, duration) in enumerate(spec):
            out.append(friction.Entry(NOW + i * 10, command, duration, code, "/x", "s1"))
        return out

    def test_a_repeated_shape_is_counted_once_with_its_runs(self):
        got = self.items(self.entries([("git status", 0, 1)] * 4))
        self.assertEqual(got["friction.repeat-command"]["data"][0], {"shape": "git status", "count": 4,
                                                                     "examples": ["git status"]})

    def test_a_trivial_command_is_never_a_finding(self):
        got = self.items(self.entries([("clear", 0, 0)] * 20 + [("ls", 0, 0)] * 20))
        self.assertEqual(got["friction.repeat-command"]["level"], "PASS")

    def test_failures_carry_their_exit_codes(self):
        got = self.items(self.entries([("make test", 1, 5)] * 3 + [("make test", 0, 5)]))
        row = got["friction.failed-command"]["data"][0]
        self.assertEqual((row["failures"], row["runs"], row["rate"]), (3, 4, 75))
        self.assertEqual(row["exit_codes"][1], 3)

    def test_a_pair_run_in_order_becomes_a_sequence(self):
        got = self.items(self.entries([("npm install", 0, 1), ("npm run dev", 0, 1)] * 3))
        pair = got["friction.repeat-sequence"]["data"][0]
        self.assertEqual((pair["first"], pair["then"]), ("npm install", "npm run dev"))

    def test_a_command_rerun_soon_after_failing_is_a_retry(self):
        got = self.items(self.entries([("make test", 1, 1), ("make test", 1, 1), ("make test", 1, 1),
                                       ("make test", 0, 1)]))
        self.assertEqual(got["friction.retry-prompt"]["data"][0]["shape"], "make test")

    def test_nothing_above_the_threshold_is_pass_not_absence(self):
        got = self.items(self.entries([("git status", 0, 1)]), min_count=5)
        self.assertTrue(all(i["level"] == "PASS" for i in got.values()), got)


class OutputTest(unittest.TestCase):
    def test_the_text_report_never_prints_a_command_line(self):
        """Examples belong in the JSON that goes into the private workspace, not on a terminal."""
        secret_ish = "deploy --to production-cluster-7"
        entries = [friction.Entry(NOW + i, secret_ish, 1, 1, "/x", "s1") for i in range(5)]
        rep = friction.Report()
        friction.analyse(entries, rep, 3, 60, examples=2)
        text = friction.text_report(rep, len(entries), [])
        self.assertIn("deploy", text)                       # the shape is the point
        self.assertNotIn("production-cluster-7", text)      # the argument is not

    def test_examples_are_redacted_before_they_reach_the_json(self):
        entries = [friction.Entry(NOW + i, "curl -H 'Bearer " + "z" * 20 + "' https://example.com", 1, 1, "/x", "s1")
                   for i in range(5)]
        rep = friction.Report()
        friction.analyse(entries, rep, 3, 60, examples=2)
        blob = str(rep.items)
        self.assertNotIn("z" * 20, blob)
        self.assertIn("<redacted>", blob)

    def test_no_history_at_all_says_so_instead_of_reporting_nothing(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = friction.main(["--history", "/no/such/history", "--now", str(NOW)])
        self.assertEqual(code, 0)
        self.assertIn("no history was readable", buffer.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=1)
