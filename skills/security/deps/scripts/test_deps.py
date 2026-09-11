#!/usr/bin/env python3
"""Offline tests for deps.py: the lock readers, the three classes, and the manifests without a lock.

Run: python3 skills/security/deps/scripts/test_deps.py
Every answer from the advisory database is a captured file, so no test touches the network.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deps  # noqa: E402

SCRIPT = os.path.abspath(deps.__file__)
NOW = "2026-09-09T12:00:00"


def advisory(vid, alias="", fixed=""):
    out = {"id": vid, "aliases": [alias] if alias else []}
    if fixed:
        out["affected"] = [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": fixed}]}]}]
    return out


def tree(d, **files):
    for name, text in files.items():
        p = Path(d) / name.replace("__", "/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return d


def run(root, *extra):
    args = [sys.executable, SCRIPT, "--json", "--now", NOW, "--root", str(root), "--offline", *extra]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def with_answer(d, answer, *extra, **files):
    tree(d, **files)
    path = Path(d) / "answer.json"
    path.write_text(json.dumps(answer), encoding="utf-8")
    return run(d, "--osv-file", str(path), *extra)


def item(out, cid, level=None):
    for i in out["items"]:
        if i["id"] == cid and (level is None or i["level"] == level):
            return i
    raise AssertionError(f"no {cid} ({level}) in {[i['id'] for i in out['items']]}")


def cost(out, cid):
    return item(out, cid)["measure"]["value"]


class ReaderTest(unittest.TestCase):
    def test_the_current_npm_lock_shape_is_read(self):
        text = json.dumps({"lockfileVersion": 3, "packages": {
            "": {"name": "root"}, "node_modules/left-pad": {"version": "1.0.0"},
            "node_modules/@scope/thing": {"version": "2.1.0"}}})
        self.assertEqual(sorted(deps.npm_lock(text)),
                         [("@scope/thing", "2.1.0"), ("left-pad", "1.0.0")])

    def test_the_older_npm_lock_shape_is_read_too(self):
        text = json.dumps({"lockfileVersion": 1, "dependencies": {"left-pad": {"version": "1.0.0"}}})
        self.assertEqual(deps.npm_lock(text), [("left-pad", "1.0.0")])

    def test_a_yarn_lock_pairs_an_entry_with_the_version_under_it(self):
        text = 'left-pad@^1.0.0:\n  version "1.0.0"\n\n"@scope/thing@^2":\n  version "2.1.0"\n'
        self.assertEqual(sorted(deps.yarn_lock(text)),
                         [("@scope/thing", "2.1.0"), ("left-pad", "1.0.0")])

    def test_a_pnpm_lock_reads_the_packages_section_only(self):
        text = ("lockfileVersion: '9.0'\ndependencies:\n  left-pad: 1.0.0\n"
                "packages:\n  /left-pad@1.0.0:\n    resolution: {integrity: x}\n")
        self.assertEqual(deps.pnpm_lock(text), [("left-pad", "1.0.0")])

    def test_a_pinned_requirement_is_read_and_a_range_is_not(self):
        self.assertEqual(deps.requirements("flask==2.0.1\nrequests>=2\n# a comment\n"),
                         [("flask", "2.0.1")])

    def test_a_package_block_lock_reads_one_pair_per_block(self):
        text = ('[[package]]\nname = "serde"\nversion = "1.0.1"\n\n'
                '[[package]]\nname = "log"\nversion = "0.4.0"\n\n[metadata]\nx = "y"\n')
        self.assertEqual(deps.toml_packages(text), [("serde", "1.0.1"), ("log", "0.4.0")])

    def test_a_go_sum_names_each_module_once(self):
        text = ("example.com/m v1.2.3 h1:abc=\nexample.com/m v1.2.3/go.mod h1:def=\n")
        self.assertEqual(deps.go_sum(text), [("example.com/m", "v1.2.3")])

    def test_a_composer_lock_and_a_gem_lock_are_read(self):
        self.assertEqual(deps.composer_lock(json.dumps({"packages": [{"name": "a/b", "version": "v1.2.3"}]})),
                         [("a/b", "1.2.3")])
        self.assertEqual(deps.gemfile_lock("GEM\n  specs:\n    rails (7.0.1)\n"), [("rails", "7.0.1")])


class ClassTest(unittest.TestCase):
    """One package counts in one check only: exploited, then fixable, then the rest."""

    def setUp(self):
        self.found = {
            "npm/hot@1.0.0": [advisory("GHSA-a", "CVE-2026-0001", "1.0.1")],
            "npm/fixable@1.0.0": [advisory("GHSA-b", "CVE-2026-0002", "1.0.2")],
            "npm/open@1.0.0": [advisory("GHSA-c", "CVE-2026-0003")],
        }

    def test_a_catalogue_entry_makes_a_package_exploited_and_takes_it_out_of_the_others(self):
        hot, fixable, rest = deps.classify(self.found, {"CVE-2026-0001"}, {}, 0.5)
        self.assertEqual(list(hot), ["npm/hot"])
        self.assertEqual(list(fixable), ["npm/fixable"])
        self.assertEqual(list(rest), ["npm/open"])

    def test_a_probability_at_the_floor_counts_as_exploited_as_well(self):
        hot, fixable, _ = deps.classify(self.found, set(), {"CVE-2026-0002": 0.7}, 0.5)
        self.assertEqual(list(hot), ["npm/fixable"])
        self.assertEqual(list(fixable), ["npm/hot"])

    def test_a_probability_below_the_floor_changes_nothing(self):
        hot, _, _ = deps.classify(self.found, set(), {"CVE-2026-0002": 0.2}, 0.5)
        self.assertEqual(list(hot), [])

    def test_an_advisory_with_no_published_fix_stays_in_the_last_class(self):
        _, fixable, rest = deps.classify(self.found, set(), {}, 0.5)
        self.assertEqual(sorted(fixable), ["npm/fixable", "npm/hot"])
        self.assertEqual(list(rest), ["npm/open"])


class EndToEndTest(unittest.TestCase):
    LOCK = json.dumps({"lockfileVersion": 3,
                       "packages": {"node_modules/hot": {"version": "1.0.0"},
                                    "node_modules/calm": {"version": "2.0.0"}}})

    def test_a_package_with_an_exploited_advisory_is_the_first_finding(self):
        with tempfile.TemporaryDirectory() as d:
            kev = Path(d) / "kev.json"
            kev.write_text(json.dumps({"vulnerabilities": [{"cveID": "CVE-2026-0001"}]}), encoding="utf-8")
            out = with_answer(d, {"npm/hot@1.0.0": [advisory("GHSA-a", "CVE-2026-0001", "1.0.1")]},
                              "--kev-file", str(kev),
                              **{"package-lock.json": self.LOCK, "package.json": "{}"})
            self.assertEqual(cost(out, "dep.known-exploited"), 1)
            self.assertEqual(cost(out, "dep.fix-available"), 0)
            self.assertEqual(item(out, "dep.known-exploited")["measure"]["by"], {"npm/hot": 1})

    def test_the_target_is_the_package_and_not_the_version_that_will_change(self):
        with tempfile.TemporaryDirectory() as d:
            out = with_answer(d, {"npm/hot@1.0.0": [advisory("GHSA-a", "", "1.0.1")]},
                              **{"package-lock.json": self.LOCK, "package.json": "{}"})
            self.assertEqual(list(item(out, "dep.fix-available")["measure"]["by"]), ["npm/hot"])

    def test_a_package_the_answer_does_not_name_costs_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = with_answer(d, {}, **{"package-lock.json": self.LOCK, "package.json": "{}"})
            for cid in ("dep.known-exploited", "dep.fix-available", "dep.vulnerable"):
                self.assertEqual(item(out, cid)["level"], "PASS")

    def test_an_accepted_package_leaves_the_count(self):
        with tempfile.TemporaryDirectory() as d:
            out = with_answer(d, {"npm/hot@1.0.0": [advisory("GHSA-a", "", "1.0.1")]},
                              "--accept", "dep.fix-available npm/hot agreed 2026-01-01",
                              **{"package-lock.json": self.LOCK, "package.json": "{}"})
            self.assertEqual(cost(out, "dep.fix-available"), 0)
            self.assertIn("1 finding is recorded as accepted", json.dumps(out))


class ManifestTest(unittest.TestCase):
    def test_a_manifest_without_a_lock_beside_it_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            out = with_answer(d, {}, **{"package.json": "{}"})
            self.assertEqual(cost(out, "dep.unresolved"), 1)

    def test_a_lock_beside_the_manifest_settles_it(self):
        with tempfile.TemporaryDirectory() as d:
            out = with_answer(d, {}, **{"package.json": "{}", "package-lock.json": "{}"})
            self.assertEqual(cost(out, "dep.unresolved"), 0)

    def test_a_lock_somewhere_else_in_the_tree_settles_nothing(self):
        """A second package of the same repository has its own lock, and it answers for itself."""
        with tempfile.TemporaryDirectory() as d:
            out = with_answer(d, {}, **{"package.json": "{}",
                                        "web__package.json": "{}", "web__package-lock.json": "{}"})
            self.assertEqual(cost(out, "dep.unresolved"), 1)


class NetworkTest(unittest.TestCase):
    def test_offline_with_packages_installed_carries_a_note_and_no_number(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d, **{"package-lock.json": EndToEndTest.LOCK})
            out = run(d)
            note = item(out, "dep.vulnerable", level="INFO")
            self.assertIsNone(note["measure"])
            self.assertIn("was not reached", note["message"])

    def test_a_repository_with_nothing_installed_says_so_and_passes(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d)
            self.assertEqual(out["packages"], 0)
            self.assertEqual(item(out, "dep.vulnerable")["level"], "PASS")

    def test_a_manifest_with_nothing_resolved_behind_it_carries_no_number(self):
        """A zero here would settle a log row with a figure nobody took (decisions/0014)."""
        with tempfile.TemporaryDirectory() as d:
            out = with_answer(d, {}, **{"package.json": '{"dependencies": {"lodash": "4.17.20"}}'})
            self.assertEqual(out["packages"], 0)
            self.assertEqual(cost(out, "dep.unresolved"), 1)
            for cid in ("dep.known-exploited", "dep.fix-available", "dep.vulnerable"):
                self.assertNotIn("PASS", [i["level"] for i in out["items"] if i["id"] == cid])
            note = item(out, "dep.vulnerable", level="INFO")
            self.assertIsNone(note["measure"])
            self.assertIn("no version was resolved", note["message"])


class ContractTest(unittest.TestCase):
    def test_measures_prints_one_id_and_unit_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--measures"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, deps.MEASURES)

    def test_the_text_report_says_what_it_measured_against_and_ends_on_a_next_step(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d, **{"package.json": "{}"})
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW, "--offline"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured against", r.stdout)
            self.assertIn("\nnext  ", r.stdout)

    def test_the_counting_line_is_a_bar_and_the_cost_stands_in_its_own_column(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d, **{"package.json": "{}"})
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW, "--offline"],
                               capture_output=True, text=True)
            self.assertRegex(r.stdout, r"\n\d+ FAIL · \d+ WARN · \d+ notes? · \d+ passed\n")
            self.assertRegex(r.stdout, r"\nWARN  dep\.unresolved {16}1 manifest\n")
            self.assertNotIn("(costs", r.stdout)

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW, "--offline"],
                               capture_output=True, text=True)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--now", NOW, "--offline"],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
