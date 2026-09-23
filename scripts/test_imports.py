#!/usr/bin/env python3
"""Offline tests for the stdlib-only import gate.

Run: python3 scripts/test_imports.py
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_imports


class ImportsTest(unittest.TestCase):
    def test_stdlib_imports_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.py"
            path.write_text("import os\nimport json as j\nfrom pathlib import Path\n", encoding="utf-8")
            self.assertEqual(check_imports.bad_imports(path), [])

    def test_a_sibling_module_passes_even_when_its_name_shadows_a_stdlib_module(self):
        # skills/security/secrets/scripts/secrets.py sits beside its own tests, and "secrets"
        # is also a name in the standard library; the sibling file must win, not the collision.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "secrets.py").write_text("VALUE = 1\n", encoding="utf-8")
            user = root / "test_secrets.py"
            user.write_text("import secrets as scan\n", encoding="utf-8")
            self.assertEqual(check_imports.bad_imports(user), [])

    def test_a_pypi_import_fails_with_its_line_number(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.py"
            path.write_text("import os\nimport requests\n", encoding="utf-8")
            hits = check_imports.bad_imports(path)
            self.assertEqual(hits, [(2, "import requests")])

    def test_import_pip_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.py"
            path.write_text("import pip\n", encoding="utf-8")
            hits = check_imports.bad_imports(path)
            self.assertEqual(len(hits), 1)
            self.assertIn("import pip", hits[0][1])

    def test_from_import_of_a_pypi_package_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.py"
            path.write_text("from yaml import safe_load\n", encoding="utf-8")
            hits = check_imports.bad_imports(path)
            self.assertEqual(len(hits), 1)
            self.assertIn("from yaml import", hits[0][1])

    def test_relative_imports_are_always_local(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.py"
            path.write_text("from . import helpers\nfrom .helpers import thing\n", encoding="utf-8")
            self.assertEqual(check_imports.bad_imports(path), [])

    def test_cli_finds_a_planted_violation_then_passes_once_it_is_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "skills" / "demo" / "sample" / "scripts" / "bad.py"
            script.parent.mkdir(parents=True)
            script.write_text("import pip\n", encoding="utf-8")
            command = [sys.executable, check_imports.__file__, "--root", str(root)]
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1, failed.stderr)
            self.assertIn("import pip is not stdlib", failed.stdout)
            script.write_text("import os\n", encoding="utf-8")
            passed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual(passed.stdout, "")

    def test_cli_only_looks_under_skills_and_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            other = root / "elsewhere" / "bad.py"
            other.parent.mkdir(parents=True)
            other.write_text("import pip\n", encoding="utf-8")
            command = [sys.executable, check_imports.__file__, "--root", str(root)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
