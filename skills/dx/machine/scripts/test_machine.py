#!/usr/bin/env python3
"""Offline tests for machine.py: sizes, thresholds, the rebuildable-tree walk, missing sources.

Run: python3 skills/dx/machine/scripts/test_machine.py
Writes into a temp folder; no network, and nothing outside that folder is measured.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import machine  # noqa: E402

MB = 1024 ** 2


def fill(path, megabytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\0" * (megabytes * MB))


class HumanTest(unittest.TestCase):
    def test_bytes_become_a_short_string(self):
        self.assertEqual(machine.human(512), "512 B")
        self.assertEqual(machine.human(1536), "1.5 KB")
        self.assertEqual(machine.human(3 * 1024 ** 3), "3.0 GB")


class SizeStringTest(unittest.TestCase):
    def test_a_runtime_size_string_becomes_gigabytes(self):
        self.assertAlmostEqual(machine._gb("12.5GB (40%)"), 12.5)
        self.assertAlmostEqual(machine._gb("512MB"), 0.5)
        self.assertAlmostEqual(machine._gb("2TB"), 2048.0)

    def test_an_unreadable_size_is_zero_not_an_error(self):
        for bad in (None, "", "N/A", "some text"):
            self.assertEqual(machine._gb(bad), 0.0)


class DirSizeTest(unittest.TestCase):
    def test_a_tree_is_measured(self):
        with tempfile.TemporaryDirectory() as d:
            fill(Path(d) / "a" / "big.bin", 4)
            size = machine.dir_size(Path(d))
            self.assertGreaterEqual(size, 4 * MB)


class LargeDirTest(unittest.TestCase):
    def run_walk(self, root, large_gb):
        rep = machine.Report()
        machine.large_dirs([root], rep, large_gb)
        return {i["id"]: i for i in rep.items}["disk.large-dir"]

    def test_a_rebuildable_tree_over_the_threshold_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            fill(Path(d) / "app" / "node_modules" / "x.bin", 4)
            item = self.run_walk(Path(d), large_gb=1 / 1024)      # 1 MB, so the test stays small
            self.assertEqual(item["level"], "WARN")
            self.assertEqual([h["kind"] for h in item["data"]], ["node_modules"])

    def test_a_tree_under_the_threshold_passes(self):
        with tempfile.TemporaryDirectory() as d:
            fill(Path(d) / "app" / "node_modules" / "x.bin", 1)
            self.assertEqual(self.run_walk(Path(d), large_gb=1)["level"], "PASS")

    def test_a_rebuildable_tree_is_not_searched_from_the_inside(self):
        """Its contents are the tree that was just measured; counting them twice inflates the total."""
        with tempfile.TemporaryDirectory() as d:
            fill(Path(d) / "app" / "node_modules" / "dep" / "node_modules" / "x.bin", 4)
            item = self.run_walk(Path(d), large_gb=1 / 1024)
            self.assertEqual(len(item["data"]), 1)
            self.assertTrue(item["data"][0]["path"].endswith("app/node_modules"))

    def test_a_repository_is_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            fill(Path(d) / "app" / ".git" / "objects" / "x.bin", 4)
            self.assertEqual(self.run_walk(Path(d), large_gb=1 / 1024)["level"], "PASS")


class VolumeTest(unittest.TestCase):
    def item(self, min_free_gb):
        rep = machine.Report()
        with tempfile.TemporaryDirectory() as d:
            machine.volume(Path(d), rep, min_free_gb)
        return rep.items[0]

    def test_enough_space_passes(self):
        self.assertEqual(self.item(0)["level"], "PASS")

    def test_a_floor_nothing_can_meet_fails(self):
        item = self.item(10 ** 9)
        self.assertEqual(item["level"], "FAIL")
        self.assertIn("below the floor", item["message"])


class CachesTest(unittest.TestCase):
    def test_only_existing_directories_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            fill(Path(d) / "cache" / "x.bin", 2)
            original = machine.CACHES
            machine.CACHES = [str(Path(d) / "cache"), str(Path(d) / "missing")]
            try:
                rep = machine.Report()
                machine.caches(rep, min_gb=1 / 1024)
                item = rep.items[0]
            finally:
                machine.CACHES = original
            self.assertEqual(item["level"], "WARN")
            self.assertEqual(len(item["data"]), 1)

    def test_no_cache_directory_at_all_passes(self):
        original = machine.CACHES
        machine.CACHES = ["/no/such/cache"]
        try:
            rep = machine.Report()
            machine.caches(rep, min_gb=1)
        finally:
            machine.CACHES = original
        self.assertEqual(rep.items[0]["level"], "PASS")


class ContainersTest(unittest.TestCase):
    def test_a_missing_runtime_is_information_not_a_failure(self):
        original = machine.RUNTIMES
        machine.RUNTIMES = ("no-such-container-runtime",)
        try:
            rep = machine.Report()
            machine.containers(rep, reclaim_gb=5)
        finally:
            machine.RUNTIMES = original
        self.assertEqual(rep.items[0]["level"], "INFO")
        self.assertIn("no container runtime", rep.items[0]["message"])

    def test_a_named_runtime_that_is_absent_says_which_one_was_expected(self):
        """The machine config names the runtime, so a missing one is a wrong record, not silence."""
        rep = machine.Report()
        machine.containers(rep, reclaim_gb=5, named="no-such-container-runtime")
        self.assertEqual(rep.items[0]["level"], "INFO")
        self.assertIn("no-such-container-runtime is not installed", rep.items[0]["message"])


class ReportTest(unittest.TestCase):
    """The console report is what a person reads before deciding, so its shape is a contract."""

    def filled(self):
        rep = machine.Report()
        rep.add("WARN", "disk.cache", "40.0 GB in 2 cache directories, all refilled on next use",
                [{"path": "/x/one", "size": 30 * machine.GB}, {"path": "/x/two", "size": 10 * machine.GB}],
                measure=40 * machine.GB, by={"/x/one": 30 * machine.GB, "/x/two": 10 * machine.GB})
        rep.add("PASS", "disk.low", "200.0 GB free on /x", measure=0)
        rep.add("INFO", "container.reclaimable", "docker did not answer")
        return rep

    def report(self):
        return machine.text_report(self.filled(), "test-machine", "free space floor 100 GB",
                                   machine.load_fixes())

    def test_the_header_says_what_was_measured_and_against_what(self):
        text = self.report()
        self.assertIn("machine  test-machine", text)
        self.assertIn("measured against  free space floor 100 GB", text)

    def test_the_counting_line_names_findings_notes_and_passed_checks(self):
        self.assertIn("0 FAIL · 1 WARN · 1 note · 1 passed", self.report())

    def test_the_counting_line_is_a_bar_and_every_finding_is_one_line(self):
        text = self.report()
        self.assertRegex(text, r"\n\d+ FAIL · \d+ WARN · \d+ notes? · \d+ passed\n")
        self.assertRegex(text, r"\n  #  level  check +measure +where +class\n")
        self.assertRegex(text, r"\n +1  WARN   disk\.cache +40\.0 GB +/x/one \+1 +safe\n")
        self.assertNotIn("(costs", text)

    def test_the_list_carries_the_cost_and_the_targets_wait_in_the_long_form(self):
        text = self.report()
        self.assertIn("40.0 GB", text)
        self.assertIn("passed  disk.low", text)
        self.assertIn("next  ", text)
        self.assertIn("30.0 GB", machine.explain_report(self.filled(), "test-machine",
                                                        machine.load_fixes(), "1", None))

    def test_a_pass_is_never_reported_as_a_finding(self):
        self.assertNotIn("PASS  disk.low", self.report())

    def test_a_note_is_ranked_like_a_finding_and_names_where_it_looked(self):
        """A note is read the same way as a finding, so it says what it found and where."""
        rep = machine.Report()
        rep.add("INFO", "disk.cache", "8.0 GB in 1 cache directory, under the threshold",
                [{"path": "/x/one", "size": 8 * machine.GB}], measure=8 * machine.GB,
                by={"/x/one": 8 * machine.GB})
        text = machine.text_report(rep, "test-machine", "free space floor 100 GB")
        self.assertRegex(text, r"\n +1  note   disk\.cache +8\.0 GB +/x/one")

    def test_a_home_path_is_written_short(self):
        self.assertEqual(machine.short(str(Path.home()) + "/one"), "~/one")


class ChainTest(unittest.TestCase):
    """The list answers what and how heavy, `--explain` answers the rest, one finding at a time."""

    def test_the_chain_names_its_fields_in_the_order_a_person_asks_them(self):
        rep = machine.Report()
        rep.add("FAIL", "disk.cache", "one line about it", [], measure=1)
        out = machine.explain_report(rep, "this repository", machine.load_fixes(), "1", None)
        labels = [l.split()[0] for l in out.splitlines() if l and not l.startswith(" ")][1:]
        self.assertEqual(labels, ["what", "weight", "means", "fix", "undo", "verify"])
        self.assertIn("Cache directories a tool refills on", out)
        self.assertIn("rank 1 of 1", out)

    def test_a_name_no_finding_carries_says_so(self):
        rep = machine.Report()
        rep.add("FAIL", "disk.cache", "one line about it", [], measure=1)
        self.assertIn("no finding called nothing.here",
                      machine.explain_report(rep, "this repository", {}, "nothing.here", None))

    def test_the_change_column_reads_the_measure_of_an_earlier_pass(self):
        rep = machine.Report()
        rep.add("FAIL", "disk.cache", "one line about it", [], measure=2)
        lines = machine.listing(rep.items, [], machine.load_fixes(), {"disk.cache": 1})
        self.assertIn("change", lines[0])
        self.assertRegex(lines[1], r"\+1")
        self.assertRegex(machine.listing(rep.items, [], {}, {})[1], r" new ")


if __name__ == "__main__":
    unittest.main(verbosity=1)
