#!/usr/bin/env python3
"""Offline tests for repos.py: discovery, one repository's state, and one item per check id.

Run: python3 skills/dx/repos/scripts/test_repos.py
Builds throwaway repositories in a temp folder; no network, no remote, no fetch.
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repos  # noqa: E402

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
             "ci": True, "lock_drift": [], "email": "", "unpushed_branches": []}
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
        self.assertIn("2 repository(s)", got["git.dirty"]["message"])

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


if __name__ == "__main__":
    unittest.main(verbosity=1)
