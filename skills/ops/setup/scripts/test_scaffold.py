#!/usr/bin/env python3
"""Offline tests for the ops scaffold: the shared workspace, the log folder, and the row it writes.

Run: python3 skills/ops/setup/scripts/test_scaffold.py
Writes into a temp folder; no network, no host.
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


def build(d, host="example-host"):
    root = Path(d) / "dx"
    subprocess.run([sys.executable, SCRIPT, "--root", str(root), host],
                   capture_output=True, text=True, check=True)
    return root


def run(root, *args):
    r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), *args],
                       capture_output=True, text=True)
    return r


class HostNameTest(unittest.TestCase):
    def test_case_and_spaces_are_normalised(self):
        self.assertEqual(scaffold.host_name("Intelligent-Bose.Example"), "intelligent-bose.example")
        self.assertEqual(scaffold.host_name(" web one "), "web-one")

    def test_a_name_that_is_not_a_host_is_rejected(self):
        """Every folder is named after this value, so a path segment must never survive it."""
        for bad in ("..", ".", "", "/", "../../escaped", "a/b", "-x", "x-"):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                scaffold.host_name(bad)


class ValueTest(unittest.TestCase):
    def test_a_default_with_an_explanation_reads_as_the_default(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.md"
            p.write_text("- report: pull (what pull means)\n- profile: (unchosen)\n", encoding="utf-8")
            self.assertEqual(scaffold.value(p, "report"), "pull")
            self.assertEqual(scaffold.value(p, "profile"), "")

    def test_a_comma_separated_value_becomes_a_list(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.md"
            p.write_text("- allow_users: root, ops-scan ,ops-admin\n", encoding="utf-8")
            self.assertEqual(scaffold.values(p, "allow_users"), ["root", "ops-scan", "ops-admin"])


class WorkspaceTest(unittest.TestCase):
    def test_the_log_folder_belongs_to_this_theme(self):
        """A shared host folder holds one log folder per theme (decisions/0015)."""
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.assertTrue((root / "machines/example-host/log/ops").is_dir())
            self.assertFalse((root / "machines/example-host/log/dx").exists())

    def test_creating_twice_overwrites_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            (root / "config.md").write_text("- forge: example.com\n", encoding="utf-8")
            build(d)
            self.assertEqual((root / "config.md").read_text(encoding="utf-8"),
                             "- forge: example.com\n")

    def test_check_names_a_section_a_shared_file_is_missing(self):
        """The other theme's setup wrote this file, so it holds none of this theme's sections."""
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            (root / "standards.md").write_text("# Standards\n\n## Every project\n", encoding="utf-8")
            r = run(root, "--check")
            self.assertEqual(r.returncode, 1)
            self.assertIn("## Ops access", r.stdout)

    def test_a_workstation_folder_is_not_this_theme_s_business(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            cfg = root / "machines/example-host/config.md"
            cfg.write_text(cfg.read_text(encoding="utf-8").replace("role: server", "role: workstation"),
                           encoding="utf-8")
            self.assertEqual(run(root, "--check").returncode, 0)

    def test_flags_leave_a_blank_standard_out(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("no standard set", out)
            (root / "standards.md").write_text(
                "# S\n\n## Ops access\n\n- access_paths_min: 2\n- key_min_bits: 3072\n",
                encoding="utf-8")
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("--paths-bar 2", out)
            self.assertIn("--min-key-bits 3072", out)

    def paths(self, root, line):
        cfg = root / "machines/example-host/config.md"
        text = cfg.read_text(encoding="utf-8")
        old = [l for l in text.splitlines() if l.startswith("- access_paths:")][0]
        cfg.write_text(text.replace(old, f"- access_paths: {line}"), encoding="utf-8")

    def test_only_a_dated_way_in_is_counted_as_a_path(self):
        """`access.single-path` decides whether access may change, so it counts proofs, not names."""
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.paths(root, "ops-scan@2026-09-06, ops-admin@2026-09-06, console")
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("--path ops-scan", out)
            self.assertIn("--path ops-admin", out)
            self.assertNotIn("--path console", out)
            self.assertIn("unproved ways in: console", out)

    def test_a_way_in_with_no_date_at_all_leaves_the_check_at_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.paths(root, "ops-scan, console")
            out = run(root, "--flags", "example-host").stdout
            self.assertNotIn("--path ", out)
            self.assertIn("unproved ways in: ops-scan, console", out)

    def test_proved_paths_splits_on_the_date(self):
        self.assertEqual(scaffold.proved_paths(["a@2026-09-06", "b", "c@nope"]),
                         (["a"], ["b", "c@nope"]))

    def services(self, root, line):
        cfg = root / "machines/example-host/config.md"
        text = cfg.read_text(encoding="utf-8")
        old = [l for l in text.splitlines() if l.startswith("- services:")][0]
        cfg.write_text(text.replace(old, f"- services: {line}"), encoding="utf-8")

    def test_flags_turn_the_service_list_into_service_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.services(root, "mailbot=mailbot.service")
            self.assertIn("--service mailbot=mailbot.service",
                          run(root, "--flags", "example-host").stdout)

    def test_a_spec_keeps_its_own_commas_because_the_list_uses_semicolons(self):
        """A comma separated list turned one service into four arguments that named nothing."""
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.services(root, "a=a.service,timer=a.timer,path=/opt/a; b=b.service")
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("--service a=a.service,timer=a.timer,path=/opt/a", out)
            self.assertIn("--service b=b.service", out)
            self.assertEqual(out.count("--service "), 2)


    def line(self, root, key, value):
        cfg = root / "machines/example-host/config.md"
        text = cfg.read_text(encoding="utf-8")
        old = [l for l in text.splitlines() if l.startswith(f"- {key}:")][0]
        cfg.write_text(text.replace(old, f"- {key}: {value}"), encoding="utf-8")

    def test_flags_turn_the_port_list_into_port_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.line(root, "expected_ports", "22/tcp, 443/tcp")
            self.line(root, "panel_ports", "8443/tcp")
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("--expected-port 22/tcp", out)
            self.assertIn("--expected-port 443/tcp", out)
            self.assertIn("--panel-port 8443/tcp", out)

    def test_a_certificate_directory_is_told_from_a_certificate_file(self):
        """A directory passed as a file would be opened and read as one certificate."""
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.line(root, "cert_paths", "/etc/ssl/site.pem, /etc/letsencrypt/live/")
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("--cert /etc/ssl/site.pem", out)
            self.assertIn("--cert-dir /etc/letsencrypt/live/", out)

    def test_the_firewall_kind_comes_from_the_host_and_not_from_a_guess(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.assertNotIn("--fw-kind", run(root, "--flags", "example-host").stdout)
            self.line(root, "firewall", "ufw")
            self.assertIn("--fw-kind ufw", run(root, "--flags", "example-host").stdout)

    def test_flags_turn_the_backup_list_into_backup_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.line(root, "backups", "web=web root,source=/srv/web,copy=store:/web; db=database,source=/var/db")
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("--backup web=web root,source=/srv/web,copy=store:/web", out)
            self.assertIn("--backup db=database,source=/var/db", out)
            self.assertEqual(out.count("--backup "), 2)

    def test_flags_pass_every_recorded_secret_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.line(root, "secret_paths", "/etc/app/token, /etc/ssl/private")
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("--secret /etc/app/token", out)
            self.assertIn("--secret /etc/ssl/private", out)

    def test_a_blank_recovery_standard_leaves_the_script_its_own_default(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.assertNotIn("--rpo-hours", run(root, "--flags", "example-host").stdout)
            (root / "standards.md").write_text(
                "# S\n\n## Ops recovery\n\n- backup_rpo_hours: 12\n- restore_test_days: 30\n",
                encoding="utf-8")
            out = run(root, "--flags", "example-host").stdout
            self.assertIn("--rpo-hours 12", out)
            self.assertIn("--restore-test-days 30", out)


class RowTest(unittest.TestCase):
    def prepare(self, d):
        root = build(d)
        (root / "standards.md").write_text(
            "# S\n\n## Ops profile\n\n- verify_window_days: 7\n- allow_safe: no\n", encoding="utf-8")
        return root

    def add(self, root, *args):
        r = run(root, "--append-row", "--today", "2026-09-07", "example-host", *args)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout

    def week(self, root):
        return (root / "machines/example-host/log/ops/2026-W37.md").read_text(encoding="utf-8")

    def test_a_row_lands_in_this_theme_s_week_file_with_its_trailer(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prepare(d)
            out = self.add(root, "--check-id", "ssh.root-login", "--target", "sshd",
                           "--action", "close direct root login", "--class", "ask",
                           "--then", "1 count", "--status", "applied")
            self.assertIn("Ops-Log: 2026-W37-01", out)
            self.assertIn("| 2026-W37-01 | ssh.root-login |", self.week(root))
            self.assertIn("2026-09-14", self.week(root))

    def test_safe_falls_back_to_confirm_while_the_switch_is_off(self):
        """On a host that serves other people nothing changes without a sentence (decisions/0017)."""
        with tempfile.TemporaryDirectory() as d:
            root = self.prepare(d)
            out = self.add(root, "--check-id", "log.no-retention", "--target", "journald",
                           "--action", "cap the journal", "--class", "safe", "--then", "1 count")
            self.assertIn("runs as confirm", out)
            self.assertIn("| confirm |", self.week(root))

    def test_the_switch_lets_safe_through_when_a_host_turns_it_on(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prepare(d)
            (root / "standards.md").write_text(
                "# S\n\n## Ops profile\n\n- verify_window_days: 7\n- allow_safe: yes\n",
                encoding="utf-8")
            self.add(root, "--check-id", "log.no-retention", "--target", "journald",
                     "--action", "cap the journal", "--class", "safe", "--then", "1 count")
            self.assertIn("| safe |", self.week(root))

    def test_a_measure_without_a_known_unit_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prepare(d)
            r = run(root, "--append-row", "example-host", "--check-id", "ssh.root-login",
                    "--target", "sshd", "--action", "x", "--class", "ask", "--then", "a few")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("not a measure", r.stdout + r.stderr)

    def test_a_class_outside_the_three_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prepare(d)
            r = run(root, "--append-row", "example-host", "--check-id", "ssh.root-login",
                    "--target", "sshd", "--action", "x", "--class", "yolo", "--then", "1 count")
            self.assertNotEqual(r.returncode, 0)

    def test_ids_continue_within_the_week(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prepare(d)
            self.add(root, "--check-id", "ssh.root-login", "--target", "sshd", "--action", "a",
                     "--class", "ask", "--then", "1 count")
            out = self.add(root, "--check-id", "key.weak", "--target", "root", "--action", "b",
                           "--class", "ask", "--then", "2 count")
            self.assertIn("id: 2026-W37-02", out)

    def test_a_pipe_and_a_line_break_stay_inside_the_cell(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prepare(d)
            self.add(root, "--check-id", "unit.unhardened", "--target", "a | b",
                     "--action", "one\ntwo", "--class", "ask", "--then", "3 count")
            row = [l for l in self.week(root).splitlines() if l.startswith("| 2026-W37-01")][0]
            self.assertIn("a \\| b", row)
            self.assertEqual(row.count(" | "), 9)

    def test_due_prints_the_then_value_a_verdict_is_measured_from(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prepare(d)
            self.add(root, "--check-id", "ssh.root-login", "--target", "sshd", "--action", "a",
                     "--class", "ask", "--then", "1 count", "--status", "applied")
            out = run(root, "--due", "--today", "2026-09-20", "example-host").stdout
            self.assertIn("then 1 count", out)
            self.assertIn("1 due", out)


class RemoteQuotingTest(unittest.TestCase):
    """remote.sh joins its arguments into one string for the remote shell, so it quotes them.

    The remote shell is whatever login shell the reading account carries, which is not always
    bash. Every argument must come back out of `sh -c` exactly as it went in.
    """

    RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote.sh")

    def dry_run(self, *args):
        r = subprocess.run(["bash", self.RUNNER, "--to", "u@h", "--dry-run", *args],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_every_argument_survives_a_posix_shell(self):
        for arg in ("a b", "it's", "a\tb", "a\nb", "x$y", "`id`", "back\\slash", 'p"q'):
            with self.subTest(arg=arg):
                # Read the whole command, not one line of it: a quoted newline is part of it.
                out = self.dry_run(SCRIPT, arg)
                quoted = out.split('python3 "$f" ', 1)[1].rsplit(" --json", 1)[0]
                back = subprocess.run(["/bin/sh", "-c", "printf '%s' " + quoted],
                                      capture_output=True, text=True)
                self.assertEqual(back.returncode, 0, back.stderr)
                self.assertEqual(back.stdout, arg)

    def test_a_fetch_path_is_quoted_the_same_way(self):
        self.assertIn("cat -- '/var/o p/x.json'", self.dry_run("--fetch", "/var/o p/x.json"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
