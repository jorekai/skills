#!/usr/bin/env python3
"""Offline tests for catalog.py: what the scan reads, and what --check refuses to pass.

Run: python3 skills/intro/intro/scripts/test_catalog.py
Writes into a temp folder; no network.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402

ROUTER = '''---
name: demo
description: "Entry point for the demo skill set: which sub-skill to reach for, and the flows."
disable-model-invocation: true
---

# Demo

One loop drives everything: **measure, fix the costliest thing, prove it held**.

## Sub-skills

| Need | Skill | Invoked by |
|---|---|---|
| Where do I stand? | `jorekai-demo:and-now` | you |
| What costs the most? | `jorekai-demo:tool` | agent or you |

## Planned

| Skill | Namespaces it will own |
|---|---|
| `jorekai-demo:later` | `port`, `fw` |

## Writing the answer

The columns, per skill:

- `jorekai-demo:tool`: `check id | cost | targets | fix | class`
- `jorekai-demo:and-now`: no table. The script's `stage`, at most three `now`, one `then`.
'''

TOOL = '''---
name: tool
description: "Measure what the machine costs via scripts/tool.py: caches, trees, memory."
---

# Tool
'''

ANDNOW = '''---
name: and-now
description: "Stage and next steps, read from the workspace files alone."
disable-model-invocation: true
---

# And now?
'''


def checkout(root):
    """A repository the size of the map: one theme, a router, two skills, two manifests."""
    root = Path(root)
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(
        {"name": "jorekai-other", "version": "9.9.9", "repository": "https://github.com/jorekai/skills"}),
        encoding="utf-8")
    (root / ".claude-plugin" / "marketplace.json").write_text(json.dumps(
        {"name": "jorekai", "plugins": [{"name": "jorekai-demo"}]}), encoding="utf-8")
    theme = root / "skills" / "demo"
    (theme / ".claude-plugin").mkdir(parents=True)
    (theme / ".claude-plugin" / "plugin.json").write_text(json.dumps(
        {"name": "jorekai-demo", "version": "1.2.3", "description": "Demo loop: tool, and-now."}),
        encoding="utf-8")
    for name, text in (("demo", ROUTER), ("tool", TOOL), ("and-now", ANDNOW)):
        d = theme / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(text, encoding="utf-8")
    (theme / "tool" / "scripts").mkdir()
    (theme / "tool" / "scripts" / "tool.py").write_text("#\n", encoding="utf-8")
    (theme / "tool" / "scripts" / "test_tool.py").write_text("#\n", encoding="utf-8")
    return root


class Scan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = checkout(self.tmp.name)
        self.map = catalog.scan(self.root)
        self.theme = self.map["themes"][0]

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_plugin_of_a_theme_carries_its_version_and_install_line(self):
        self.assertEqual(self.theme["plugin"], "jorekai-demo")
        self.assertEqual(self.theme["version"], "1.2.3")
        self.assertEqual(self.theme["install"], "claude plugin install jorekai-demo@jorekai")

    def test_the_marketplace_line_comes_from_the_manifest_not_from_this_script(self):
        self.assertEqual(self.map["marketplace"]["add"],
                         "claude plugin marketplace add jorekai/skills")

    def test_the_router_comes_first_then_the_order_the_router_itself_chose(self):
        self.assertEqual([s["skill"] for s in self.theme["skills"]],
                         ["jorekai-demo:demo", "jorekai-demo:and-now", "jorekai-demo:tool"])

    def test_who_may_start_a_skill_is_read_from_its_frontmatter(self):
        by = {s["skill"]: s["invoked_by"] for s in self.theme["skills"]}
        self.assertEqual(by["jorekai-demo:and-now"], "you")
        self.assertEqual(by["jorekai-demo:tool"], "agent or you")

    def test_a_skill_carries_the_need_and_the_answer_its_router_gives_it(self):
        tool = self.theme["skills"][2]
        self.assertEqual(tool["reach_for_it_when"], "What costs the most?")
        self.assertEqual(tool["hands_back"], "`check id | cost | targets | fix | class`")

    def test_a_planned_skill_is_kept_apart_from_the_ones_that_exist(self):
        self.assertEqual(self.theme["planned"], [{"skill": "jorekai-demo:later", "note": "port, fw"}])
        self.assertNotIn("jorekai-demo:later", [s["skill"] for s in self.theme["skills"]])

    def test_a_test_script_is_not_a_deterministic_part(self):
        self.assertEqual(self.theme["skills"][2]["scripts"], ["tool.py"])

    def test_the_thesis_of_the_theme_is_the_line_under_its_heading(self):
        self.assertEqual(self.theme["thesis"],
                         "One loop drives everything: measure, fix the costliest thing, prove it held.")

    def test_the_entry_command_is_the_setup_of_the_theme_or_its_router(self):
        self.assertEqual(self.theme["entry"], "/jorekai-demo:demo")


class Drift(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = checkout(self.tmp.name)
        self.snapshot = Path(self.tmp.name) / "catalog.json"
        self.snapshot.write_text(json.dumps(catalog.scan(self.root)), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def args(self):
        return ["--check", "--scan", str(self.root), "--snapshot", str(self.snapshot)]

    def test_a_snapshot_that_matches_the_checkout_passes(self):
        self.assertEqual(catalog.main(self.args()), 0)

    def test_a_snapshot_written_on_another_day_still_passes(self):
        old = json.loads(self.snapshot.read_text())
        old["generated"] = "2020-01-01"
        self.snapshot.write_text(json.dumps(old), encoding="utf-8")
        self.assertEqual(catalog.main(self.args()), 0)

    def test_a_skill_the_snapshot_does_not_know_fails_the_check(self):
        d = self.root / "skills" / "demo" / "extra"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: extra\ndescription: \"New.\"\n---\n", encoding="utf-8")
        self.assertEqual(catalog.main(self.args()), 1)

    def test_the_difference_names_the_field_that_moved(self):
        fresh = catalog.scan(self.root)
        old = json.loads(json.dumps(fresh))
        old["themes"][0]["version"] = "1.0.0"
        lines = list(catalog.differences(fresh, old))
        self.assertEqual(lines, ["map.themes[0].version: the checkout says '1.2.3', "
                                 "the snapshot says '1.0.0'"])


class Report(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.text = self.render(catalog.scan(checkout(self.tmp.name)))

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, data, theme=None):
        out = io.StringIO()
        catalog.report(data, theme, out)
        return out.getvalue()

    def test_the_first_line_counts_what_the_map_holds(self):
        self.assertIn("1 theme(s), 3 skill(s), marketplace jorekai", self.text)

    def test_every_theme_names_the_command_that_starts_it(self):
        self.assertIn("start    /jorekai-demo:demo", self.text)

    def test_a_planned_skill_is_marked_as_planned_and_never_as_available(self):
        self.assertIn("jorekai-demo:later", self.text)
        self.assertIn("planned", self.text)

    def test_every_theme_table_carries_a_column_header_before_its_first_row(self):
        self.assertRegex(self.text, r"\n  skill +invoked by +reach for it when\n  jorekai-")

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        self.assertNotIn("\033", self.text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
