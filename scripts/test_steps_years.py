#!/usr/bin/env python3
"""Offline tests for the year-in-Steps gate.

Run: python3 scripts/test_steps_years.py
"""
from pathlib import Path
import tempfile
import unittest

import check_steps_years as csy


def skill(steps_body, rules_body="- Nothing.\n"):
    return (
        "---\nname: sample\ndescription: \"Sample.\"\n---\n\n# Sample\n\n"
        f"## Steps\n\n{steps_body}\n## Rules\n\n{rules_body}"
    )


class StepsYearsTest(unittest.TestCase):
    def test_a_year_in_step_prose_is_a_hit(self):
        text = skill("1. Check the log since 2020, then act.\n2. Done when the check passes.\n\n")
        self.assertEqual(len(csy.years_in_steps(text)), 1)

    def test_a_year_in_inline_code_is_not_a_hit(self):
        text = skill("1. Run `git log --since=2020-01-01`.\n2. Done when the check passes.\n\n")
        self.assertEqual(csy.years_in_steps(text), [])

    def test_a_year_in_a_fenced_block_is_not_a_hit(self):
        text = skill("1. Run the export.\n```bash\nfind . -newer 2020-01-01.marker\n```\n"
                      "2. Done when the check passes.\n\n")
        self.assertEqual(csy.years_in_steps(text), [])

    def test_a_year_in_rules_stands_outside_steps_and_is_not_a_hit(self):
        text = skill("1. Do the thing.\n2. Done when the check passes.\n\n",
                      rules_body="- Google confirmed this in 2019.\n")
        self.assertEqual(csy.years_in_steps(text), [])

    def test_a_file_with_no_steps_heading_returns_none(self):
        text = "---\nname: sample\ndescription: \"Sample.\"\n---\n\n# Sample\n\n## Rules\n\n- x\n"
        self.assertIsNone(csy.steps_section(text))
        self.assertEqual(csy.years_in_steps(text), [])

    def test_steps_section_stops_at_the_next_heading(self):
        text = skill("1. Do the thing.\n2. Done when the check passes.\n\n")
        section = csy.steps_section(text)
        self.assertNotIn("## Rules", section)
        self.assertIn("Done when", section)

    def test_cli_finds_a_planted_violation_then_passes_once_it_is_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "skills" / "demo" / "sample" / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(skill("1. Check the log since 2020, then act.\n"
                                   "2. Done when the check passes.\n\n"), encoding="utf-8")
            import subprocess
            import sys
            command = [sys.executable, csy.__file__, "--root", str(root)]
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1, failed.stderr)
            self.assertIn("2020 inside ## Steps", failed.stdout)
            path.write_text(skill("1. Check the log, then act.\n"
                                   "2. Done when the check passes.\n\n"), encoding="utf-8")
            passed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual(passed.stdout, "")


if __name__ == "__main__":
    unittest.main()
