#!/usr/bin/env python3
"""Offline tests for lay.py: the plan, the manifest, the wire, the adoption, and the invariants.

Run: python3 skills/stack/new/scripts/test_lay.py
Every test lays a repository out in a temporary directory from the declaration template of the
choose skill. No generator runs, no network; the app directory is a fake manifest.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lay  # noqa: E402

SCRIPT = os.path.abspath(lay.__file__)
SKILLS = Path(SCRIPT).resolve().parents[3]
STACK_TEMPLATE = SKILLS / "stack" / "choose" / "templates" / "stack.yaml"
REFERENCES = SKILLS / "stack" / "stack" / "references"
TEMPLATES = lay.TEMPLATES
TODAY = "2026-09-14"
DEFAULTS = {"NAME": "demo", "DECLARED": TODAY, "OSS_LEVEL": "pragmatic", "TARGET": "vercel",
            "OSS_CAVEAT": "", "NODE": "22", "PACKAGE_MANAGER": "pnpm@10",
            "GENERATOR": "create-next-app", "DB": "neon-http", "STORAGE": "vercel-blob",
            "JOBS": "vercel-cron", "HOST": "vercel", "AUTH": "better-auth", "MAIL": "resend",
            "ANALYTICS": "posthog", "ERRORS": "sentry", "COVERAGE_LINES": "70",
            "COVERAGE_BRANCHES": "60", "MAX_FUNCTION_LINES": "60", "MAX_FILE_LINES": "400",
            "MAX_COMPLEXITY": "10", "MAX_PARAMS": "4", "DEAD_EXPORTS_MAX": "0",
            "DEAD_FILES_MAX": "0", "DEAD_DEPS_MAX": "0", "GATE_MAX_SECONDS": "90",
            "DECIDE_BY": "2026-12-14"}
PORTS_READY = (TEMPLATES / "packages" / "ports" / "package.json").is_file() \
    and (TEMPLATES / "ports" / "db").is_dir()


def declaration(**over):
    text = STACK_TEMPLATE.read_text(encoding="utf-8")
    for k, v in {**DEFAULTS, **over}.items():
        text = text.replace("{{%s}}" % k, v)
    return text


def repo(d, with_app=True, **over):
    root = Path(d) / "demo"
    root.mkdir()
    (root / "stack.yaml").write_text(declaration(**over), encoding="utf-8")
    if with_app:
        (root / "apps" / "web").mkdir(parents=True)
        (root / "apps" / "web" / "package.json").write_text('{"name": "web"}\n', encoding="utf-8")
        (root / "apps" / "web" / "tsconfig.json").write_text("{}\n", encoding="utf-8")
        (root / "apps" / "web" / "eslint.config.mjs").write_text("export default [];\n", encoding="utf-8")
    return root


def run(*args, expect=0):
    r = subprocess.run([sys.executable, SCRIPT, "--today", TODAY, *args], capture_output=True, text=True)
    assert r.returncode == expect, f"exit {r.returncode}: {r.stdout}{r.stderr}"
    return r.stdout + r.stderr


def manifest(root):
    return json.loads((root / lay.MANIFEST).read_text(encoding="utf-8"))


class PlanTest(unittest.TestCase):
    def test_the_plan_writes_nothing_and_names_every_action(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            out = run("--root", str(root), "--plan")
            self.assertIn("scripts/gate.sh", out)
            self.assertIn("| write", out)
            self.assertIn("apps/web/tsconfig.json", out)
            self.assertIn("| replace", out)
            self.assertIn("apps/web/eslint.config.mjs", out)
            self.assertIn("| remove", out)
            self.assertFalse((root / "scripts" / "gate.sh").exists())

    def test_without_a_declaration_nothing_runs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "empty"
            root.mkdir()
            self.assertIn("no stack.yaml", run("--root", str(root), "--plan", expect=1))

    def test_the_app_files_wait_for_the_generator(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d, with_app=False)
            out = run("--root", str(root))
            self.assertIn("run the generator", out)
            self.assertFalse((root / "apps" / "web" / "tsconfig.json").exists())
            self.assertTrue((root / "scripts" / "gate.sh").exists())


class LayTest(unittest.TestCase):
    def test_lay_writes_the_tree_and_the_manifest_and_check_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            run("--root", str(root))
            m = manifest(root)
            self.assertIn("scripts/gate.sh", m["files"])
            self.assertNotIn("rules/no-raw-env.rule.mjs", m["files"])
            self.assertNotIn("packages/ui/src/index.ts", m["files"])
            self.assertIn("apps/web/tsconfig.json", m["files"])
            self.assertFalse((root / "apps" / "web" / "eslint.config.mjs").exists())
            self.assertIn("extends", (root / "apps" / "web" / "tsconfig.json").read_text(encoding="utf-8"))
            self.assertIn("demo", (root / "package.json").read_text(encoding="utf-8"))
            self.assertIn("@OWNER", (root / "CODEOWNERS").read_text(encoding="utf-8"))
            self.assertTrue(os.access(root / "scripts" / "gate.sh", os.X_OK))
            if PORTS_READY:
                self.assertIn("ok", run("--root", str(root), "--check"))

    def test_a_hand_edit_of_an_owned_file_fails_check_and_lay_leaves_it_alone(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            run("--root", str(root))
            gate = root / "scripts" / "gate.sh"
            gate.write_text(gate.read_text(encoding="utf-8") + "# by hand\n", encoding="utf-8")
            out = run("--root", str(root), "--check", expect=1)
            self.assertIn("changed", out)
            self.assertIn("scripts/gate.sh", out)
            out = run("--root", str(root), "--plan")
            self.assertRegex(out, r"scripts/gate\.sh\s+\| skip\s+\| changed by hand")
            run("--root", str(root))
            self.assertIn("# by hand", gate.read_text(encoding="utf-8"))

    def test_a_project_file_that_exists_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            (root / "rules").mkdir()
            (root / "rules" / "no-raw-env.rule.mjs").write_text("// mine\n", encoding="utf-8")
            run("--root", str(root))
            self.assertEqual((root / "rules" / "no-raw-env.rule.mjs").read_text(encoding="utf-8"), "// mine\n")

    def test_disown_takes_a_file_out_of_the_drift_check(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            run("--root", str(root))
            run("--root", str(root), "--disown", "scripts/gate.sh")
            self.assertIn("scripts/gate.sh", manifest(root)["disowned"])
            gate = root / "scripts" / "gate.sh"
            gate.write_text("# mine\n", encoding="utf-8")
            out = run("--root", str(root), "--check", expect=0 if PORTS_READY else 1)
            self.assertNotIn("scripts/gate.sh", out)
            self.assertIn("not a generated file", run("--root", str(root), "--disown", "nope.txt", expect=1))

    def test_flags_print_the_generator_command_and_the_adapters(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            out = run("--root", str(root), "--flags")
            self.assertIn("create-next-app@latest apps/web", out)
            self.assertIn("--skip-install", out)
            self.assertIn("db=neon-http", out)
            self.assertIn("auth=better-auth", out)


@unittest.skipUnless(PORTS_READY, "the port templates are written by another skill build")
class WireTest(unittest.TestCase):
    def test_wire_copies_the_adapters_the_axes_resolve_to(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            run("--root", str(root))
            out = run("--root", str(root), "--wire")
            expected = {"db": "neon-http", "storage": "vercel-blob", "jobs": "vercel-cron",
                        "host": "vercel", "auth": "better-auth", "mail": "resend",
                        "analytics": "posthog", "errors": "sentry"}
            for port, adapter in expected.items():
                self.assertTrue((root / lay.PORT_DIR / port / f"{adapter}{lay.ADAPTER_SUFFIX}").is_file(), port)
                wired = (root / lay.PORT_DIR / port / "wired.ts").read_text(encoding="utf-8")
                self.assertIn(f"./{adapter}.adapter", wired)
                self.assertNotIn("./memory.adapter", wired)
            pkg = json.loads((root / "packages" / "ports" / "package.json").read_text(encoding="utf-8"))
            self.assertIn("@neondatabase/serverless", pkg["dependencies"])
            self.assertIn("@vercel/blob", pkg["dependencies"])
            self.assertIn("better-auth", pkg["dependencies"])
            self.assertNotIn("pg", pkg["dependencies"])
            self.assertTrue((root / "scripts" / "wizard.sh").is_file())
            self.assertIn("pnpm install", out)
            self.assertIn("ok", run("--root", str(root), "--check"))

    def test_full_on_hetzner_wires_the_generic_store_and_the_relay(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d, OSS_LEVEL="full", TARGET="hetzner", STORAGE="s3", MAIL="smtp",
                        DB="pool", JOBS="systemd-timer", HOST="docker")
            run("--root", str(root))
            run("--root", str(root), "--wire")
            self.assertTrue((root / lay.PORT_DIR / "storage" / f"s3{lay.ADAPTER_SUFFIX}").is_file())
            self.assertTrue((root / lay.PORT_DIR / "mail" / f"smtp{lay.ADAPTER_SUFFIX}").is_file())
            self.assertTrue((root / "Dockerfile").is_file())


class AdoptTest(unittest.TestCase):
    def test_adopt_leaves_files_alone_and_proposes_a_waiver_per_suppression(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            (root / "scripts").mkdir()
            (root / "scripts" / "gate.sh").write_text("#!/bin/bash\necho mine\n", encoding="utf-8")
            (root / "packages" / "ui" / "src").mkdir(parents=True)
            (root / "packages" / "ui" / "src" / "legacy.ts").write_text(
                "export const x = (y as any).z;\nit.skip('later', () => {});\n", encoding="utf-8")
            out = run("--root", str(root), "--adopt", "--plan")
            self.assertRegex(out, r"scripts/gate\.sh\s+\| skip\s+\| exists, left alone")
            self.assertIn("2 suppression(s)", out)
            self.assertNotIn("waivers:\n  - kind", (root / "stack.yaml").read_text(encoding="utf-8"))
            out = run("--root", str(root), "--adopt")
            self.assertEqual((root / "scripts" / "gate.sh").read_text(encoding="utf-8"), "#!/bin/bash\necho mine\n")
            text = (root / "stack.yaml").read_text(encoding="utf-8")
            self.assertIn("  - kind: type\n    file: packages/ui/src/legacy.ts\n    line: 1\n", text)
            self.assertIn("  - kind: test\n    file: packages/ui/src/legacy.ts\n    line: 2\n", text)
            self.assertIn("until: 2026-12-13", text)
            self.assertIn('reason: ""', text)
            self.assertIn("nothing measured yet", out)
            self.assertNotIn("gate.sh", manifest(root)["files"])

    def test_adopt_sets_the_bars_from_what_the_gate_measured(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            (root / ".stack").mkdir()
            (root / ".stack" / "dead.json").write_text('{"exports": 7, "files": 2, "dependencies": 1}', encoding="utf-8")
            (root / "coverage").mkdir()
            (root / "coverage" / "coverage-summary.json").write_text(
                '{"total": {"lines": {"pct": 43.5}, "branches": {"pct": 31}}}', encoding="utf-8")
            run("--root", str(root), "--adopt")
            text = (root / "stack.yaml").read_text(encoding="utf-8")
            self.assertIn("dead_exports_max: 7", text)
            self.assertIn("dead_files_max: 2", text)
            self.assertIn("dead_deps_max: 1", text)
            self.assertIn("coverage_lines: 43", text)
            self.assertIn("coverage_branches: 31", text)


def adapters_in_tables():
    out = set()
    for port, table in lay.BY_TARGET.items():
        out |= {(port, a) for a in table.values()}
    for port, table in lay.BY_LEVEL.items():
        out |= {(port, a) for a in table.values()}
    out.add(("storage", "s3"))
    return out


class InvariantTest(unittest.TestCase):
    """Both directions, because one direction proves nothing."""

    @unittest.skipUnless(PORTS_READY, "the port templates are written by another skill build")
    def test_every_adapter_in_the_tables_has_a_template_and_the_other_way_round(self):
        expected = {f"{p}/{a}" for p, a in adapters_in_tables()}
        found = {f"{p.parent.name}/{p.name[:-len(lay.ADAPTER_SUFFIX)]}"
                 for p in (TEMPLATES / "ports").glob(f"*/*{lay.ADAPTER_SUFFIX}")
                 if p.name != "memory" + lay.ADAPTER_SUFFIX}
        self.assertEqual(expected - found, set(), "adapters in the tables with no template")
        self.assertEqual(found - expected, set(), "templates no table names")
        for port in lay.PORTS:
            self.assertTrue((TEMPLATES / "ports" / port / ("memory" + lay.ADAPTER_SUFFIX)).is_file(), port)

    def test_every_env_key_stands_in_the_schema_and_the_example_and_nothing_else_does(self):
        keys = {f"{p.upper()}_{s}" for p in lay.PORTS for s in ("URL", "KEY")}
        schema = (TEMPLATES / "packages" / "env" / "src" / "schema.ts").read_text(encoding="utf-8")
        example = (TEMPLATES / "root" / ".env.example").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"^\s*([A-Z]+_(?:URL|KEY)):", schema, re.M)), keys)
        self.assertEqual(set(re.findall(r"^([A-Z]+_(?:URL|KEY))=", example, re.M)), keys)

    def test_every_bar_stands_in_the_file_that_carries_it(self):
        where = {"coverage_lines": "root/vitest.config.ts", "coverage_branches": "root/vitest.config.ts",
                 "max_function_lines": "root/eslint.config.mjs", "max_file_lines": "root/eslint.config.mjs",
                 "max_complexity": "root/eslint.config.mjs", "max_params": "root/eslint.config.mjs",
                 "dead_exports_max": "root/scripts/dead.mjs", "dead_files_max": "root/scripts/dead.mjs",
                 "dead_deps_max": "root/scripts/dead.mjs", "gate_max_seconds": "root/scripts/gate.sh"}
        bars = set(re.findall(r"^  ([a-z_]+): \{\{", STACK_TEMPLATE.read_text(encoding="utf-8"), re.M))
        bars = {b for b in bars if b in where}
        self.assertEqual(bars, set(where))
        for bar, rel in where.items():
            self.assertIn(bar, (TEMPLATES / rel).read_text(encoding="utf-8"), f"{bar} not in {rel}")

    def test_every_axis_pair_resolves_to_eight_adapters(self):
        for level in lay.LEVELS:
            for target in lay.TARGETS:
                adapters = lay.resolve(level, target)
                self.assertEqual(set(adapters), set(lay.PORTS))
                self.assertTrue(all(adapters.values()), (level, target))
                if PORTS_READY:
                    for port, adapter in adapters.items():
                        self.assertTrue((TEMPLATES / "ports" / port / f"{adapter}{lay.ADAPTER_SUFFIX}").is_file(),
                                        (level, target, port, adapter))
        self.assertEqual(lay.resolve("full", "vercel")["storage"], "s3")

    def test_every_contract_file_stands_in_codeowners(self):
        table = (REFERENCES / "contracts.md").read_text(encoding="utf-8").split("## Contract files", 1)[1]
        table = table.split("## Generated", 1)[0]
        listed = re.findall(r"^\| `([^`]+)` \|", table, re.M)
        owners = (TEMPLATES / "root" / "CODEOWNERS").read_text(encoding="utf-8")
        self.assertGreater(len(listed), 5)
        for path in listed:
            self.assertRegex(owners, r"(?m)^/?" + re.escape(path.rstrip("/")) + r"/? ", path)

    def test_every_rule_has_a_test_and_the_declaration_names_exactly_those(self):
        rules = {p.name[:-len(".rule.mjs")] for p in (TEMPLATES / "root" / "rules").glob("*.rule.mjs")}
        tests = {p.name[:-len(".test.mjs")] for p in (TEMPLATES / "root" / "rules").glob("*.test.mjs")}
        self.assertEqual(rules, tests)
        text = STACK_TEMPLATE.read_text(encoding="utf-8")
        section = text.split("\nrules:\n", 1)[1].split("\n\n", 1)[0]
        declared = set(re.findall(r"^  - (no-[a-z-]+)$", section, re.M))
        self.assertEqual(declared, rules)


@unittest.skipUnless(shutil.which("node"), "the rule engine and the waiver check run on node")
class NodeTest(unittest.TestCase):
    def test_the_rules_prove_themselves_and_the_waiver_check_turns_red_on_a_suppression(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            run("--root", str(root))
            r = subprocess.run(["node", "rules/run.mjs", "--self-test"], cwd=root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("proved by their tests", r.stdout)
            (root / "packages" / "ui" / "src" / "bad.ts").write_text("export const x = (y as any).z;\n", encoding="utf-8")
            r = subprocess.run(["node", "scripts/waivers.mjs"], cwd=root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("packages/ui/src/bad.ts:1  escape.type", r.stdout)
            self.assertIn("allowed: a waiver in stack.yaml", r.stdout)
            text = (root / "stack.yaml").read_text(encoding="utf-8")
            waiver = ("waivers:\n  - kind: type\n    file: packages/ui/src/bad.ts\n    line: 1\n"
                      '    reason: "the type comes from a driver"\n    until: 2099-01-01\n    owner: someone')
            (root / "stack.yaml").write_text(text.replace("waivers: []", waiver), encoding="utf-8")
            r = subprocess.run(["node", "scripts/waivers.mjs"], cwd=root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            expired = (root / "stack.yaml").read_text(encoding="utf-8").replace("until: 2099-01-01", "until: 2020-01-01")
            (root / "stack.yaml").write_text(expired, encoding="utf-8")
            r = subprocess.run(["node", "scripts/waivers.mjs"], cwd=root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("expired", r.stdout)

    def test_the_rule_engine_names_file_line_and_the_allowed_state(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            run("--root", str(root))
            (root / "packages" / "ui" / "src" / "raw.ts").write_text("export const u = process.env.DB_URL;\n", encoding="utf-8")
            r = subprocess.run(["node", "rules/run.mjs"], cwd=root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("packages/ui/src/raw.ts:1  no-raw-env", r.stdout)
            self.assertIn('allowed: import { env } from "@app/env"', r.stdout)
            (root / "packages" / "ui" / "src" / "raw.ts").unlink()
            r = subprocess.run(["node", "rules/run.mjs"], cwd=root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ContractTest(unittest.TestCase):
    def test_help_prints_the_docstring(self):
        self.assertIn("Lay the guards of a declared repository", run("--help"))

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            self.assertNotIn("\033[", run("--root", str(root), "--plan"))

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            root = repo(d)
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--plan"],
                               capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
