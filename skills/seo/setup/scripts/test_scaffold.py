#!/usr/bin/env python3
"""Offline tests for scaffold.py: host names (a folder is named after one) and week ids.

Run: python3 skills/seo/setup/scripts/test_scaffold.py
Writes into a temp folder; no network.
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


class HostTest(unittest.TestCase):
    def test_scheme_and_path_are_stripped(self):
        self.assertEqual(scaffold.host("https://Example.COM/blog/"), "example.com")
        self.assertEqual(scaffold.host(" http://sub.example.co.uk "), "sub.example.co.uk")

    def test_a_name_that_is_not_a_host_is_rejected(self):
        """Every folder is named after this value, so a path segment must never survive it."""
        for bad in ("..", ".", "", "/", "../../escaped", "a b.com", "-x.com", "example.com:8080"):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                scaffold.host(bad)

    def test_an_internationalized_host_converts_to_punycode(self):
        self.assertEqual(scaffold.host("münchen.example"), "xn--mnchen-3ya.example")
        self.assertEqual(scaffold.host("HTTPS://MÜNCHEN.example/seite/"), "xn--mnchen-3ya.example")

    def test_a_plain_ascii_host_is_unaffected_by_the_idna_path(self):
        self.assertEqual(scaffold.host("example.com"), "example.com")

    def test_traversal_writes_nothing_outside_the_root(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "docs" / "seo"
            root.mkdir(parents=True)
            r = subprocess.run([sys.executable, os.path.abspath(scaffold.__file__), "--root", str(root), "../escaped"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertEqual(sorted(p.name for p in (Path(d) / "docs").iterdir()), ["seo"])
            self.assertEqual(list(root.iterdir()), [])


class TodayFlagTest(unittest.TestCase):
    def test_a_bad_today_value_is_a_clean_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "docs" / "seo"
            r = subprocess.run([sys.executable, os.path.abspath(scaffold.__file__), "--root", str(root),
                               "--today", "not-a-date", "--check"], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("--today needs YYYY-MM-DD", r.stderr)


class WeekTest(unittest.TestCase):
    def test_week_bounds_start_on_monday(self):
        week, start, end = scaffold.week_bounds(dt.date(2026, 9, 3))
        self.assertEqual(week, "2026-W36")
        self.assertEqual((start.isoformat(), end.isoformat()), ("2026-08-31", "2026-09-06"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
