#!/usr/bin/env python3
"""Offline tests for availability.py: unit state, timers, hardening options, deploy paths.

Run: python3 skills/ops/availability/scripts/test_availability.py
Uses captured `systemctl show` output and a temp git repository; no systemd, no network.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import availability  # noqa: E402

SCRIPT = os.path.abspath(availability.__file__)
NOW = "2026-09-07T12:00:00"


def unit_show(directory, unit, **fields):
    """One captured `systemctl show <unit>` file."""
    p = Path(directory) / f"{unit}.show"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"{k}={v}" for k, v in fields.items()) + "\n", encoding="utf-8")
    return p


def run(show_dir, *services, extra=(), root=None):
    args = [sys.executable, SCRIPT, "--json", "--now", NOW, "--show-dir", str(show_dir)]
    if root:
        args += ["--root", str(root)]
    for s in services:
        args += ["--service", s]
    r = subprocess.run(args + list(extra), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def item(out, cid, level=None):
    for i in out["items"]:
        if i["id"] == cid and (level is None or i["level"] == level):
            return i
    raise AssertionError(f"no {cid} ({level}) in {[i['id'] for i in out['items']]}")


class SpecTest(unittest.TestCase):
    def test_a_spec_carries_the_optional_fields(self):
        s = availability.parse_spec("mailbot=mailbot.service,timer=mailbot.timer,path=/opt/x")
        self.assertEqual(s["name"], "mailbot")
        self.assertEqual(s["unit"], "mailbot.service")
        self.assertEqual(s["path"], "/opt/x")

    def test_a_spec_without_a_unit_is_refused(self):
        with self.assertRaises(SystemExit):
            availability.parse_spec("mailbot")

    def test_an_unknown_field_is_refused_rather_than_ignored(self):
        """A typo that is silently dropped turns a check off without saying so."""
        with self.assertRaises(SystemExit):
            availability.parse_spec("mailbot=mailbot.service,pat=/opt/x")


class ParseTest(unittest.TestCase):
    def test_a_systemd_timestamp_is_read_without_its_zone(self):
        got = availability.timestamp("Mon 2026-09-08 06:45:00 CEST")
        self.assertEqual(got.isoformat(), "2026-09-08T06:45:00")

    def test_an_empty_timestamp_is_no_time(self):
        self.assertIsNone(availability.timestamp(""))
        self.assertIsNone(availability.timestamp("n/a"))

    def test_a_repository_host_is_read_from_both_url_shapes(self):
        self.assertEqual(availability.repo_host("git@github-mailbot:org/x.git"), "github-mailbot")
        self.assertEqual(availability.repo_host("ssh://git@example.com/org/x.git"), "example.com")

    def test_a_host_alias_without_an_identity_file_is_not_ready(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config"
            p.write_text("Host a\n  IdentityFile ~/.ssh/a\n\nHost b\n  User git\n", encoding="utf-8")
            hosts = availability.ssh_hosts(p)
            self.assertTrue(hosts["a"])
            self.assertFalse(hosts["b"])


class ChecksTest(unittest.TestCase):
    def test_an_inactive_unit_is_down_and_an_active_one_measures_zero(self):
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="inactive", Result="success", NRestarts="0")
            out = run(d, "mailbot=mailbot.service,path=/")
            self.assertEqual(item(out, "service.down")["level"], "FAIL")
            self.assertEqual(item(out, "service.down")["measure"]["value"], 1)
            unit_show(d, "mailbot.service", ActiveState="active", Result="success", NRestarts="0")
            out = run(d, "mailbot=mailbot.service,path=/")
            self.assertEqual(item(out, "service.down")["level"], "PASS")
            self.assertEqual(item(out, "service.down")["measure"]["value"], 0)

    def test_a_failed_unit_is_not_also_counted_as_down(self):
        """One state, one finding: a failed unit and a stopped one need different fixes."""
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="failed", Result="exit-code", NRestarts="0")
            out = run(d, "mailbot=mailbot.service,path=/")
            self.assertEqual(item(out, "service.failed")["measure"]["value"], 1)
            self.assertEqual(item(out, "service.down")["measure"]["value"], 0)

    def test_restarts_measure_only_what_is_over_the_bar(self):
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="active", Result="success", NRestarts="7")
            out = run(d, "mailbot=mailbot.service,path=/", extra=["--restart-bar", "3"])
            self.assertEqual(item(out, "service.restarts")["measure"]["value"], 4)

    def test_a_timer_that_is_not_enabled_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="active", Result="success", NRestarts="0")
            unit_show(d, "mailbot.timer", UnitFileState="disabled", ActiveState="inactive")
            out = run(d, "mailbot=mailbot.service,timer=mailbot.timer,path=/")
            self.assertEqual(item(out, "timer.disabled")["measure"]["value"], 1)

    def test_a_timer_past_its_next_elapse_beyond_the_grace_window_is_missed(self):
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="active", Result="success", NRestarts="0")
            unit_show(d, "mailbot.timer", UnitFileState="enabled", ActiveState="active",
                      NextElapseUSecRealtime="Sun 2026-09-07 06:45:00 UTC")
            out = run(d, "mailbot=mailbot.service,timer=mailbot.timer,path=/")
            self.assertEqual(item(out, "timer.missed")["measure"]["value"], 1)
            out = run(d, "mailbot=mailbot.service,timer=mailbot.timer,path=/",
                      extra=["--missed-grace-seconds", "99999"])
            self.assertEqual(item(out, "timer.missed")["level"], "PASS")

    def test_a_required_option_that_is_exempt_stops_being_a_finding(self):
        """An option that breaks a service is recorded once, with its reason, in standards.md."""
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="active", Result="success", NRestarts="0",
                      ProtectSystem="full", NoNewPrivileges="no")
            args = ["--require-option", "ProtectSystem=strict",
                    "--require-option", "NoNewPrivileges=yes"]
            out = run(d, "mailbot=mailbot.service,path=/", extra=args)
            self.assertEqual(item(out, "unit.unhardened")["measure"]["value"], 2)
            out = run(d, "mailbot=mailbot.service,path=/",
                      extra=args + ["--except", "mailbot.service:NoNewPrivileges"])
            self.assertEqual(item(out, "unit.unhardened")["measure"]["value"], 1)

    def test_a_service_without_a_deploy_path_is_absent(self):
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="active", Result="success", NRestarts="0")
            out = run(d, "mailbot=mailbot.service")
            self.assertEqual(item(out, "deploy.absent")["measure"]["value"], 1)

    def test_a_repository_host_without_an_identity_file_has_no_deploy_key(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "host"
            (root / "root/.ssh").mkdir(parents=True)
            (root / "root/.ssh/config").write_text("Host other\n  IdentityFile ~/.ssh/o\n",
                                                   encoding="utf-8")
            shows = Path(d) / "shows"
            unit_show(shows, "mailbot.service", ActiveState="active", Result="success", NRestarts="0")
            out = run(shows, "mailbot=mailbot.service,path=/,repo=git@github-mailbot:org/x.git",
                      root=root)
            self.assertEqual(item(out, "deploy.no-key")["measure"]["value"], 1)
            (root / "root/.ssh/config").write_text(
                "Host github-mailbot\n  IdentityFile ~/.ssh/deploy\n", encoding="utf-8")
            out = run(shows, "mailbot=mailbot.service,path=/,repo=git@github-mailbot:org/x.git",
                      root=root)
            self.assertEqual(item(out, "deploy.no-key")["level"], "PASS")

    def test_a_missing_unit_state_is_a_note_and_measures_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, "mailbot=mailbot.service,path=/")
            note = item(out, "service.down", level="INFO")
            self.assertIsNone(note["measure"])


class CodeBehindTest(unittest.TestCase):
    def repo(self, d):
        r = Path(d) / "opt" / "app"
        r.mkdir(parents=True)
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")
        subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True, env=env)
        shas = []
        for n in range(3):
            (r / "f").write_text(str(n), encoding="utf-8")
            subprocess.run(["git", "-C", str(r), "add", "f"], check=True, env=env)
            subprocess.run(["git", "-C", str(r), "commit", "-qm", f"c{n}"], check=True, env=env)
            shas.append(subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"],
                                       capture_output=True, text=True, check=True).stdout.strip())
        subprocess.run(["git", "-C", str(r), "checkout", "-q", shas[0]], check=True, env=env)
        return shas

    def test_the_distance_to_the_named_commit_is_counted(self):
        with tempfile.TemporaryDirectory() as d:
            shas = self.repo(d)
            shows = Path(d) / "shows"
            unit_show(shows, "app.service", ActiveState="active", Result="success", NRestarts="0")
            out = run(shows, f"app=app.service,path=/opt/app,commit={shas[2]}", root=Path(d))
            self.assertEqual(item(out, "code.behind")["measure"]["value"], 2)

    def test_a_commit_this_clone_does_not_hold_is_a_note_not_a_number(self):
        with tempfile.TemporaryDirectory() as d:
            self.repo(d)
            shows = Path(d) / "shows"
            unit_show(shows, "app.service", ActiveState="active", Result="success", NRestarts="0")
            out = run(shows, "app=app.service,path=/opt/app,commit=" + "0" * 40, root=Path(d))
            self.assertEqual(item(out, "code.behind", level="INFO")["measure"], None)


class ContractTest(unittest.TestCase):
    def test_measures_prints_one_id_and_unit_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--measures"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, availability.MEASURES)

    def test_without_a_service_the_pass_refuses_rather_than_reporting_nothing(self):
        r = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--service", r.stderr)

    def test_the_counting_line_is_a_bar_and_the_cost_stands_in_its_own_column(self):
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="inactive", Result="success", NRestarts="0")
            r = subprocess.run([sys.executable, SCRIPT, "--show-dir", d, "--now", NOW,
                                "--service", "mailbot=mailbot.service,path=/"],
                               capture_output=True, text=True)
            self.assertRegex(r.stdout, r"\n\d+ FAIL · \d+ WARN · \d+ notes? · \d+ passed\n")
            self.assertRegex(r.stdout, r"\nFAIL  service\.down {18}1 unit\n")
            self.assertNotIn("(costs", r.stdout)

    def test_the_text_report_ends_on_a_next_step(self):
        with tempfile.TemporaryDirectory() as d:
            unit_show(d, "mailbot.service", ActiveState="inactive", Result="success", NRestarts="0")
            r = subprocess.run([sys.executable, SCRIPT, "--show-dir", d, "--now", NOW,
                                "--service", "mailbot=mailbot.service,path=/"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured against", r.stdout)
            self.assertIn("\nnext  ", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
