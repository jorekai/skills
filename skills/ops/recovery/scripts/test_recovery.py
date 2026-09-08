#!/usr/bin/env python3
"""Offline tests for recovery.py: copies, secrets, units, and what the journal keeps.

Run: python3 skills/ops/recovery/scripts/test_recovery.py
Uses a temporary filesystem root, a temporary git repository, and captured unit and journald
files. No systemd, no network, and no secret is ever written into the output it checks.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recovery  # noqa: E402

SCRIPT = os.path.abspath(recovery.__file__)
NOW = "2026-09-08T12:00:00"


def write(path, text="x\n", mode=None):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if mode is not None:
        os.chmod(p, mode)
    return p


def age(path, days):
    """A file written `days` ago, so a window has something to be past."""
    when = time.time() - days * 86400
    os.utime(path, (when, when))


def run(root, extra=(), backups=(), secrets=()):
    args = [sys.executable, SCRIPT, "--json", "--now", NOW, "--root", str(root)]
    for b in backups:
        args += ["--backup", b]
    for s in secrets:
        args += ["--secret", s]
    r = subprocess.run(args + list(extra), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def item(out, cid, level=None):
    for i in out["items"]:
        if i["id"] == cid and (level is None or i["level"] == level):
            return i
    raise AssertionError(f"no {cid} ({level}) in {[(i['id'], i['level']) for i in out['items']]}")


class SpecTest(unittest.TestCase):
    def test_a_target_may_carry_several_copies(self):
        s = recovery.parse_spec("web=web root,source=/srv/web,copy=/backup/web,copy=off:/w")
        self.assertEqual(s["name"], "web")
        self.assertEqual(s["copies"], ["/backup/web", "off:/w"])

    def test_a_spec_without_a_label_is_refused(self):
        with self.assertRaises(SystemExit):
            recovery.parse_spec("web")

    def test_an_unknown_field_is_refused_rather_than_ignored(self):
        """A typo that is silently dropped turns a check off without saying so."""
        with self.assertRaises(SystemExit):
            recovery.parse_spec("web=web,sorce=/srv/web")

    def test_a_copy_off_this_host_is_told_from_a_path_on_it(self):
        self.assertTrue(recovery.is_remote("backup@store:/srv/web"))
        self.assertTrue(recovery.is_remote("s3://bucket/web"))
        self.assertFalse(recovery.is_remote("/backup/web"))
        self.assertFalse(recovery.is_remote("relative/backup"))


class BackupTest(unittest.TestCase):
    def test_a_target_with_no_copy_anywhere_fails(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "srv/web/index.html")
            out = run(d, backups=["web=web root,source=/srv/web"])
            self.assertEqual(item(out, "backup.missing", "FAIL")["measure"]["value"], 1)

    def test_a_copy_that_exists_passes_and_measures_zero(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "backup/web/index.html")
            out = run(d, backups=["web=web root,source=/srv/web,copy=/backup/web"])
            self.assertEqual(item(out, "backup.missing", "PASS")["measure"]["value"], 0)

    def test_a_copy_older_than_the_window_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            p = write(Path(d) / "backup/web/dump.sql")
            age(p, 4)
            out = run(d, backups=["web=web root,source=/srv/web,copy=/backup/web"],
                      extra=["--rpo-hours", "24"])
            self.assertEqual(item(out, "backup.stale", "FAIL")["measure"]["value"], 1)

    def test_the_newest_file_in_a_directory_dates_the_copy(self):
        """A directory's own time says nothing: a copy written into it leaves that time behind."""
        with tempfile.TemporaryDirectory() as d:
            old = write(Path(d) / "backup/web/old.sql")
            age(old, 9)
            write(Path(d) / "backup/web/new.sql")
            out = run(d, backups=["web=web root,source=/srv/web,copy=/backup/web"])
            self.assertEqual(item(out, "backup.stale", "PASS")["measure"]["value"], 0)

    def test_every_copy_on_this_host_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "backup/web/dump.sql")
            out = run(d, backups=["web=web root,source=/srv/web,copy=/backup/web"])
            self.assertEqual(item(out, "backup.offsite", "FAIL")["measure"]["value"], 1)

    def test_a_copy_off_this_host_settles_offsite_and_is_named_as_undatable(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, backups=["web=web root,source=/srv/web,copy=backup@store:/srv/web"])
            self.assertEqual(item(out, "backup.offsite", "PASS")["measure"]["value"], 0)
            self.assertEqual(item(out, "backup.stale", "INFO")["data"][0]["target"], "web")

    def test_a_target_never_restored_is_untested(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "backup/web/dump.sql")
            out = run(d, backups=["web=web root,source=/srv/web,copy=/backup/web"])
            got = item(out, "backup.untested", "WARN")
            self.assertEqual(got["measure"]["value"], 1)
            self.assertEqual(got["data"][0]["value"], "never")

    def test_a_restore_test_inside_the_window_passes(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "backup/web/dump.sql")
            out = run(d, backups=["web=web,source=/srv/web,copy=/backup/web,tested=2026-08-20"],
                      extra=["--restore-test-days", "90"])
            self.assertEqual(item(out, "backup.untested", "PASS")["measure"]["value"], 0)

    def test_no_target_at_all_is_a_note_and_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d)
            self.assertEqual(item(out, "backup.missing", "INFO")["measure"], None)


