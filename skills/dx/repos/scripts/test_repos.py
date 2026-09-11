#!/usr/bin/env python3
"""Offline tests for repos.py: discovery, one repository's state, and one item per check id.

Run: python3 skills/dx/repos/scripts/test_repos.py
Builds throwaway repositories in a temp folder; no network, no remote, no fetch.
"""
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repos  # noqa: E402

SCRIPT = os.path.abspath(repos.__file__)

ENV = dict(os.environ, GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.com",
           GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.com",
           GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
NOW = 1_757_030_400          # a fixed unix second, so ages in the tests never move


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=ENV)


def make_repo(path, commit=True, branch="main"):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", branch)
    if commit:
        (path / "file.txt").write_text("one\n")
        git(path, "add", ".")
        git(path, "commit", "-qm", "first")
    return path


class DiscoveryTest(unittest.TestCase):
    def test_a_repository_is_found_and_its_inside_is_not_searched(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root / "app")
            (root / "app" / "vendored").mkdir()
            make_repo(root / "app" / "vendored" / "inner")
            found = repos.find_repos([root], depth=5)
            self.assertEqual([p.name for p in found], ["app"])

    def test_depth_limits_the_search(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root / "a" / "b" / "c" / "deep")
            self.assertEqual(repos.find_repos([root], depth=2), [])
            self.assertEqual([p.name for p in repos.find_repos([root], depth=4)], ["deep"])

    def test_noise_directories_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_repo(root / "node_modules" / "pkg")
            make_repo(root / ".hidden" / "pkg")
            self.assertEqual(repos.find_repos([root], depth=3), [])

    def test_a_path_that_is_itself_a_repository_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            self.assertEqual([p.name for p in repos.find_repos([r], depth=0)], ["app"])

    def test_a_missing_path_is_ignored(self):
        self.assertEqual(repos.find_repos(["/no/such/place"], depth=3), [])


