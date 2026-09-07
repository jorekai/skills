#!/usr/bin/env python3
"""Offline tests for status.py: one fake workspace walked through every stage of the loop.

Run: python3 skills/dx/and-now/scripts/test_status.py
Uses setup/scripts/scaffold.py for the folders so the templates stay the single source of truth.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAFFOLD = HERE.parent.parent / "setup" / "scripts" / "scaffold.py"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status  # noqa: E402

TODAY = dt.date(2026, 9, 5)
MACHINE = "example-machine"
ROW = ("| {id} | {check} | {target} | {action} | {cls} | {then} | {st} | {applied} | {after} | |")


class Workspace:
    def __init__(self, d):
        self.root = Path(d) / "dx"
        subprocess.run([sys.executable, str(SCAFFOLD), "--root", str(self.root), MACHINE],
                       capture_output=True, text=True, check=True)
        self.base = self.root / "machines" / MACHINE

    def set_key(self, relpath, key, val):
        """Replace a template placeholder in place, the way a person filling the file does."""
        p = self.root / relpath
        text = re.sub(rf"^- {re.escape(key)}:.*$", f"- {key}: {val}", p.read_text(), count=1, flags=re.M)
        p.write_text(text)

    def machine_filled(self):
        self.set_key(f"machines/{MACHINE}/config.md", "project_roots", "~/code")

    def standards_filled(self):
        self.set_key("standards.md", "verify_window_days", "14")

    def config_filled(self):
        self.set_key("config.md", "forge", "example.com")

    def audit(self, name="2026-09-01-repos.json", fail=0, ids=(), tool="repos"):
        items = [{"id": i, "level": "FAIL", "message": i} for i in ids]
        (self.base / "audits" / name).write_text(json.dumps(
            {"tool": tool, "target": MACHINE, "counts": {"FAIL": fail, "WARN": 0}, "items": items}))

    def rows(self, *rows):
        subprocess.run([sys.executable, str(SCAFFOLD), "--root", str(self.root), MACHINE,
                        "--log", "--today", TODAY.isoformat()], capture_output=True, text=True, check=True)
        p = self.base / "log" / "dx" / "2026-W36.md"
        p.write_text(p.read_text() + "\n".join(rows) + "\n")

    def read(self):
        return status.read_machine(self.root, MACHINE, TODAY)

    def decide(self):
        return status.decide(self.read(), TODAY)


class StageTest(unittest.TestCase):
    def test_a_fresh_workspace_is_setup_with_one_item(self):
        with tempfile.TemporaryDirectory() as d:
            stage, now, _ = Workspace(d).decide()
            self.assertEqual(stage, "setup")
            self.assertEqual(len(now), 1)
            self.assertIn("jorekai-dx:setup", now[0])

    def test_setup_items_are_listed_not_gated_once_the_loop_started(self):
        """A machine with an audit is in the loop; its open setup work is an item, not a wall."""
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.audit()
            stage, now, _ = w.decide()
            self.assertNotEqual(stage, "setup")
            self.assertTrue(any("standards.md is still the template" in i for i in now))

    def test_no_audit_yet_asks_for_a_measurement(self):
        """Setup is complete and nothing has measured yet: the machine is unknown, not unset."""
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.config_filled()
            stage, now, _ = w.decide()
            self.assertEqual(stage, "measure")
            self.assertIn("nothing has measured this machine yet", now[0])
            self.assertIn("jorekai-dx:repos", now[0])

    def test_a_row_past_its_verify_date_outranks_the_audit(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit(fail=2, ids=("git.dirty", "git.unpushed"))
            w.rows(ROW.format(id="2026-W36-01", check="disk.cache", target="~/x", action="cleared",
                              cls="safe", then="41", st="applied", applied="2026-08-20", after="2026-09-03"))
            _, now, _ = w.decide()
            self.assertIn("past their verify date", now[0])
            self.assertIn("`git.dirty` still fails", now[1])

    def test_a_future_verify_date_becomes_the_then_line(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit()
            w.rows(ROW.format(id="2026-W36-01", check="disk.cache", target="~/x", action="cleared",
                              cls="safe", then="41", st="applied", applied="2026-09-02", after="2026-09-16"))
            _, now, then = w.decide()
            self.assertEqual(then, ["2026-09-16: first verify date reached, "
                                    "`jorekai-dx:grade` settles the row it belongs to"])
            self.assertFalse(any("past their verify date" in i for i in now))

    def test_an_open_row_and_a_proposal_are_both_listed(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit()
            w.rows(ROW.format(id="2026-W36-01", check="git.stale-branch", target="example-app",
                              action="delete four merged branches", cls="confirm", then="4", st="todo",
                              applied="", after=""))
            (w.base / "proposals" / "shell-alias.md").write_text("# idea\n")
            _, now, _ = w.decide()
            self.assertTrue(any("open row 2026-W36-01" in i for i in now))
            self.assertTrue(any("proposals/shell-alias.md" in i for i in now))

    def test_a_row_naming_a_check_id_no_tool_measures_is_reported_the_same_week(self):
        """Otherwise the row is refused at its verify date, weeks after anyone could fix it."""
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit()
            w.rows(ROW.format(id="2026-W36-01", check="pkg.duplicate", target="~/x",
                              action="removed two copies", cls="safe", then="2 count",
                              st="applied", applied="2026-09-02", after="2026-09-16"))
            _, now, _ = w.decide()
            self.assertTrue(any("pkg.duplicate" in i and "no tool measures" in i for i in now), now)
            self.assertIn("1 with an unknown check id", status.report(w.read(), TODAY))

    def test_a_row_naming_a_known_check_id_is_not_reported(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit()
            w.rows(ROW.format(id="2026-W36-01", check="friction.slow-command", target="~/x",
                              action="cached the install", cls="safe", then="120 seconds",
                              st="applied", applied="2026-09-02", after="2026-09-16"))
            _, now, _ = w.decide()
            self.assertFalse(any("no tool measures" in i for i in now), now)

    def test_a_stale_audit_is_reported_even_with_zero_fail(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.audit(name="2026-06-01-repos.json")
            _, now, _ = w.decide()
            self.assertTrue(any("has moved on" in i for i in now), now)

    def test_a_settled_machine_says_nothing_is_open(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            w.standards_filled()
            w.config_filled()
            w.audit()
            _, now, _ = w.decide()
            self.assertEqual(now, ["nothing open: measure again when the newest audit ages out"])

    def test_a_broken_audit_file_does_not_crash_the_report(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            w.machine_filled()
            (w.base / "audits" / "2026-09-01-repos.json").write_text("{not json")
            out = status.report(w.read(), TODAY)
            self.assertIn("2026-09-01-repos.json", out)


class AuditsPerKindTest(unittest.TestCase):
    """One newest audit per kind. A single newest file across all kinds hides every other pass."""

    def ready(self, d):
        w = Workspace(d)
        w.machine_filled(); w.standards_filled(); w.config_filled()
        return w

    def test_a_newer_pass_of_one_kind_does_not_hide_another_kind(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.ready(d)
            w.audit(name="2026-09-01-machine.json", tool="machine", fail=1, ids=("disk.low",))
            w.audit(name="2026-09-04-repos.json", tool="repos", fail=0)
            _, now, _ = w.decide()
            self.assertTrue(any("`disk.low` still fails" in i for i in now), now)
            self.assertTrue(any("jorekai-dx:machine" in i for i in now), now)

    def test_the_newest_of_one_kind_wins_over_the_older_of_the_same_kind(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.ready(d)
            w.audit(name="2026-08-01-repos.json", tool="repos", fail=1, ids=("git.dirty",))
            w.audit(name="2026-09-04-repos.json", tool="repos", fail=0)
            s = w.read()
            self.assertEqual(list(s["audits"]), ["repos"])
            self.assertEqual(s["audits"]["repos"]["file"], "2026-09-04-repos.json")

    def test_failures_are_ordered_by_the_priority_ladder_not_by_the_newest_pass(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.ready(d)
            w.audit(name="2026-09-04-machine.json", tool="machine", fail=1, ids=("disk.cache",))
            w.audit(name="2026-09-01-repos.json", tool="repos", fail=1, ids=("git.unpushed",))
            _, now, _ = w.decide()
            self.assertIn("`git.unpushed`", now[0])
            self.assertIn("`disk.cache`", now[1])

    def test_a_missing_repository_pass_blocks_destructive_work(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.ready(d)
            w.audit(name="2026-09-04-machine.json", tool="machine", fail=0)
            _, now, _ = w.decide()
            self.assertTrue(any("nothing destructive may run" in i for i in now), now)

    def test_the_kind_falls_back_to_the_file_name_when_the_json_omits_it(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.ready(d)
            (w.base / "audits" / "2026-09-04-github.json").write_text(json.dumps({"counts": {"FAIL": 0}}))
            self.assertIn("github", w.read()["audits"])

    def test_the_standard_decides_when_an_audit_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.ready(d)
            w.set_key("standards.md", "audit_max_age_days", "120")
            w.audit(name="2026-06-01-repos.json", tool="repos", fail=0)
            self.assertEqual(w.read()["max_age"], 120)
            _, now, _ = w.decide()
            self.assertFalse(any("has moved on" in i for i in now), now)


class LadderTest(unittest.TestCase):
    def test_every_namespace_names_the_skill_that_owns_it(self):
        self.assertEqual(status.skill_for("git.dirty"), "jorekai-dx:repos")
        self.assertEqual(status.skill_for("container.reclaimable"), "jorekai-dx:machine")
        self.assertEqual(status.skill_for("pr.stale"), "jorekai-dx:github")
        self.assertEqual(status.skill_for("agent.hook-broken"), "jorekai-dx:agent-config")
        self.assertEqual(status.skill_for("friction.retry-prompt"), "jorekai-dx:friction")
        self.assertEqual(status.skill_for("unknown.thing"), "")

    def test_unsaved_work_outranks_a_full_disk_and_tidiness_comes_last(self):
        self.assertLess(status.rung("git.dirty"), status.rung("disk.low"))
        self.assertLess(status.rung("disk.low"), status.rung("pr.review-requested"))
        self.assertLess(status.rung("disk.cache"), status.rung("git.stale-branch"))

    def test_an_unlisted_id_sits_in_the_middle_instead_of_first_or_last(self):
        self.assertEqual(status.rung("something.new"), 5)

    def test_an_exposed_credential_sits_on_the_first_rung(self):
        self.assertEqual(status.rung("repo.secret-exposed"), 1)

    def test_only_an_id_outside_the_ladder_counts_as_unmeasured(self):
        """The ladder names every id the tools emit, so it answers both questions."""
        rows = [{"check": "git.dirty", "_file": "a.md"}, {"check": "friction.retry-prompt", "_file": "a.md"},
                {"check": "auth.stale", "_file": "b.md"}, {"_file": "b.md"}]
        self.assertEqual([r["check"] for r in status.unsettled(rows)], ["auth.stale"])


class CliTest(unittest.TestCase):
    def test_no_workspace_exits_2_and_names_the_skill(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(Path(d) / "dx")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("jorekai-dx:setup", r.stdout)

    def test_a_machine_name_with_a_separator_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(w.root), "../escaped"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

    def test_the_report_labels_every_block_it_prints(self):
        """A block nobody can name is a block nobody reads."""
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(w.root),
                                "--today", TODAY.isoformat()], capture_output=True, text=True)
            for label in ("and-now  ", "setup      ", "audits     ", "log        ", "proposals  "):
                self.assertIn(label, r.stdout)

    def test_the_report_prints_stage_and_a_numbered_now_list(self):
        with tempfile.TemporaryDirectory() as d:
            w = Workspace(d)
            r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(w.root),
                                "--today", TODAY.isoformat()], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("stage  ", r.stdout)
            self.assertIn("now\n  1. ", r.stdout)


class StrayLogTest(unittest.TestCase):
    """A week file at the old flat path is invisible to every reader (decisions/0015)."""

    def test_a_flat_week_file_is_named_and_the_fix_is_the_migration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "dx"
            base = root / "machines" / "example-machine"
            (base / "log" / "dx").mkdir(parents=True)
            (base / "config.md").write_text("- project_roots: ~/code\n", encoding="utf-8")
            (root / "config.md").write_text("- git_email: a@b.c\n", encoding="utf-8")
            (root / "standards.md").write_text("- verify_window_days: 14\n", encoding="utf-8")
            (base / "log" / "2026-W35.md").write_text("# 2026-W35\n", encoding="utf-8")
            s = status.read_machine(root, "example-machine", dt.date(2026, 9, 7))
            self.assertEqual(s["stray_logs"], ["2026-W35.md"])
            text = status.report(s, dt.date(2026, 9, 7))
            self.assertIn("--migrate-log", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