class SecretTest(unittest.TestCase):
    def test_a_secret_the_standards_name_and_the_host_lacks(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, secrets=["/etc/app/token"])
            self.assertEqual(item(out, "secret.missing", "WARN")["measure"]["value"], 1)

    def test_a_secret_readable_by_others_is_a_finding_with_its_mode(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/app/token", mode=0o644)
            out = run(d, secrets=["/etc/app/token"])
            got = item(out, "secret.mode", "FAIL")
            self.assertEqual(got["measure"]["value"], 1)
            self.assertEqual(got["data"][0]["value"], "644")

    def test_a_secret_only_its_owner_can_read_passes(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/app/token", mode=0o600)
            out = run(d, secrets=["/etc/app/token"])
            self.assertEqual(item(out, "secret.mode", "PASS")["measure"]["value"], 0)

    def test_a_directory_contributes_every_file_inside_it(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/app/keys/a", mode=0o644)
            write(Path(d) / "etc/app/keys/b", mode=0o600)
            out = run(d, secrets=["/etc/app/keys"])
            self.assertEqual(item(out, "secret.mode", "FAIL")["measure"]["value"], 1)

    def test_a_secret_in_a_work_tree_that_does_not_ignore_it(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "srv/app"
            write(repo / "app.py")
            subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
            write(repo / ".env", mode=0o600)
            out = run(d, secrets=["/srv/app/.env"])
            got = item(out, "secret.in-repo", "FAIL")
            self.assertEqual(got["measure"]["value"], 1)
            self.assertIn("not ignored", got["data"][0]["value"])

    def test_a_secret_the_repository_ignores_is_no_finding(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "srv/app"
            subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
            write(repo / ".gitignore", ".env\n")
            write(repo / ".env", mode=0o600)
            out = run(d, secrets=["/srv/app/.env"])
            self.assertEqual(item(out, "secret.in-repo", "PASS")["measure"]["value"], 0)


class UnitTest(unittest.TestCase):
    def test_a_credential_passed_as_an_environment_variable_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/system/app.service",
                  "[Service]\nEnvironment=DB_PASSWORD=hunter2\nExecStart=/usr/bin/app\n")
            out = run(d)
            got = item(out, "secret.plaintext", "FAIL")
            self.assertEqual(got["measure"]["value"], 1)
            self.assertEqual(got["data"][0]["value"], "DB_PASSWORD")

    def test_the_value_of_a_credential_never_reaches_the_output(self):
        """The name is the finding. A pass that copies the value moves the secret into the audit."""
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/system/app.service",
                  "[Service]\nEnvironment=API_TOKEN=hunter2\n")
            out = run(d)
            self.assertNotIn("hunter2", json.dumps(out))

    def test_the_verb_agrees_with_the_count_in_front_of_it(self):
        """One credential reaches a service, two credentials reach it."""
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/system/app.service",
                  "[Service]\nEnvironment=API_TOKEN=a\n")
            self.assertIn("1 credential reaches", item(run(d), "secret.plaintext", "FAIL")["message"])
            write(Path(d) / "etc/systemd/system/app.service",
                  "[Service]\nEnvironment=API_TOKEN=a\nEnvironment=DB_PASSWORD=b\n")
            self.assertIn("2 credentials reach", item(run(d), "secret.plaintext", "FAIL")["message"])

    def test_a_unit_that_loads_an_environment_file_is_a_note(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/system/app.service",
                  "[Service]\nEnvironmentFile=-/etc/app/env\n")
            out = run(d)
            self.assertEqual(item(out, "secret.plaintext", "INFO")["data"][0]["value"], "/etc/app/env")

    def test_a_variable_that_names_no_credential_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/system/app.service",
                  "[Service]\nEnvironment=LANG=C.UTF-8\n")
            out = run(d)
            self.assertEqual(item(out, "secret.plaintext", "PASS")["measure"]["value"], 0)


class JournalTest(unittest.TestCase):
    def test_neither_bound_set_counts_two(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/journald.conf", "[Journal]\nStorage=persistent\n")
            out = run(d)
            self.assertEqual(item(out, "log.no-retention", "WARN")["measure"]["value"], 2)

    def test_both_bounds_set_pass(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/journald.conf",
                  "[Journal]\nStorage=persistent\nMaxRetentionSec=30d\nSystemMaxUse=2G\n")
            out = run(d)
            self.assertEqual(item(out, "log.no-retention", "PASS")["measure"]["value"], 0)

    def test_a_drop_in_is_read_beside_the_main_file(self):
        """A value set in journald.conf.d is the value the host runs, so a pass that reads only
        the main file reports a default nobody is running."""
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/journald.conf", "[Journal]\nStorage=persistent\n")
            write(Path(d) / "etc/systemd/journald.conf.d/10-ops.conf",
                  "[Journal]\nMaxRetentionSec=30d\nSystemMaxUse=2G\n")
            out = run(d)
            got = item(out, "log.no-retention", "PASS")
            self.assertIn("10-ops.conf", got["message"])

    def test_a_retention_of_zero_is_named_as_deletion_by_size_alone(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/journald.conf",
                  "[Journal]\nStorage=persistent\nMaxRetentionSec=0\nSystemMaxUse=2G\n")
            out = run(d)
            self.assertEqual(item(out, "log.no-retention", "INFO")["data"][0]["target"],
                             "MaxRetentionSec")

    def test_a_volatile_journal_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/systemd/journald.conf",
                  "[Journal]\nMaxRetentionSec=30d\nSystemMaxUse=2G\n")
            out = run(d)
            notes = [i for i in out["items"] if i["id"] == "log.no-retention" and i["level"] == "INFO"]
            self.assertTrue(any("volatile" in n["message"] for n in notes))

    def test_a_journal_over_its_share_measures_the_points_over(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "var/log/journal/abc/system.journal", "x" * 300)
            out = run(d, extra=["--filesystem-bytes", "1000", "--log-share-percent", "10"])
            self.assertEqual(item(out, "log.growth", "WARN")["measure"]["value"], 20.0)

    def test_a_file_that_is_not_a_journal_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "var/log/journal/abc/system.journal", "x" * 50)
            write(Path(d) / "var/log/journal/abc/other.txt", "x" * 900)
            out = run(d, extra=["--filesystem-bytes", "1000", "--log-share-percent", "10"])
            self.assertEqual(item(out, "log.growth", "PASS")["measure"]["value"], 0)


class TimeTest(unittest.TestCase):
    def test_journald_time_values_parse_into_seconds(self):
        self.assertEqual(recovery.seconds("30d"), 30 * 86400)
        self.assertEqual(recovery.seconds("2 week"), 2 * 604800)
        self.assertEqual(recovery.seconds("900"), 900)
        self.assertEqual(recovery.seconds("0"), 0)

    def test_a_value_in_no_unit_this_table_knows_is_no_time(self):
        self.assertIsNone(recovery.seconds("30 fortnights"))


class ReportTest(unittest.TestCase):
    def test_every_measured_id_carries_the_unit_the_table_names(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, backups=["web=web,source=/srv/web"], secrets=["/etc/app/token"])
            for i in out["items"]:
                if i["measure"]:
                    self.assertEqual(i["measure"]["unit"], recovery.MEASURES[i["id"]])

    def test_the_console_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW],
                               capture_output=True, text=True)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