class RepoStateTest(unittest.TestCase):
    def state(self, path, stale_days=90, stash_days=90):
        return repos.read_repo(path, NOW, stale_days, stash_days, timeout=10)

    def test_a_clean_repository_reports_nothing_dirty(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.state(make_repo(Path(d) / "app"))
            self.assertEqual(s["dirty"], 0)
            self.assertEqual(s["branch"], "main")
            self.assertEqual(s["remotes"], [])

    def test_an_untracked_file_counts_as_dirty(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / "new.txt").write_text("x")
            self.assertEqual(self.state(r)["dirty"], 1)

    def test_unpushed_stays_zero_without_a_remote(self):
        """No remote is its own finding; counting every commit as unpushed would drown it."""
        with tempfile.TemporaryDirectory() as d:
            s = self.state(make_repo(Path(d) / "app"))
            self.assertEqual(s["unpushed"], 0)
            self.assertEqual(s["remotes"], [])

    def test_a_commit_missing_from_the_remote_is_unpushed(self):
        with tempfile.TemporaryDirectory() as d:
            origin = Path(d) / "origin.git"
            subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], env=ENV, check=True)
            r = make_repo(Path(d) / "app")
            git(r, "remote", "add", "origin", str(origin))
            git(r, "push", "-q", "origin", "main")
            self.assertEqual(self.state(r)["unpushed"], 0)
            (r / "file.txt").write_text("two\n")
            git(r, "commit", "-aqm", "second")
            self.assertEqual(self.state(r)["unpushed"], 1)

    def test_a_merged_branch_older_than_the_retention_is_stale(self):
        """A branch's age is its tip commit's date, so the old commit has to exist first."""
        with tempfile.TemporaryDirectory() as d:
            r = Path(d) / "app"
            r.mkdir()
            git(r, "init", "-q", "-b", "main")
            old = f"{NOW - 200 * 86400} +0000"
            (r / "file.txt").write_text("one\n")
            git(r, "add", ".")
            subprocess.run(["git", "-C", str(r), "commit", "-qm", "first"], capture_output=True,
                           env=dict(ENV, GIT_AUTHOR_DATE=old, GIT_COMMITTER_DATE=old))
            git(r, "branch", "done")
            (r / "file.txt").write_text("two\n")
            git(r, "commit", "-aqm", "second")
            names = [n for n, _ in self.state(r)["stale_branches"]]
            self.assertEqual(names, ["done"])
            self.assertEqual(self.state(r, stale_days=365)["stale_branches"], [])

    def test_a_detached_head_is_seen(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            sha = git(r, "rev-parse", "HEAD").stdout.strip()
            git(r, "checkout", "-q", sha)
            self.assertTrue(self.state(r)["detached"])

    def test_a_lock_older_than_its_manifest_is_drift(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / "package-lock.json").write_text("{}")
            os.utime(r / "package-lock.json", (NOW - 86400, NOW - 86400))
            (r / "package.json").write_text("{}")
            os.utime(r / "package.json", (NOW, NOW))
            self.assertEqual(self.state(r)["lock_drift"], ["package-lock.json"])

    def test_a_lock_newer_than_its_manifest_is_not_drift(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / "package.json").write_text("{}")
            os.utime(r / "package.json", (NOW - 86400, NOW - 86400))
            (r / "package-lock.json").write_text("{}")
            os.utime(r / "package-lock.json", (NOW, NOW))
            self.assertEqual(self.state(r)["lock_drift"], [])

    def test_hygiene_files_are_detected(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            s = self.state(r)
            self.assertEqual((s["readme"], s["ignore"], s["ci"]), (False, False, False))
            (r / "README.md").write_text("# app")
            (r / ".gitignore").write_text("*.log")
            (r / ".github" / "workflows").mkdir(parents=True)
            s = self.state(r)
            self.assertEqual((s["readme"], s["ignore"], s["ci"]), (True, True, True))


class SecretTest(unittest.TestCase):
    """The finding is an untracked credential file that no ignore rule covers, which is the one
    state where a single `git add` puts a credential into a history."""

    def state(self, path):
        return repos.read_repo(path, NOW, 90, 90, timeout=10)

    def test_an_untracked_credential_file_that_nothing_ignores_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / ".env").write_text("TOKEN=x\n")
            (r / "deploy.pem").write_text("key\n")
            self.assertEqual(self.state(r)["secrets"], [".env", "deploy.pem"])

    def test_an_ignored_credential_file_is_not_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / ".env").write_text("TOKEN=x\n")
            (r / ".gitignore").write_text(".env\n")
            self.assertEqual(self.state(r)["secrets"], [])

    def test_an_ignore_file_that_covers_something_else_leaves_the_finding(self):
        """The check reads coverage, not the existence of an ignore file."""
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / ".env").write_text("TOKEN=x\n")
            (r / ".gitignore").write_text("*.log\n")
            self.assertEqual(self.state(r)["secrets"], [".env"])

    def test_a_placeholder_file_is_not_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            for name in (".env.example", ".env.template", "id_rsa.pub"):
                (r / name).write_text("x\n")
            self.assertEqual(self.state(r)["secrets"], [])

    def test_a_tracked_credential_file_is_another_finding(self):
        """Once it is committed the history holds it, which no ignore rule undoes."""
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / ".env").write_text("TOKEN=x\n")
            git(r, "add", "-f", ".env")
            git(r, "commit", "-qm", "env")
            self.assertEqual(self.state(r)["secrets"], [])

    def test_a_credential_file_in_a_subdirectory_is_found(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / "config").mkdir()
            (r / "config" / "credentials.json").write_text("{}\n")
            self.assertEqual(self.state(r)["secrets"], ["config/credentials.json"])

    def test_the_finding_fails_and_counts_the_files_per_repository(self):
        rep = repos.Report()
        base = CollectTest().base
        repos.collect([base(path="/x/a", secrets=[".env"]),
                       base(path="/x/b", secrets=["a.pem", "b.pem"])], rep, 90)
        item = {i["id"]: i for i in rep.items}["repo.secret-exposed"]
        self.assertEqual(item["level"], "FAIL")
        self.assertEqual(item["measure"], {"value": 2, "unit": "count",
                                           "by": {"/x/a": 1, "/x/b": 2}})


