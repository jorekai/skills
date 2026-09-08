#!/usr/bin/env python3
"""Offline tests for the ops status: stage, parked rows, unknown ids, and the role filter.

Run: python3 skills/ops/and-now/scripts/test_status.py
Builds a workspace in a temp folder; no host, no network.
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
import status  # noqa: E402

SCRIPT = os.path.abspath(status.__file__)
TODAY = dt.date(2026, 9, 7)
HEAD = ("## Actions\n\n"
        "| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n")


def workspace(d, role="server", access="ops-scan@h", plane="plesk 18.0", profile="hardened",
              paths="ops-admin, console"):
    root = Path(d) / "dx"
    base = root / "machines" / "example-host"
    (base / "audits").mkdir(parents=True)
    (base / "log" / "ops").mkdir(parents=True)
    (base / "proposals").mkdir(parents=True)
    (base / "config.md").write_text(
        f"# h\n\n## Where things live\n\n- role: {role}\n- control_plane: {plane}\n"
        f"- access: {access}\n- access_paths: {paths}\n", encoding="utf-8")
    (root / "standards.md").write_text(
        f"# S\n\n## Ops profile\n\n- profile: {profile}\n- verify_window_days: 7\n", encoding="utf-8")
    return root, base


def rows(base, *lines):
    p = base / "log" / "ops" / "2026-W36.md"
    p.write_text("# 2026-W36\n\n" + HEAD + "".join(lines), encoding="utf-8")


def row(rid, check, status_="todo", after="", applied=""):
    return (f"| {rid} | {check} | host | do a thing | ask | 1 count | {status_} "
            f"| {applied} | {after} |  |\n")


def audit(base, kind, date, items):
    (base / "audits" / f"{date}-{kind}.json").write_text(
        json.dumps({"tool": kind, "items": items}), encoding="utf-8")


class StageTest(unittest.TestCase):
    def test_an_empty_workspace_is_still_in_setup(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d, access="", plane="", profile="", paths="")
            stage, now, _ = status.decide(status.read_host(root, "example-host", TODAY), TODAY)
            self.assertEqual(stage, "setup")
            self.assertTrue(any("no `access` is recorded" in s for s in now))

    def test_a_host_with_work_is_past_setup_even_when_setup_is_unfinished(self):
        """Unfinished setup is an item, never a gate (decisions/0010, same rule here)."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d, profile="")
            rows(base, row("2026-W36-01", "ssh.root-login"))
            stage, now, _ = status.decide(status.read_host(root, "example-host", TODAY), TODAY)
            self.assertNotEqual(stage, "setup")
            self.assertTrue(any("no profile is chosen" in s for s in now))

    def test_without_an_audit_the_first_step_is_access(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            rows(base, row("2026-W36-01", "ssh.root-login"))
            stage, now, _ = status.decide(status.read_host(root, "example-host", TODAY), TODAY)
            self.assertEqual(stage, "measure")
            self.assertIn("jorekai-ops:access", now[0])


class RowTest(unittest.TestCase):
    def test_a_row_past_its_verify_date_outranks_everything(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            rows(base, row("2026-W36-01", "ssh.root-login", "applied", "2026-09-01", "2026-08-25"))
            s = status.read_host(root, "example-host", TODAY)
            self.assertEqual(len(s["due"]), 1)
            _, now, _ = status.decide(s, TODAY)
            self.assertIn("jorekai-ops:grade", now[0])

    def test_an_id_this_theme_does_not_own_is_named_as_such(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            rows(base, row("2026-W36-01", "repo.access"))
            s = status.read_host(root, "example-host", TODAY)
            self.assertEqual([r["check"] for r in s["unknown"]], ["repo.access"])
            _, now, _ = status.decide(s, TODAY)
            self.assertTrue(any("does not own" in step for step in now))

    def test_an_id_whose_tool_has_not_shipped_is_parked_not_broken(self):
        """A row waiting for a release is not the same as a row nobody can ever measure."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            rows(base, row("2026-W36-01", "pkg.security"))
            s = status.read_host(root, "example-host", TODAY)
            self.assertEqual([r["check"] for r in s["parked"]], ["pkg.security"])
            self.assertEqual(s["unknown"], [])
            _, now, _ = status.decide(s, TODAY)
            self.assertTrue(any("has not shipped" in step for step in now))

    def test_a_parked_row_is_never_due_for_a_verdict(self):
        """Nothing recomputes it, so naming it as gradeable sends the reader to a refusal."""
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            rows(base, row("2026-W36-01", "tls.expired", "applied", "2026-09-01", "2026-08-25"),
                 row("2026-W36-02", "key.orphan", "applied", "2026-09-01", "2026-08-25"))
            s = status.read_host(root, "example-host", TODAY)
            self.assertEqual([r["id"] for r in s["due"]], ["2026-W36-02"])
            _, now, _ = status.decide(s, TODAY)
            grade_step = [step for step in now if step.startswith("grade ")][0]
            self.assertIn("2026-W36-02", grade_step)
            self.assertNotIn("2026-W36-01", grade_step)

    def test_a_parked_row_does_not_set_the_next_dated_event(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            rows(base, row("2026-W36-01", "tls.expired", "applied", "2099-01-01", "2026-09-01"))
            self.assertIsNone(status.read_host(root, "example-host", TODAY)["next_verify"])

    def test_a_measured_id_is_neither_parked_nor_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            rows(base, row("2026-W36-01", "timer.disabled"))
            s = status.read_host(root, "example-host", TODAY)
            self.assertEqual(s["parked"], [])
            self.assertEqual(s["unknown"], [])


class AuditTest(unittest.TestCase):
    def test_failing_ids_come_in_ladder_order_not_in_audit_order(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "availability", "2026-09-06", [{"id": "code.behind", "level": "FAIL"}])
            audit(base, "access", "2026-09-06", [{"id": "access.single-path", "level": "FAIL"}])
            _, now, _ = status.decide(status.read_host(root, "example-host", TODAY), TODAY)
            self.assertIn("access.single-path", now[0])

    def test_an_audit_older_than_the_bar_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "access", "2026-01-01", [])
            _, now, _ = status.decide(status.read_host(root, "example-host", TODAY), TODAY)
            self.assertTrue(any("moved on" in step for step in now))

    def test_without_an_access_audit_nothing_may_change_access(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "availability", "2026-09-06", [])
            _, now, _ = status.decide(status.read_host(root, "example-host", TODAY), TODAY)
            self.assertTrue(any("nothing may change access" in step for step in now))


class EndToEndTest(unittest.TestCase):
    def test_a_workstation_is_skipped_and_says_why(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d, role="workstation")
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root),
                                "--today", "2026-09-07"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("role: server", r.stdout)

    def test_a_named_host_is_reported_even_when_it_is_not_a_server(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d, role="workstation")
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "example-host",
                                "--today", "2026-09-07"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("does not say `role: server`", r.stdout)

    def test_a_path_instead_of_a_folder_name_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = workspace(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "../escaped"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

    def test_the_report_names_the_stage_and_the_next_steps(self):
        with tempfile.TemporaryDirectory() as d:
            root, base = workspace(d)
            audit(base, "access", "2026-09-06", [{"id": "ssh.root-login", "level": "FAIL"}])
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root),
                                "--today", "2026-09-07"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("stage  measure", r.stdout)
            self.assertIn("ssh.root-login", r.stdout)

    def test_every_ladder_id_names_a_skill(self):
        """An id with no owner is a finding nobody can act on."""
        for cid in status.LADDER:
            self.assertTrue(status.skill_for(cid), cid)


if __name__ == "__main__":
    unittest.main(verbosity=1)
