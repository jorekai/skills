#!/usr/bin/env python3
"""Offline tests for drift.py: the declaration, the lock, the boundaries, the adapters.

Run: python3 skills/stack/drift/scripts/test_drift.py
Every test builds its own tree in a temporary directory; no network, no shared state.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drift  # noqa: E402

SCRIPT = os.path.abspath(drift.__file__)
TODAY = "2026-09-14"
TEMPLATE = Path(SCRIPT).resolve().parents[2] / "choose" / "templates" / "stack.yaml"
DEFAULTS = {"NAME": "demo", "DECLARED": "2026-09-14", "OSS_LEVEL": "pragmatic", "TARGET": "vercel",
            "OSS_CAVEAT": "", "NODE": "22", "PACKAGE_MANAGER": "pnpm@10", "GENERATOR": "create-next-app",
            "DB": "neon-http", "STORAGE": "vercel-blob", "JOBS": "vercel-cron", "HOST": "vercel",
            "AUTH": "better-auth", "MAIL": "resend", "ANALYTICS": "posthog", "ERRORS": "sentry",
            "COVERAGE_LINES": "70", "COVERAGE_BRANCHES": "60", "MAX_FUNCTION_LINES": "60",
            "MAX_FILE_LINES": "400", "MAX_COMPLEXITY": "10", "MAX_PARAMS": "4",
            "DEAD_EXPORTS_MAX": "0", "DEAD_FILES_MAX": "0", "DEAD_DEPS_MAX": "0",
            "GATE_MAX_SECONDS": "90", "DECIDE_BY": "2026-12-14"}
WORKSPACES = {"apps/web": "web", "packages/ui": "@app/ui", "packages/ports": "@app/ports",
              "packages/env": "@app/env", "packages/config": "@app/config"}


def declaration(**subs):
    text = TEMPLATE.read_text(encoding="utf-8")
    for k, v in dict(DEFAULTS, **subs).items():
        text = text.replace("{{%s}}" % k, v)
    return text


def write(root, path, text):
    p = Path(root) / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def lock_text(extra=""):
    out = ["lockfileVersion: '9.0'", "importers:"]
    for ws, name in WORKSPACES.items():
        out += [f"  {ws}:", "    dependencies:", "      zod:", "        specifier: ^3",
                "        version: 3.23.8"]
    out.append("  .:")
    out.append("    devDependencies:")
    out.append("      typescript:")
    out.append("        specifier: ^5")
    out.append("        version: 5.6.2")
    return "\n".join(out) + extra + "\n"


def tree(d, decl=None, manifest=True):
    """A small generated-like tree that passes every check."""
    root = Path(d)
    write(root, "stack.yaml", decl if decl is not None else declaration())
    write(root, ".nvmrc", "22\n")
    write(root, "package.json", json.dumps({"name": "demo", "packageManager": "pnpm@10.4.1",
                                            "engines": {"node": ">=22"}}))
    write(root, "pnpm-lock.yaml", lock_text())
    write(root, ".github/workflows/gate.yml",
          "name: gate\non: [push]\njobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n"
          "      - uses: actions/setup-node@v4\n        with:\n          node-version: 22\n"
          "      - run: pnpm check\n")
    for ws, name in WORKSPACES.items():
        data = {"name": name, "dependencies": {"zod": "^3"}}
        if name == "@app/ports":
            data["exports"] = {f"./{p}": f"./src/{p}/index.ts" for p in drift.PORTS}
        write(root, f"{ws}/package.json", json.dumps(data))
    write(root, "packages/config/src/index.ts", "export const TIMEOUT_MS = 10_000;\n")
    write(root, "packages/env/src/index.ts", 'import { TIMEOUT_MS } from "@app/config";\nexport const env = {};\n')
    write(root, "packages/ui/src/index.ts", 'import { TIMEOUT_MS } from "@app/config";\nexport const cn = () => "";\n')
    write(root, "apps/web/app/page.ts", 'import { db } from "@app/ports/db";\nimport { cn } from "@app/ui";\n')
    for port in drift.PORTS:
        for part in drift.PARTS:
            write(root, f"packages/ports/src/{port}/{part}", f"// {port} {part}\n")
        write(root, f"packages/ports/src/{port}/index.ts", 'import { env } from "@app/env";\n')
    if manifest:
        owned = ["packages/config/src/index.ts", "packages/ports/src/db/wired.ts"]
        files = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in owned}
        write(root, ".stack/generated.json", json.dumps({"generator": "create-next-app",
                                                          "written": TODAY, "files": files,
                                                          "disowned": []}))
    return root


def run(root, *extra, today=TODAY):
    args = [sys.executable, SCRIPT, "--json", "--root", str(root), "--today", today, *extra]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def item(out, cid, level=None):
    for i in out["items"]:
        if i["id"] == cid and (level is None or i["level"] == level):
            return i
    raise AssertionError(f"no {cid} ({level}) in {[(i['id'], i['level']) for i in out['items']]}")


def cost(out, cid):
    return item(out, cid)["measure"]["value"]


class CleanTreeTest(unittest.TestCase):
    def test_a_clean_tree_passes_every_id(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(tree(d))
            self.assertEqual(out["declaration"], "read")
            failing = [i["id"] for i in out["items"] if i["level"] in ("FAIL", "WARN")]
            self.assertEqual(failing, [])
            for cid in drift.MEASURES:
                self.assertEqual(cost(out, cid), 0, cid)


class DeclarationTest(unittest.TestCase):
    def test_a_missing_declaration_counts_every_section_and_leaves_the_rest_unmeasured(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            (root / "stack.yaml").unlink()
            out = run(root)
            self.assertEqual(out["declaration"], "missing")
            self.assertEqual(cost(out, "decl.absent"), 11)
            self.assertIsNone(item(out, "boundary.crossed", "INFO")["measure"]["value"])
            self.assertIsNone(item(out, "lock.incomplete", "INFO")["measure"]["value"])
            # What the tree alone answers is still measured.
            self.assertEqual(cost(out, "adapter.missing"), 0)
            self.assertEqual(cost(out, "decl.undeclared"), 5)

    def test_a_declaration_missing_two_sections_counts_two(self):
        with tempfile.TemporaryDirectory() as d:
            text = "\n".join(l for l in declaration().splitlines()
                             if not l.startswith("waivers:") and not l.startswith("rules:")
                             and not l.startswith("  - no-"))
            out = run(tree(d, decl=text))
            self.assertEqual(cost(out, "decl.absent"), 2)
            self.assertIn("stack.yaml:rules", [r["target"] for r in item(out, "decl.absent")["data"]])

    def test_an_unreadable_declaration_is_unread_never_clean(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(tree(d, decl="base: &a\n  x: 1\n"))
            self.assertTrue(out["declaration"].startswith("unread:"))
            self.assertIsNone(item(out, "decl.absent", "INFO")["measure"]["value"])

    def test_entries_that_point_at_nothing_are_counted_by_their_location(self):
        with tempfile.TemporaryDirectory() as d:
            text = declaration().replace("waivers: []",
                                         "waivers:\n  - kind: type\n    file: packages/gone.ts\n"
                                         "    line: 3\n    reason: x\n    until: 2027-01-01\n    owner: p")
            text = text.replace("  packages/config: []", "  packages/config: []\n  packages/nothere: []")
            out = run(tree(d, decl=text))
            self.assertEqual(cost(out, "decl.unmatched"), 2)
            targets = [r["target"] for r in item(out, "decl.unmatched")["data"]]
            self.assertIn("waivers[0].file", targets)
            self.assertIn("workspaces.packages/nothere", targets)

    def test_generated_files_changed_or_missing_count_and_disowned_ones_do_not(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "packages/config/src/index.ts", "export const TIMEOUT_MS = 1;\n")
            (root / "packages/ports/src/db/wired.ts").unlink()
            out = run(root)
            self.assertEqual(cost(out, "decl.generated"), 2)
            values = {r["target"]: r["value"] for r in item(out, "decl.generated")["data"]}
            self.assertEqual(values["packages/config/src/index.ts"], "changed")
            self.assertEqual(values["packages/ports/src/db/wired.ts"], "missing")
            m = json.loads((root / ".stack/generated.json").read_text())
            m["disowned"] = ["packages/config/src/index.ts"]
            (root / ".stack/generated.json").write_text(json.dumps(m))
            self.assertEqual(cost(out := run(root), "decl.generated"), 1)

    def test_a_missing_manifest_is_a_note_with_no_number(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(tree(d, manifest=False))
            self.assertIsNone(item(out, "decl.generated", "INFO")["measure"]["value"])

    def test_a_package_the_declaration_does_not_name_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "packages/extra/package.json", '{"name": "@app/extra"}')
            self.assertEqual(cost(run(root), "decl.undeclared"), 1)

    def test_an_open_decision_past_its_date_counts_and_a_future_one_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            text = declaration().replace("    until: 2026-12-14\n", "    until: 2026-09-01\n", 1)
            out = run(tree(d, decl=text))
            self.assertEqual(cost(out, "decl.undecided"), 1)
            self.assertEqual(item(out, "decl.undecided")["data"][0]["target"], "admin view")


class LockTest(unittest.TestCase):
    def test_a_dependency_the_lock_does_not_resolve_counts_its_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "packages/ui/package.json",
                  json.dumps({"name": "@app/ui", "dependencies": {"zod": "^3", "left-pad": "^1"}}))
            out = run(root)
            self.assertEqual(cost(out, "lock.incomplete"), 1)
            self.assertEqual(item(out, "lock.incomplete")["data"][0]["value"], "left-pad")

    def test_an_unreadable_lock_is_a_note(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "pnpm-lock.yaml", "a: &x 1\n")
            self.assertIsNone(item(run(root), "lock.incomplete", "INFO")["measure"]["value"])

    def test_pinning_places_that_contradict_the_declaration_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, ".nvmrc", "20\n")
            write(root, "package.json", json.dumps({"name": "demo", "packageManager": "npm@10"}))
            out = run(root)
            self.assertEqual(cost(out, "lock.runtime"), 2)
            targets = [r["target"] for r in item(out, "lock.runtime")["data"]]
            self.assertIn(".nvmrc", targets)
            self.assertIn("package.json packageManager", targets)


class BoundaryTest(unittest.TestCase):
    def test_an_import_over_a_forbidden_edge_names_the_allowed_list(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "packages/ui/src/index.ts", 'import { db } from "@app/ports/db";\n')
            out = run(root)
            self.assertEqual(cost(out, "boundary.crossed"), 1)
            row = item(out, "boundary.crossed")["data"][0]
            self.assertEqual(row["target"], "packages/ui/src/index.ts:1")
            self.assertIn("allowed: packages/config", row["value"])
            self.assertEqual(item(out, "boundary.crossed")["measure"]["by"], {"packages/ui": 1})

    def test_a_boundary_waiver_removes_the_edge(self):
        with tempfile.TemporaryDirectory() as d:
            text = declaration().replace("waivers: []",
                                         "waivers:\n  - kind: boundary\n    file: packages/ui/src/index.ts\n"
                                         "    line: 1\n    reason: moving\n    until: 2027-01-01\n    owner: p")
            root = tree(d, decl=text)
            write(root, "packages/ui/src/index.ts", 'import { db } from "@app/ports/db";\n')
            self.assertEqual(cost(run(root), "boundary.crossed"), 0)

    def test_two_packages_that_import_each_other_are_one_pair(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "packages/ui/src/index.ts", 'import { env } from "@app/env";\n')
            write(root, "packages/env/src/index.ts", 'import { cn } from "@app/ui";\n')
            out = run(root)
            self.assertEqual(cost(out, "boundary.cycle"), 1)
            self.assertEqual(item(out, "boundary.cycle")["data"][0]["target"], "packages/env and packages/ui")

    def test_a_deep_import_counts_and_an_exported_subpath_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "apps/web/app/page.ts",
                  'import { schema } from "@app/env/src/schema";\nimport { db } from "@app/ports/db";\n')
            out = run(root)
            self.assertEqual(cost(out, "boundary.deep-import"), 1)
            self.assertEqual(item(out, "boundary.deep-import")["data"][0]["target"], "apps/web/app/page.ts:1")

    def test_a_vendor_module_outside_its_adapter_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "apps/web/app/page.ts", 'import pg from "pg";\n')
            write(root, "packages/ports/src/db/pool.adapter.ts", 'import pg from "pg";\n')
            out = run(root)
            self.assertEqual(cost(out, "adapter.bypassed"), 1)
            row = item(out, "adapter.bypassed")["data"][0]
            self.assertEqual(row["target"], "apps/web/app/page.ts:1")
            self.assertIn("db/pool", row["value"])


class AdapterTest(unittest.TestCase):
    def test_a_port_missing_its_smoke_test_counts_one_part(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            (root / "packages/ports/src/mail/smoke.test.ts").unlink()
            out = run(root)
            self.assertEqual(cost(out, "adapter.missing"), 1)
            self.assertEqual(item(out, "adapter.missing")["measure"]["by"], {"mail": 1})

    def test_a_port_off_its_axes_counts_unless_an_exception_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(tree(d, decl=declaration(DB="pool")))
            self.assertEqual(cost(out, "adapter.untargeted"), 1)
            self.assertEqual(item(out, "adapter.untargeted")["data"][0]["value"],
                             "declared pool, axes resolve to neon-http")
            text = declaration(DB="pool").replace(
                "port_exceptions: []",
                "port_exceptions:\n  - port: db\n    reason: adopted\n    since: 2026-09-01")
            self.assertEqual(cost(run(tree(d, decl=text)), "adapter.untargeted"), 0)

    def test_full_resolves_storage_to_the_generic_client_everywhere(self):
        self.assertEqual(drift.resolve_adapters("full", "fly")["storage"], "s3")
        self.assertEqual(drift.resolve_adapters("pragmatic", "fly")["storage"], "tigris")
        for level in ("minimal", "pragmatic", "full"):
            for target in ("vercel", "cloudflare", "fly", "hetzner", "railway"):
                self.assertEqual(sorted(drift.resolve_adapters(level, target)), sorted(drift.PORTS))


class SymlinkTest(unittest.TestCase):
    """A symlink is walked, and its real target decides whether it is read at all."""

    def test_a_symlink_escaping_the_root_is_skipped_not_read(self):
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as d:
            secret = Path(outside) / "secret.ts"
            secret.write_text('import pg from "pg";\n', encoding="utf-8")
            root = tree(d)
            link = root / "apps" / "web" / "app" / "escaped.ts"
            try:
                link.symlink_to(secret)
            except OSError:
                self.skipTest("symlinks are not available on this filesystem")
            out = run(root)
            self.assertEqual(cost(out, "adapter.bypassed"), 0)
            self.assertNotIn("escaped.ts", json.dumps(out))

    def test_a_symlink_inside_the_root_is_named_at_the_place_it_stands(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "apps/web/app/real.ts", 'import pg from "pg";\n')
            link = root / "apps" / "web" / "app" / "alias.ts"
            try:
                link.symlink_to(root / "apps" / "web" / "app" / "real.ts")
            except OSError:
                self.skipTest("symlinks are not available on this filesystem")
            out = run(root)
            targets = {r["target"] for r in item(out, "adapter.bypassed")["data"]}
            self.assertIn("apps/web/app/real.ts:1", targets)
            self.assertIn("apps/web/app/alias.ts:1", targets)


class FlagTest(unittest.TestCase):
    def test_accept_removes_a_finding_and_notes_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "packages/extra/package.json", '{"name": "@app/extra"}')
            out = run(root, "--accept", "decl.undeclared packages/extra kept 2026-09-01")
            self.assertEqual(cost(out, "decl.undeclared"), 0)
            self.assertIn("accepted", item(out, "decl.unmatched", "INFO")["message"])

    def test_a_differing_snapshot_is_noted_by_its_keys(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            snap = write(root, "snapshot.yaml", declaration(TARGET="fly"))
            out = run(root, "--snapshot", str(snap))
            note = item(out, "decl.absent", "INFO")
            self.assertIn("target", note["message"])
            self.assertEqual(cost(run(root, "--snapshot", str(snap)), "decl.absent"), 0)


class ContractTest(unittest.TestCase):
    def test_measures_prints_one_id_and_unit_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--measures"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, drift.MEASURES)
        self.assertEqual(len(pairs), 13)

    def test_help_prints_the_docstring(self):
        r = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True, text=True)
        self.assertIn("Whether the tree still matches its declaration", r.stdout)

    def test_the_text_report_has_the_bar_and_one_line_per_finding(self):
        with tempfile.TemporaryDirectory() as d:
            root = tree(d)
            write(root, "packages/extra/package.json", '{"name": "@app/extra"}')
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--today", TODAY],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured against  stack.yaml read", r.stdout)
            self.assertRegex(r.stdout, r"\n\d+ FAIL · \d+ WARN · \d+ notes? · \d+ passed\n")
            self.assertRegex(r.stdout, r"\n +\d+  WARN +decl\.undeclared +1 +package")
            self.assertIn("\nnext  ", r.stdout)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(tree(d)), "--today", TODAY],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


class ChainTest(unittest.TestCase):
    def test_the_chain_names_its_fields_in_the_order_a_person_asks_them(self):
        rep = drift.Report()
        rep.add("FAIL", "boundary.crossed", "one line about it", [], measure=1)
        out = drift.explain_report(rep, "this repository", drift.load_fixes(), "1", None)
        labels = [l.split()[0] for l in out.splitlines() if l and not l.startswith(" ")][1:]
        self.assertEqual(labels, ["what", "weight", "means", "fix", "undo", "verify"])
        self.assertIn("A file imports across an edge", out)
        self.assertIn("review", out)
        self.assertIn("rank 1 of 1", out)

    def test_a_name_no_finding_carries_says_so(self):
        rep = drift.Report()
        rep.add("FAIL", "boundary.crossed", "one line about it", [], measure=1)
        self.assertIn("no finding called nothing.here",
                      drift.explain_report(rep, "this repository", {}, "nothing.here", None))

    def test_the_change_column_reads_the_measure_of_an_earlier_pass(self):
        rep = drift.Report()
        rep.add("FAIL", "boundary.crossed", "one line about it", [], measure=2)
        lines = drift.listing(rep.items, [], drift.load_fixes(), {"boundary.crossed": 1})
        self.assertIn("change", lines[0])
        self.assertRegex(lines[1], r"\+1")
        self.assertRegex(drift.listing(rep.items, [], {}, {})[1], r" new ")

    def test_the_fixes_table_carries_every_id_with_a_class_and_a_rung(self):
        fixes = drift.load_fixes()
        for cid in drift.MEASURES:
            self.assertIn(cid, fixes)
            self.assertIn(fixes[cid]["class"], ("safe", "confirm", "ask"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