class IdentityTest(unittest.TestCase):
    def test_only_a_repository_that_would_commit_under_another_address_is_a_finding(self):
        rep = repos.Report()
        states = [{"path": "/x/a", "email": "someone@example.com"},
                  {"path": "/x/b", "email": "other@example.com"}]
        base = CollectTest().base
        repos.collect([base(**s) for s in states], rep, 90, expect_email="someone@example.com")
        item = {i["id"]: i for i in rep.items}["git.identity"]
        self.assertEqual(item["level"], "WARN")
        self.assertEqual([d["repo"] for d in item["data"]], ["/x/b"])

    def test_without_an_expected_address_the_check_does_not_run(self):
        """A blank standard turns a check off; inventing an address would flag every repository."""
        rep = repos.Report()
        repos.collect([CollectTest().base(email="anything@example.com")], rep, 90)
        self.assertNotIn("git.identity", {i["id"] for i in rep.items})


class StashRetentionTest(unittest.TestCase):
    def test_a_stash_under_its_own_retention_is_not_reported(self):
        with tempfile.TemporaryDirectory() as d:
            r = make_repo(Path(d) / "app")
            (r / "file.txt").write_text("changed\n")
            git(r, "stash", "push", "-q", "-m", "wip")
            fresh = repos.read_repo(r, NOW_REAL := int(time.time()), 90, 30, timeout=10)
            self.assertEqual(fresh["stashes"], [])
            old = repos.read_repo(r, NOW_REAL + 40 * 86400, 90, 30, timeout=10)
            self.assertEqual(len(old["stashes"]), 1)


class CollectTest(unittest.TestCase):
    def items(self, states):
        rep = repos.Report()
        repos.collect(states, rep, 90)
        return {i["id"]: i for i in rep.items}

    def base(self, **over):
        s = {"path": "/x/app", "name": "app", "branch": "main", "detached": False, "dirty": 0,
             "remotes": ["origin"], "upstream": "origin/main", "unpushed": 0, "stashes": [],
             "stale_branches": [], "default_branch": "main", "readme": True, "ignore": True,
             "ci": True, "lock_drift": [], "email": "", "unpushed_branches": [], "secrets": []}
        s.update(over)
        return s

    def test_a_clean_set_is_all_pass(self):
        got = self.items([self.base()])
        self.assertTrue(all(i["level"] == "PASS" for i in got.values()), got)

    def test_one_item_per_check_id_lists_every_repository(self):
        """The same finding gets one row, not one row per affected path."""
        got = self.items([self.base(path="/x/a", dirty=2), self.base(path="/x/b", dirty=5)])
        self.assertEqual(got["git.dirty"]["level"], "FAIL")
        self.assertEqual([d["repo"] for d in got["git.dirty"]["data"]], ["/x/a", "/x/b"])
        self.assertIn("2 repositories", got["git.dirty"]["message"])

    def test_unsaved_work_is_fail_and_hygiene_is_info(self):
        got = self.items([self.base(dirty=1, unpushed=3, readme=False)])
        self.assertEqual(got["git.dirty"]["level"], "FAIL")
        self.assertEqual(got["git.unpushed"]["level"], "FAIL")
        self.assertEqual(got["repo.no-readme"]["level"], "INFO")

    def test_unpushed_names_the_branches_that_hold_the_work(self):
        """The work is rarely on the checked out branch, and a count alone hides where it is."""
        state = self.base(unpushed=13, unpushed_branches=[{"branch": "feat/a", "commits": 10},
                                                          {"branch": "feat/b", "commits": 3}])
        got = self.items([state])
        self.assertEqual(got["git.unpushed"]["data"][0]["branches"][0]["branch"], "feat/a")

    def test_a_repository_without_a_remote_is_flagged_once(self):
        got = self.items([self.base(remotes=[], upstream=None)])
        self.assertEqual(got["repo.no-remote"]["level"], "WARN")
        self.assertEqual(got["git.no-upstream"]["level"], "PASS")


