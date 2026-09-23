#!/usr/bin/env python3
"""Offline tests for the marketplace-against-plugin.json gate.

Run: python3 scripts/test_marketplace.py
"""
import json
from pathlib import Path
import unittest

import check_marketplace


def write_repo(root, *, market_desc="Loop for a thing: setup, grade, and-now.",
                plugin_desc="Loop for a thing: setup, grade, and-now.",
                plugin_name="jorekai-demo", market_name="jorekai-demo",
                source="./skills/demo", skills=("setup", "grade")):
    market_dir = root / ".claude-plugin"
    market_dir.mkdir(parents=True)
    (market_dir / "marketplace.json").write_text(json.dumps({
        "name": "jorekai",
        "plugins": [{"name": market_name, "description": market_desc, "source": source}],
    }), encoding="utf-8")
    plugin_dir = root / "skills" / "demo"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": plugin_name, "description": plugin_desc}), encoding="utf-8")
    for skill in skills:
        skill_dir = plugin_dir / skill
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("---\n", encoding="utf-8")
    # the router directory, named after the theme, is never itself a loop item
    (plugin_dir / "demo").mkdir(exist_ok=True)
    (plugin_dir / "demo" / "SKILL.md").write_text("---\n", encoding="utf-8")


class MarketplaceTest(unittest.TestCase):
    def test_matching_entry_passes(self, tmp_path_factory=None):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_repo(root)
            self.assertEqual(check_marketplace.check(root), [])

    def test_description_drift_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_repo(root, market_desc="Drifted text.")
            hits = check_marketplace.check(root)
            self.assertEqual(len(hits), 1)
            self.assertIn("description differs", hits[0])

    def test_name_mismatch_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_repo(root, plugin_name="jorekai-other")
            hits = check_marketplace.check(root)
            self.assertEqual(len(hits), 1)
            self.assertIn("plugin.json name is", hits[0])

    def test_missing_source_directory_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_repo(root, source="./skills/ghost")
            hits = check_marketplace.check(root)
            self.assertEqual(len(hits), 1)
            self.assertIn("resolves to no directory", hits[0])

    def test_missing_manifest_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_repo(root)
            (root / "skills" / "demo" / ".claude-plugin" / "plugin.json").unlink()
            hits = check_marketplace.check(root)
            self.assertEqual(len(hits), 1)
            self.assertIn("holds no .claude-plugin/plugin.json", hits[0])

    def test_a_loop_description_missing_a_skill_directory_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_repo(root, market_desc="Loop for a thing: setup, and-now.",
                       plugin_desc="Loop for a thing: setup, and-now.",
                       skills=("setup", "grade"))
            hits = check_marketplace.check(root)
            self.assertEqual(len(hits), 1)
            self.assertIn("names no grade in its loop", hits[0])

    def test_a_non_loop_description_is_not_forced_into_the_form(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = "The map of this collection: the themes, their loops, and which one you need."
            write_repo(root, market_desc=text, plugin_desc=text, skills=("setup", "grade"))
            self.assertEqual(check_marketplace.check(root), [])

    def test_root_source_resolves_to_the_repository_root(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".claude-plugin").mkdir(parents=True)
            (root / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
                "name": "jorekai",
                "plugins": [{"name": "jorekai-seo", "description": "SEO loop: setup, and-now.",
                             "source": "./"}],
            }), encoding="utf-8")
            (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({
                "name": "jorekai-seo", "description": "SEO loop: setup, and-now."}), encoding="utf-8")
            for skill in ("setup", "seo"):
                d = root / "skills" / "seo" / skill
                d.mkdir(parents=True)
                (d / "SKILL.md").write_text("---\n", encoding="utf-8")
            self.assertEqual(check_marketplace.check(root), [])


if __name__ == "__main__":
    unittest.main()
