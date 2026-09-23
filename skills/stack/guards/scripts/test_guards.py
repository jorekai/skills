#!/usr/bin/env python3
"""Offline tests for guards.py: the escapes, the guards, the bars, and the report's shape.

Run: python3 skills/stack/guards/scripts/test_guards.py
Every test builds its own tree in a temporary directory from the declaration template of
jorekai-stack:choose; nothing is run, nothing touches the network.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guards  # noqa: E402

SCRIPT = os.path.abspath(guards.__file__)
TODAY = "2026-09-14"
TEMPLATE = Path(SCRIPT).resolve().parents[2] / "choose" / "templates" / "stack.yaml"
DEFAULTS = {"NAME": "demo", "DECLARED": TODAY, "OSS_LEVEL": "pragmatic", "TARGET": "vercel",
            "OSS_CAVEAT": "", "NODE": "22", "PACKAGE_MANAGER": "pnpm@10", "GENERATOR": "create-next-app",
            "DB": "neon-http", "STORAGE": "vercel-blob", "JOBS": "vercel-cron", "HOST": "vercel",
            "AUTH": "better-auth", "MAIL": "resend", "ANALYTICS": "posthog", "ERRORS": "sentry",
            "COVERAGE_LINES": "70", "COVERAGE_BRANCHES": "60", "MAX_FUNCTION_LINES": "60",
            "MAX_FILE_LINES": "400", "MAX_COMPLEXITY": "10", "MAX_PARAMS": "4",
            "DEAD_EXPORTS_MAX": "0", "DEAD_FILES_MAX": "0", "DEAD_DEPS_MAX": "0",
            "GATE_MAX_SECONDS": "90", "DECIDE_BY": "2026-12-01"}
RULES = ("no-raw-env", "no-vendor-outside-adapter", "no-cross-boundary", "no-untimed-fetch",
         "no-floating-promise", "no-test-without-assertion")
GUARD_COMMANDS = ["pnpm exec prettier --check .", "pnpm exec eslint .", "node rules/run.mjs",
                  "node scripts/waivers.mjs", "pnpm exec tsc -b", "pnpm exec vitest run --coverage",
                  "node scripts/dead.mjs", "node scripts/drift.mjs",
                  "gitleaks git . --no-banner --redact", "pnpm exec playwright test"]
BARS = ("coverage_lines", "coverage_branches", "max_function_lines", "max_file_lines",
        "max_complexity", "max_params", "dead_exports_max", "dead_files_max", "dead_deps_max",
        "gate_max_seconds")


def declaration(**over):
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, value in dict(DEFAULTS, **over).items():
        text = text.replace("{{%s}}" % key, value)
    return text


def write(root, path, text):
    p = Path(root) / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def tree(d, owner="@a-person", **over):
    """A tree shaped like a generated repository, without a single tool installed."""
    write(d, "stack.yaml", declaration(**over))
    write(d, "CODEOWNERS", "\n".join(f"{c} {owner}" for c in guards.CONTRACT_FILES) + "\n")
    gate = "#!/usr/bin/env bash\n# reads gate_max_seconds from stack.yaml\n" \
        + "\n".join(f"run_guard {c}" for c in GUARD_COMMANDS) + "\n"
    write(d, "scripts/gate.sh", gate)
    write(d, "scripts/waivers.mjs", "// the scanner holds its patterns as pieces\nconst kinds = ['@ts-' + 'ignore'];\n")
    write(d, "scripts/dead.mjs", "// dead_exports_max dead_files_max dead_deps_max\n")
    write(d, "scripts/drift.mjs", "// hashes\n")
    write(d, "scripts/stack-yaml.mjs", "// reader\n")
    write(d, "rules/run.mjs", "// runner\n")
    write(d, ".github/workflows/gate.yml",
          "name: gate\non: [push]\njobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n"
          "      - run: pnpm install\n      - run: pnpm check\n")
    write(d, "eslint.config.mjs", "// max_function_lines max_file_lines max_complexity max_params\n"
          "export default [{ rules: { complexity: ['error', gates.max_complexity] } }];\n")
    write(d, "vitest.config.ts", "export default { coverage: { thresholds: { lines: gates.coverage_lines, "
          "branches: gates.coverage_branches } }, expect: { requireAssertions: true } };\n")
    write(d, "tsconfig.base.json", '{ "compilerOptions": { "strict": true } }\n')
    write(d, "knip.json", '{ "ignore": [] }\n')
    write(d, "lefthook.yml", "pre-commit:\n  commands:\n    gate:\n      run: bash scripts/gate.sh --staged\n")
    for rid in RULES:
        write(d, f"rules/{rid}.rule.mjs", f"export default {{ id: '{rid}' }};\n")
        write(d, f"rules/{rid}.test.mjs", "export const hit = 'x';\n")
    write(d, "packages/ui/src/index.ts", "export function cn(a: string) {\n  return a;\n}\n")
    write(d, "packages/ui/src/index.test.ts",
          "import { it, expect } from 'vitest';\nit('joins', () => {\n  expect(cn('a')).toBe('a');\n});\n")
    return d


def run(root, *extra, expect=0):
    args = [sys.executable, SCRIPT, "--json", "--today", TODAY, "--root", str(root), *extra]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == expect, r.stdout + r.stderr
    return json.loads(r.stdout)


def item(out, cid, level=None):
    for i in out["items"]:
        if i["id"] == cid and (level is None or i["level"] == level):
            return i
    raise AssertionError(f"no {cid} ({level}) in {[(i['id'], i['level']) for i in out['items']]}")


def cost(out, cid):
    return item(out, cid)["measure"]["value"]


def full_protection(*contexts):
    """A captured branch protection with every guard proved: the contexts, admin bypass off, and
    code owner review required."""
    return json.dumps({"required_status_checks": {"contexts": list(contexts)},
                        "enforce_admins": {"enabled": True},
                        "required_pull_request_reviews": {"require_code_owner_reviews": True}})


def with_waiver(root, kind, file, line, reason="the driver types it as any", until="2026-12-01",
                owner="a-person"):
    p = Path(root) / "stack.yaml"
    entry = f"waivers:\n  - kind: {kind}\n    file: {file}\n    line: {line}\n"
    if reason is not None:
        entry += f'    reason: "{reason}"\n'
    entry += f"    until: {until}\n    owner: {owner}\n"
    p.write_text(p.read_text(encoding="utf-8").replace("waivers: []\n", entry), encoding="utf-8")


class CleanTreeTest(unittest.TestCase):
    def test_a_clean_tree_passes_what_it_can_measure_and_leaves_the_artefacts_null(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(tree(d))
            self.assertEqual(out["declaration"], "read")
            for cid in ("escape.type", "escape.lint", "escape.test", "escape.expired", "escape.unowned",
                        "guard.missing", "guard.disabled", "guard.unwired", "guard.unbarred",
                        "guard.rulegap", "guard.assertionless"):
                self.assertEqual(cost(out, cid), 0, cid)
            # Without a captured protection, a date alone proves nothing: the check is unknown.
            note = item(out, "escape.unenforced", "INFO")
            self.assertIsNone(note["measure"]["value"])
            for cid in ("guard.coverage", "guard.slow", "dead.export", "dead.file", "dead.dep"):
                note = item(out, cid, "INFO")
                self.assertIsNone(note["measure"]["value"])
                self.assertEqual(note["measure"]["unit"], guards.MEASURES[cid])
            self.assertIn("coverage-summary.json", item(out, "guard.coverage")["message"])
            self.assertIn("gate-times.log", item(out, "guard.slow")["message"])
            self.assertIn(".stack/dead.json", item(out, "dead.export")["message"])

    def test_a_missing_declaration_leaves_every_bar_null_and_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            (Path(d) / "stack.yaml").unlink()
            out = run(d)
            self.assertEqual(out["declaration"], "missing")
            for cid in guards.NEEDS_DECLARATION:
                self.assertIsNone(item(out, cid, "INFO")["measure"]["value"], cid)
            self.assertFalse([i for i in out["items"] if i["id"].startswith("decl.")])
            self.assertTrue(any("stack.yaml is missing" in i["message"] for i in out["items"]))

    def test_an_unreadable_declaration_is_unread_and_not_clean(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "stack.yaml", "base: &b\n  x: 1\n")
            out = run(d)
            self.assertTrue(out["declaration"].startswith("unread:"))
            self.assertIsNone(item(out, "guard.rulegap", "INFO")["measure"]["value"])


class EscapeTest(unittest.TestCase):
    """Invariant 8: a suppression is red, a valid waiver makes it green, an expired one red again."""

    def test_a_type_suppression_without_a_waiver_counts_with_file_and_line(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "packages/ui/src/legacy.ts", "const a = 1;\nconst b = a as any;\nexport { b };\n")
            out = run(d)
            self.assertEqual(cost(out, "escape.type"), 1)
            self.assertEqual(item(out, "escape.type")["data"][0]["target"], "packages/ui/src/legacy.ts:2")
            self.assertEqual(item(out, "escape.type")["level"], "FAIL")

    def test_a_valid_waiver_makes_the_same_line_green(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "packages/ui/src/legacy.ts", "const a = 1;\nconst b = a as any;\nexport { b };\n")
            with_waiver(d, "type", "packages/ui/src/legacy.ts", 2)
            out = run(d)
            self.assertEqual(cost(out, "escape.type"), 0)
            self.assertEqual(cost(out, "escape.expired"), 0)

    def test_an_expired_waiver_counts_as_expired_and_not_as_a_suppression(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "packages/ui/src/legacy.ts", "const a = 1;\nconst b = a as any;\nexport { b };\n")
            with_waiver(d, "type", "packages/ui/src/legacy.ts", 2, until="2026-09-01")
            out = run(d)
            self.assertEqual(cost(out, "escape.type"), 0)
            self.assertEqual(cost(out, "escape.expired"), 1)
            self.assertEqual(item(out, "escape.expired")["data"][0]["target"], "packages/ui/src/legacy.ts:2")

    def test_a_waiver_without_a_reason_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "packages/ui/src/legacy.ts", "const a = 1;\nconst b = a as any;\nexport { b };\n")
            with_waiver(d, "type", "packages/ui/src/legacy.ts", 2, reason=None)
            out = run(d)
            self.assertEqual(cost(out, "escape.type"), 1)
            self.assertEqual(cost(out, "escape.expired"), 0)

    def test_a_skipped_test_and_a_lint_suppression_count_under_their_kind(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "packages/ui/src/skip.test.ts",
                  "import { it, expect } from 'vitest';\nit.skip('later', () => {\n  expect(1).toBe(1);\n});\n")
            write(d, "packages/ui/src/lint.ts",
                  "// eslint-disable-next-line max-params\nexport function f(a: number) {\n  return a;\n}\n")
            out = run(d)
            self.assertEqual(cost(out, "escape.test"), 1)
            self.assertEqual(item(out, "escape.test")["data"][0]["target"], "packages/ui/src/skip.test.ts:2")
            self.assertEqual(cost(out, "escape.lint"), 1)
            self.assertEqual(cost(out, "escape.type"), 0)

    def test_the_waiver_scanner_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "scripts/waivers.mjs", "const rx = /@ts-ignore|eslint-disable|it\\.skip\\(/;\n")
            out = run(d)
            for cid in ("escape.type", "escape.lint", "escape.test"):
                self.assertEqual(cost(out, cid), 0, cid)

    def test_an_accepted_finding_leaves_the_count(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "a.ts", "const a = 1;\nconst b = 2;\nconst c = a as any;\nexport { b, c };\n")
            out = run(d, "--accept", "escape.type a.ts:3 the driver 2026-01-01")
            self.assertEqual(cost(out, "escape.type"), 0)
            self.assertTrue(any("accepted" in i["message"] for i in out["items"] if i["level"] == "INFO"))


class EnforcementTest(unittest.TestCase):
    """A date alone in stack.yaml is self-attested, never proof: only a captured protection can
    settle escape.unenforced (the CRITICAL fix), and it now reads enforce_admins and
    require_code_owner_reviews from that capture too."""

    def test_without_a_captured_protection_the_check_is_unknown_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            p = Path(d) / "stack.yaml"
            p.write_text(p.read_text(encoding="utf-8").replace("  - gate\n", "  - gate@2026-09-01\n"),
                         encoding="utf-8")
            out = run(d)
            note = item(out, "escape.unenforced", "INFO")
            self.assertIsNone(note["measure"]["value"])
            self.assertIn("not proof", note["message"])

    def test_an_undated_entry_counts_and_a_dated_one_with_a_full_capture_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            prot = write(d, "prot.json", full_protection("gate"))
            self.assertEqual(cost(run(d, "--protection-file", str(prot)), "escape.unenforced"), 1)
            p = Path(d) / "stack.yaml"
            p.write_text(p.read_text(encoding="utf-8").replace("  - gate\n", "  - gate@2026-09-01\n"),
                         encoding="utf-8")
            self.assertEqual(cost(run(d, "--protection-file", str(prot)), "escape.unenforced"), 0)

    def test_a_captured_protection_without_the_context_counts(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            p = Path(d) / "stack.yaml"
            p.write_text(p.read_text(encoding="utf-8").replace("  - gate\n", "  - gate@2026-09-01\n"),
                         encoding="utf-8")
            prot = write(d, "prot.json", full_protection("lint"))
            self.assertEqual(cost(run(d, "--protection-file", str(prot)), "escape.unenforced"), 1)
            prot.write_text(full_protection("gate"), encoding="utf-8")
            self.assertEqual(cost(run(d, "--protection-file", str(prot)), "escape.unenforced"), 0)

    def test_admin_bypass_on_and_no_required_codeowner_review_each_count_once(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            p = Path(d) / "stack.yaml"
            p.write_text(p.read_text(encoding="utf-8").replace("  - gate\n", "  - gate@2026-09-01\n"),
                         encoding="utf-8")
            prot = write(d, "prot.json", json.dumps(
                {"required_status_checks": {"contexts": ["gate"]},
                 "enforce_admins": {"enabled": False},
                 "required_pull_request_reviews": {"require_code_owner_reviews": False}}))
            out = run(d, "--protection-file", str(prot))
            self.assertEqual(cost(out, "escape.unenforced"), 2)
            found = {r["target"] for r in item(out, "escape.unenforced")["data"]}
            self.assertEqual(found, {"enforce_admins", "require_code_owner_reviews"})

    def test_a_missing_enforcement_section_counts_the_gate(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            p = Path(d) / "stack.yaml"
            p.write_text(p.read_text(encoding="utf-8").replace("enforcement:\n  - gate\n", ""), encoding="utf-8")
            prot = write(d, "prot.json", full_protection("gate"))
            out = run(d, "--protection-file", str(prot))
            self.assertEqual(cost(out, "escape.unenforced"), 1)
            self.assertEqual(item(out, "escape.unenforced")["data"][0]["target"], "gate")


class SymlinkTest(unittest.TestCase):
    """A symlink is walked, and its real target decides whether it is read at all."""

    def test_a_symlink_escaping_the_root_is_skipped_not_read(self):
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as d:
            secret = Path(outside) / "secret.ts"
            secret.write_text("export const x = 1 as any;\n", encoding="utf-8")
            tree(d)
            link = Path(d) / "packages" / "ui" / "src" / "escaped.ts"
            try:
                link.symlink_to(secret)
            except OSError:
                self.skipTest("symlinks are not available on this filesystem")
            out = run(d)
            self.assertEqual(cost(out, "escape.type"), 0)
            self.assertNotIn("escaped.ts", json.dumps(out))

    def test_a_symlink_inside_the_root_is_named_at_the_place_it_stands(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            target = Path(d) / "packages" / "ui" / "src" / "legacy.ts"
            target.write_text("const a = 1;\nconst b = a as any;\nexport { b };\n", encoding="utf-8")
            link = Path(d) / "packages" / "ui" / "src" / "alias.ts"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlinks are not available on this filesystem")
            out = run(d)
            targets = {r["target"] for r in item(out, "escape.type")["data"]}
            self.assertIn("packages/ui/src/legacy.ts:2", targets)
            self.assertIn("packages/ui/src/alias.ts:2", targets)
            self.assertEqual(cost(out, "escape.type"), 2)


class OwnerTest(unittest.TestCase):
    def test_the_placeholder_owner_counts_every_contract_file_that_exists(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d, owner="@OWNER")
            out = run(d)
            found = {r["target"] for r in item(out, "escape.unowned")["data"]}
            self.assertEqual(cost(out, "escape.unowned"), len(guards.contract_paths(Path(d))))
            self.assertIn("stack.yaml", found)
            self.assertIn("rules/", found)

    def test_a_real_owner_counts_nothing_and_a_missing_file_counts_all(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            self.assertEqual(cost(run(d), "escape.unowned"), 0)
            (Path(d) / "CODEOWNERS").unlink()
            out = run(d)
            self.assertEqual(cost(out, "escape.unowned"), len(guards.contract_paths(Path(d))))

    def test_a_directory_pattern_covers_its_files_and_a_glob_covers_a_name(self):
        rules = [("rules/", ["@x"]), (".github/workflows/", ["@x"]), ("*.yaml", ["@x"])]
        self.assertTrue(guards.covered("rules/", rules))
        self.assertTrue(guards.covered(".github/workflows/", rules))
        self.assertTrue(guards.covered("stack.yaml", rules))
        self.assertFalse(guards.covered("knip.json", rules))
        self.assertFalse(guards.covered("stack.yaml", [("stack.yaml", ["@OWNER"])]))


class GuardTest(unittest.TestCase):
    def test_an_empty_command_and_a_missing_script_count_as_missing(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            p = Path(d) / "stack.yaml"
            text = p.read_text(encoding="utf-8").replace('  format: "pnpm exec prettier --check ."\n', '  format: ""\n')
            p.write_text(text, encoding="utf-8")
            (Path(d) / "scripts" / "drift.mjs").unlink()
            out = run(d)
            self.assertEqual(cost(out, "guard.missing"), 2)
            self.assertEqual({r["target"] for r in item(out, "guard.missing")["data"]}, {"format", "drift"})

    def test_a_workflow_that_runs_only_lint_leaves_the_other_guards_unwired(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, ".github/workflows/gate.yml",
                  "name: gate\non: [push]\njobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n"
                  "      - run: pnpm exec eslint .\n")
            out = run(d)
            self.assertEqual(cost(out, "guard.unwired"), 9)
            self.assertNotIn("lint", {r["target"] for r in item(out, "guard.unwired")["data"]})

    def test_no_workflow_at_all_leaves_every_guard_unwired(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            (Path(d) / ".github" / "workflows" / "gate.yml").unlink()
            self.assertEqual(cost(run(d), "guard.unwired"), 10)

    def test_a_bar_that_left_its_file_is_unbarred(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "eslint.config.mjs", "// max_file_lines max_complexity max_params\n")
            out = run(d)
            self.assertEqual(cost(out, "guard.unbarred"), 1)
            self.assertEqual(item(out, "guard.unbarred")["data"][0]["target"], "max_function_lines")

    def test_a_switch_in_a_configuration_counts_as_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "tsconfig.base.json", '{ "compilerOptions": { "strict": false } }\n')
            write(d, "knip.json", '{ "ignore": ["packages/**"] }\n')
            out = run(d)
            self.assertEqual(cost(out, "guard.disabled"), 2)
            self.assertEqual(item(out, "guard.disabled")["level"], "WARN")

    def test_a_commented_step_in_the_gate_counts_as_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            gate = (Path(d) / "scripts" / "gate.sh").read_text(encoding="utf-8")
            write(d, "scripts/gate.sh", gate.replace("run_guard node scripts/dead.mjs", "# run_guard node scripts/dead.mjs"))
            self.assertEqual(cost(run(d), "guard.disabled"), 1)

    def test_a_rule_without_a_test_is_a_gap(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            (Path(d) / "rules" / "no-raw-env.test.mjs").unlink()
            out = run(d)
            self.assertEqual(cost(out, "guard.rulegap"), 1)
            self.assertEqual(item(out, "guard.rulegap")["data"][0], {"target": "no-raw-env", "value": "no test"})

    def test_a_test_block_without_an_assertion_counts(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "packages/ui/src/empty.test.ts",
                  "import { it, expect } from 'vitest';\nit('does nothing', async () => {\n  await cn('a');\n});\n"
                  "it('asserts', () => {\n  expect(1).toBe(1);\n});\n")
            out = run(d)
            self.assertEqual(cost(out, "guard.assertionless"), 1)
            self.assertEqual(item(out, "guard.assertionless")["data"][0]["target"], "packages/ui/src/empty.test.ts:2")


class BarTest(unittest.TestCase):
    def test_coverage_below_the_bar_is_measured_in_points(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "coverage/coverage-summary.json",
                  json.dumps({"total": {"lines": {"pct": 65}, "branches": {"pct": 70}}}))
            out = run(d)
            self.assertEqual(cost(out, "guard.coverage"), 5)
            self.assertEqual(item(out, "guard.coverage")["measure"]["unit"], "percent")
            self.assertEqual(item(out, "guard.coverage")["level"], "WARN")

    def test_coverage_at_the_bar_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "coverage/coverage-summary.json",
                  json.dumps({"total": {"lines": {"pct": 70}, "branches": {"pct": 60}}}))
            self.assertEqual(cost(run(d), "guard.coverage"), 0)

    def test_a_slow_gate_is_measured_in_seconds_over_the_bar(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, ".stack/gate-times.log", "2026-09-13T10:00:00 40 full\n2026-09-14T10:00:00 120 full\n")
            out = run(d)
            self.assertEqual(cost(out, "guard.slow"), 30)
            self.assertEqual(item(out, "guard.slow")["measure"]["unit"], "seconds")
            write(d, ".stack/gate-times.log", "2026-09-14T10:00:00 80 full\n")
            self.assertEqual(cost(run(d), "guard.slow"), 0)

    def test_dead_code_over_the_bar_counts_and_inside_it_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, ".stack/dead.json", json.dumps({"exports": 3, "files": 0, "dependencies": 1}))
            out = run(d)
            self.assertEqual(cost(out, "dead.export"), 3)
            self.assertEqual(cost(out, "dead.file"), 0)
            self.assertEqual(item(out, "dead.file")["level"], "PASS")
            self.assertEqual(cost(out, "dead.dep"), 1)


class SnapshotTest(unittest.TestCase):
    def test_a_differing_snapshot_adds_a_note_naming_the_keys(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            snap = write(d, "snap.yaml", declaration(TARGET="fly"))
            out = run(d, "--snapshot", str(snap))
            notes = [i["message"] for i in out["items"] if "snapshot" in i["message"]]
            self.assertEqual(len(notes), 1)
            self.assertIn("target", notes[0])
            same = write(d, "same.yaml", declaration())
            out = run(d, "--snapshot", str(same))
            self.assertFalse([i for i in out["items"] if "snapshot" in i["message"]])


class ContractTest(unittest.TestCase):
    def test_measures_prints_one_id_and_unit_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--measures"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, guards.MEASURES)
        self.assertEqual(len(pairs), 17)

    def test_help_prints_the_docstring(self):
        r = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True, text=True)
        self.assertIn("Do the guards of a generated repository still stand", r.stdout)

    def test_the_text_report_has_the_bar_one_line_per_finding_and_a_next_step(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            write(d, "a.ts", "const a = 1;\nexport const b = a as any;\n")
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--today", TODAY],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured against  stack.yaml read", r.stdout)
            self.assertRegex(r.stdout, r"\n\d+ FAIL · \d+ WARN · \d+ notes? · \d+ passed\n")
            self.assertRegex(r.stdout, r"\n +\d+  FAIL +escape\.type +1 suppression")
            self.assertNotIn("(costs", r.stdout)
            self.assertIn("\nnext  ", r.stdout)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", tree(d), "--today", TODAY],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


class ChainTest(unittest.TestCase):
    """The list answers what and how heavy, `--explain` answers the rest, one finding at a time."""

    def test_the_chain_names_its_fields_in_the_order_a_person_asks_them(self):
        rep = guards.Report()
        rep.add("FAIL", "escape.type", "one line about it", [{"target": "a.ts:2", "value": "as any"}], measure=1)
        out = guards.explain_report(rep, "demo", guards.load_fixes(), "1", None)
        labels = [l.split()[0] for l in out.splitlines() if l and not l.startswith(" ")][1:]
        self.assertEqual(labels, ["what", "weight", "means", "fix", "undo", "verify"])
        self.assertIn("A type suppression stands in the code", out)
        self.assertIn("review", out)
        self.assertIn("rank 1 of 1", out)

    def test_explain_by_rank_from_the_command_line(self):
        with tempfile.TemporaryDirectory() as d:
            tree(d)
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--today", TODAY, "--explain", "1"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("escape.unenforced", r.stdout)
            self.assertIn("verify", r.stdout)

    def test_a_name_no_finding_carries_says_so(self):
        rep = guards.Report()
        rep.add("FAIL", "escape.type", "one line about it", [], measure=1)
        self.assertIn("no finding called nothing.here",
                      guards.explain_report(rep, "demo", {}, "nothing.here", None))

    def test_the_change_column_reads_the_measure_of_an_earlier_pass(self):
        rep = guards.Report()
        rep.add("FAIL", "escape.type", "one line about it", [], measure=2)
        lines = guards.listing(rep.items, [], guards.load_fixes(), {"escape.type": 1})
        self.assertIn("change", lines[0])
        self.assertRegex(lines[1], r"\+1")
        self.assertRegex(guards.listing(rep.items, [], {}, {})[1], r" new ")

    def test_every_id_has_a_row_in_the_fixes_table(self):
        fixes = guards.load_fixes()
        for cid in guards.MEASURES:
            self.assertIn(cid, fixes)
            self.assertIn("fix", fixes[cid])


if __name__ == "__main__":
    unittest.main(verbosity=1)