class CellTest(unittest.TestCase):
    def test_a_flag_prints_nothing_and_a_list_prints_its_members(self):
        self.assertEqual(repos.cell(True), "")
        self.assertEqual(repos.cell(["a", "b"]), "a, b")
        self.assertEqual(repos.cell(3), "3")


class ReportTest(unittest.TestCase):
    """The console report is what a person reads before deciding, so its shape is a contract."""

    def report(self):
        rep = repos.Report()
        rep.add("FAIL", "git.dirty", "1 repository with uncommitted changes",
                [{"repo": "/x/one", "value": 25}], measure=1, by={"/x/one": 25})
        rep.add("PASS", "repo.no-readme", "no repository matches repo.no-readme", measure=0)
        return repos.text_report([{"path": "/x/one"}], rep, ["/x"], "merged branches over 30 days")

    def test_the_header_says_what_was_scanned_and_against_what(self):
        text = self.report()
        self.assertIn("repos  1 repository under /x", text)
        self.assertIn("measured against  merged branches over 30 days", text)

    def test_a_finding_names_its_cost_and_what_the_number_in_a_row_counts(self):
        text = self.report()
        self.assertIn("FAIL  " + "git.dirty".ljust(repos.ID_WIDTH) + "  1 repository", text)
        self.assertNotIn("(costs", text)
        self.assertIn("25 changed paths", text)

    def test_the_counting_line_is_a_bar_and_the_cost_stands_in_its_own_column(self):
        text = self.report()
        self.assertRegex(text, r"\n\d+ FAIL · \d+ WARN · \d+ notes? · \d+ passed\n")
        self.assertIn("\nFAIL  " + "git.dirty".ljust(repos.ID_WIDTH) + "  1 repository\n", text)
        self.assertNotIn("(costs", text)

    def test_passed_checks_are_listed_once_and_never_as_findings(self):
        text = self.report()
        self.assertIn("passed  repo.no-readme", text)
        self.assertNotIn("PASS  repo.no-readme", text)

    def test_unsaved_work_comes_before_every_other_step(self):
        self.assertIn("next  save the work a FAIL names before anything else", self.report())

    def test_a_row_word_carries_its_own_plural(self):
        """A count reads as English or it reads as a bug: stash entries, never stash entrys."""
        rep = repos.Report()
        rep.add("WARN", "git.stash-old", "1 repository with a stash older than the retention",
                [{"repo": "/x/one", "value": 2}], measure=1, by={"/x/one": 2})
        text = repos.text_report([{"path": "/x/one"}], rep, ["/x"], "stashes over 30 days")
        self.assertIn("2 stash entries", text)


class ColourTest(unittest.TestCase):
    """Colour is a hint on a report that reads the same without it (decisions/0022)."""

    def run_report(self, root, env=None):
        e = dict(os.environ)
        e.pop("FORCE_COLOR", None)
        e.pop("NO_COLOR", None)
        e.update(env or {})
        return subprocess.run([sys.executable, SCRIPT, str(root)], capture_output=True,
                              text=True, env=e).stdout

    def test_a_pipe_reads_plain_text(self):
        """Nothing here runs on a terminal: a redirect, a test and a subagent see no escape."""
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn("\033", self.run_report(Path(d)))

    def test_no_colour_wins_over_force_colour(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.run_report(Path(d), {"FORCE_COLOR": "1", "NO_COLOR": "1"})
            self.assertNotIn("\033", out)

    def test_every_escape_removed_leaves_the_same_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plain = self.run_report(root)
            painted = self.run_report(root, {"FORCE_COLOR": "1"})
            self.assertIn("\033", painted)
            self.assertEqual(re.sub(r"\033\[[0-9;]*m", "", painted), plain)


if __name__ == "__main__":
    unittest.main(verbosity=1)
