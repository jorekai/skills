#!/usr/bin/env python3
"""Offline tests for status.py: one fake workspace walked through every stage of the loop.

Run: python3 skills/seo/and-now/scripts/test_status.py
Uses setup/scripts/scaffold.py for the folders so the templates stay the single source of truth.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import status  # noqa: E402

SCAFFOLD = HERE.parent.parent / "setup" / "scripts" / "scaffold.py"
TODAY = dt.date(2026, 9, 3)
DOMAIN = "example.com"
LOG_HEAD = ("# 2026-W36 (2026-08-31 to 2026-09-06)\n\nSource: {source}\n\n## Outcomes of earlier actions\n\n"
            "| id | URL | Applied | Then | Now | Baseline | Verdict |\n|---|---|---|---|---|---|---|\n\n## Actions\n\n"
            "| id | Bucket | URL | Query | Action | Then | Status | Applied | Verify after | Outcome |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n")


def row(i, bucket, url, state, applied="", verify=""):
    return f"| 2026-W36-{i:02d} | {bucket} | {url} | q | do x | pos 12.4 | {state} | {applied} | {verify} | |\n"


class Stages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "docs" / "seo"
        subprocess.run([sys.executable, str(SCAFFOLD), "--root", str(self.root), DOMAIN],
                       check=True, capture_output=True)
        self.base = self.root / DOMAIN

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self):
        s = status.read_domain(self.base, TODAY)
        return status.decide(s, TODAY)

    def fill_setup(self):
        (self.base / "config.md").write_text("- canonical_host: https://example.com\n- framework: Astro\n", encoding="utf-8")
        (self.base / "connections.md").write_text("- GSC_PROPERTY: sc-domain:example.com\n- SITEMAP_SUBMITTED_AT: 2026-09-01\n"
                                                  "- BING_IMPORTED_AT:\n- INDEXNOW_TESTED_AT: (URL)\n", encoding="utf-8")
        (self.base / "strategy.md").write_text("# strategy\n\n## Offer\n\nWe sell boats.\n", encoding="utf-8")
        (self.base / "glossary.md").write_text("# glossary\n\n**Boat**:\nA thing.\n_Avoid_: ship\n", encoding="utf-8")

    def audit(self, name, fail_ids=()):
        items = [{"section": "Crawl", "level": "FAIL", "id": i, "message": "x"} for i in fail_ids]
        (self.base / "audits" / name).write_text(json.dumps({"url": "https://example.com/", "final_url": "https://example.com/",
                                                             "counts": {"PASS": 1, "FAIL": len(items), "WARN": 0, "INFO": 0},
                                                             "items": items}), encoding="utf-8")

    def log(self, rows, source=""):
        (self.base / "log" / "2026-W36.md").write_text(LOG_HEAD.format(source=source) + "".join(rows), encoding="utf-8")

    def test_fresh_scaffold_is_setup(self):
        stage, now, _ = self.stage()
        self.assertEqual(stage, "setup")
        self.assertIn("jorekai-seo:setup", now[0])

    def test_config_filled_but_not_connected_or_grilled(self):
        self.fill_setup()
        (self.base / "connections.md").write_text("- GSC_PROPERTY:\n- SITEMAP_SUBMITTED_AT:\n", encoding="utf-8")
        template = (SCAFFOLD.parent.parent / "templates" / "strategy.md").read_text(encoding="utf-8")
        (self.base / "strategy.md").write_text(template, encoding="utf-8")
        stage, now, _ = self.stage()
        self.assertEqual(stage, "setup")
        self.assertTrue(any("jorekai-seo:connect" in n for n in now))
        self.assertTrue(any("jorekai-seo:grill" in n for n in now))

    def test_setup_done_no_audit(self):
        self.fill_setup()
        stage, now, _ = self.stage()
        self.assertEqual(stage, "audit")
        self.assertIn("jorekai-seo:tech-audit --crawl", now[0])

    def test_latest_audit_wins_and_fail_ids_listed(self):
        self.fill_setup()
        self.audit("2026-09-02-tech.json", ["crawl.broken-link", "head.canonical"])
        self.audit("2026-09-02-tech-verify.json", ["crawl.broken-link"])
        self.audit("2026-09-02-tech-verify2.json", [])
        s = status.read_domain(self.base, TODAY)
        self.assertEqual(s["audit"]["file"], "2026-09-02-tech-verify2.json")
        self.audit("2026-09-02-tech-verify3.json", ["crawl.orphans"])
        stage, now, _ = self.stage()
        self.assertEqual(stage, "audit")
        self.assertIn("crawl.orphans", now[0])
        self.assertTrue(any("export Search Console" in n for n in now), "loop steps still shown behind the FAIL")

    def test_green_audit_no_export_is_loop_not_started(self):
        self.fill_setup()
        self.audit("2026-09-02-tech.json")
        stage, now, then = self.stage()
        self.assertEqual(stage, "loop, not started")
        self.assertIn("export Search Console", now[0])
        self.assertEqual(then, [])

    def test_tech_todo_and_next_verify(self):
        self.fill_setup()
        self.audit("2026-09-02-tech.json")
        self.log([row(1, "tech", "/", "applied", "2026-09-02", "2026-09-16"), row(2, "tech", "/a/", "todo")])
        stage, now, then = self.stage()
        self.assertEqual(stage, "loop")
        self.assertIn("2026-W36-02", now[0])
        self.assertIn("2026-09-16", then[0])

    def test_due_rows_need_verdict(self):
        self.fill_setup()
        self.audit("2026-09-02-tech.json")
        self.log([row(1, "ctr", "/p/", "applied", "2026-08-01", "2026-08-15")])
        _, now, _ = self.stage()
        self.assertIn("verdict", now[0])
        self.assertIn("2026-W36-01", now[0])

    def test_export_not_reviewed_then_stale(self):
        self.fill_setup()
        self.audit("2026-09-02-tech.json")
        (self.base / "exports" / "2026-09-01-gsc.zip").write_bytes(b"x")
        self.log([])
        _, now, _ = self.stage()
        self.assertIn("jorekai-seo:gsc-review", now[0])
        self.assertIn("not named", now[0])
        self.log([], source="exports/2026-09-01-gsc.zip vs exports/2026-08-04-gsc.zip")
        _, now, _ = self.stage()
        self.assertIn("nothing open", now[0])
        old = self.base / "exports" / "2026-08-01-gsc.zip"
        (self.base / "exports" / "2026-09-01-gsc.zip").rename(old)
        self.log([], source="exports/2026-08-01-gsc.zip")
        _, now, _ = self.stage()
        self.assertIn("again", now[0])
        self.assertIn("33 days old", now[0])

    def test_log_without_the_export_file_says_where_it_went(self):
        """exports/ is git-ignored: a second checkout has the log rows and no export."""
        self.fill_setup()
        self.audit("2026-09-02-tech.json")
        self.log([row(1, "ctr", "/p/", "won", "2026-08-01", "2026-09-30")],
                 source="exports/2026-09-01-gsc.zip (2026-08-04 to 2026-09-01, 28 days)")
        stage, now, _ = self.stage()
        self.assertEqual(stage, "loop")
        self.assertTrue(any("git-ignored" in n and "2026-09-01-gsc.zip" in n for n in now), now)

    def test_content_chain(self):
        self.fill_setup()
        self.audit("2026-09-02-tech.json")
        (self.base / "exports" / "2026-09-01-gsc.zip").write_bytes(b"x")
        (self.base / "briefs" / "sbf-see-und-binnen.md").write_text("brief", encoding="utf-8")
        self.log([row(1, "content", "/sbf-see-und-binnen/", "todo")], source="exports/2026-09-01-gsc.zip")
        _, now, _ = self.stage()
        self.assertTrue(any("jorekai-seo:content" in n and "2026-W36-01" in n for n in now))
        self.assertTrue(any("no draft yet" in n for n in now))
        (self.base / "drafts" / "sbf-see-und-binnen.md").write_text("draft", encoding="utf-8")
        _, now, _ = self.stage()
        self.assertTrue(any("jorekai-seo:review" in n for n in now))
        self.log([row(1, "content", "/sbf-see-und-binnen/", "applied", "2026-09-03", "2026-10-01")],
                 source="exports/2026-09-01-gsc.zip")
        _, now, _ = self.stage()
        self.assertFalse(any("jorekai-seo:review" in n for n in now))
        self.assertTrue(any("jorekai-seo:links" in n for n in now))
        self.assertTrue(any("jorekai-seo:distribution" in n for n in now))
        self.log([row(1, "content", "/sbf-see-und-binnen/", "applied", "2026-09-03", "2026-10-01"),
                  row(2, "links", "/sbf-see-und-binnen/", "applied", "2026-09-03", "2026-10-01"),
                  row(3, "distribution", "/sbf-see-und-binnen/", "applied", "2026-09-03", "2026-10-01")],
                 source="exports/2026-09-01-gsc.zip")
        _, now, _ = self.stage()
        self.assertTrue(any("jorekai-seo:report" in n and "2026-08" in n for n in now), now)
        (self.base / "reports" / "2026-08.md").write_text("# report", encoding="utf-8")
        _, now, _ = self.stage()
        self.assertIn("nothing open", now[0])

    def test_log_table_without_an_id_column(self):
        """A hand-edited log may drop or rename the id column; the report still has to come out."""
        self.fill_setup()
        self.audit("2026-09-01-tech.json")
        head = ("# 2026-W36 (2026-08-31 to 2026-09-06)\n\nSource:\n\n## Actions\n\n"
                "| Bucket | URL | Query | Action | Status | Applied | Verify after | Outcome |\n"
                "|---|---|---|---|---|---|---|---|\n")
        (self.base / "log" / "2026-W36.md").write_text(head + "| tech | /a/ | q | do x | todo | | | |\n", encoding="utf-8")
        _, now, _ = self.stage()
        self.assertTrue(any("apply the open `tech` rows" in step for step in now), now)

    def test_cli_exit_codes(self):
        env = dict(os.environ)
        r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(self.root / "nope")],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        r = subprocess.run([sys.executable, str(HERE / "status.py"), "--root", str(self.root), "--today", "2026-09-03"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stage  setup", r.stdout)
        self.assertIn("\nstage  ", r.stdout)
        self.assertRegex(r.stdout, r"\n  1\. jorekai-seo:setup {10}fill config\.md")


if __name__ == "__main__":
    unittest.main(verbosity=1)
