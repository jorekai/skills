#!/usr/bin/env python3
"""Offline tests for the frontmatter gate and its failure diagnostics.

Run: python3 scripts/test_frontmatter.py
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_frontmatter


def header(description='"Use when scope is clear: read, then act."', extra=""):
    return f"---\nname: sample\ndescription: {description}\n{extra}---\n\n# Sample\n"


class FrontmatterTest(unittest.TestCase):
    def test_quoted_punctuation_and_literal_boolean_are_valid(self):
        text = header(json.dumps('Read "name: value" and # without losing text.'),
                      'disable-model-invocation: true\nargument-hint: "[scope]"\n')
        self.assertEqual(check_frontmatter.check(text, "sample"), [])

    def test_unquoted_description_cannot_pass(self):
        errors = check_frontmatter.check(header("Entry point: read first"), "sample")
        self.assertEqual(errors, [(3, 'description needs text in double quotes, for example description: "Text"')])

    def test_invalid_or_non_string_descriptions_cannot_pass(self):
        for value in ('"bad \\q"', '"unfinished', 'true', '42', '[]', '""', '"text" # comment'):
            with self.subTest(value=value):
                self.assertTrue(check_frontmatter.check(header(value), "sample"))

    def test_fences_required_fields_and_duplicate_keys_are_checked(self):
        for text in ("# Sample\n", "---\nname: sample\n", "---\nname: sample\n---\n",
                     header(extra='name: sample\n')):
            with self.subTest(text=text):
                self.assertTrue(check_frontmatter.check(text, "sample"))

    def test_name_matches_its_directory_and_boolean_is_typed(self):
        self.assertTrue(check_frontmatter.check(header(), "different"))
        for extra in ('disable-model-invocation: "true"\n', 'description-extra: "x"\n',
                      ' continuation\n'):
            with self.subTest(extra=extra):
                self.assertTrue(check_frontmatter.check(header(extra=extra), "sample"))

    def test_cli_rejects_an_invalid_skill_even_before_it_is_tracked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skills" / "demo" / "sample" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(header("Entry point: read first"), encoding="utf-8")
            command = [sys.executable, check_frontmatter.__file__, "--root", str(root), "--json"]
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1, failed.stderr)
            data = json.loads(failed.stdout)
            self.assertEqual(data["errors"][0]["file"], "skills/demo/sample/SKILL.md")
            self.assertEqual(data["errors"][0]["line"], 3)
            skill.write_text(header(), encoding="utf-8")
            passed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual(json.loads(passed.stdout), {"checked": 1, "errors": []})

    def test_a_clean_pass_says_nothing_on_stdout(self):
        """check.sh prints ok when its zone is silent, so the count goes to stderr."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skills" / "demo" / "sample" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(header(), encoding="utf-8")
            command = [sys.executable, check_frontmatter.__file__, "--root", str(root)]
            passed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(passed.stdout, "")
            self.assertIn("1 checked, 0 errors", passed.stderr)
            skill.write_text(header("Entry point: read first"), encoding="utf-8")
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertIn("skills/demo/sample/SKILL.md:3:", failed.stdout)

    def test_cli_does_not_pass_an_empty_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, check_frontmatter.__file__, "--root", directory],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("no skill files found", result.stdout)


if __name__ == "__main__":
    unittest.main()
