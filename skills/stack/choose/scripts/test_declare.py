#!/usr/bin/env python3
"""Offline tests for declare.py: the resolution of the axes, the profiles, the written file.

Run: python3 skills/stack/choose/scripts/test_declare.py
The written file is read back with the same subset reader the passes use, copied from the
pipeline pass of jorekai-security, so a template the reader cannot follow fails here.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import declare  # noqa: E402

SCRIPT = os.path.abspath(declare.__file__)
TODAY = "2026-09-14"


class Unsupported(Exception):
    """The reader met a construction it does not parse. The file counts as unread, not as clean."""


def strip_comment(line):
    """The line without a trailing comment. A `#` inside quotes is content, not a comment."""
    out, quote, i = [], "", 0
    while i < len(line):
        c = line[i]
        if quote:
            out.append(c)
            if c == "\\" and quote == '"' and i + 1 < len(line):
                out.append(line[i + 1])
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "'\"":
            quote = c
            out.append(c)
        elif c == "#" and (not out or out[-1] in " \t"):
            break
        else:
            out.append(c)
        i += 1
    return "".join(out).rstrip()


def unquote(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text


KEY = re.compile(r"^((?:\"[^\"]*\")|(?:'[^']*')|(?:[^:#]+?))\s*:(?:\s+(.*))?$")
BLOCK = re.compile(r"^[|>][+-]?\d*$")


def tokenize(text):
    """Lines that carry content, as (indent, body, raw).

    `raw` keeps what a comment marker would have removed, because a script inside a block scalar
    is not this format's comment: the runner substitutes an expression before a shell sees the
    line, so an expression behind a `#` is still substituted. Everything a reader cannot follow
    raises, and the file counts as unread.
    """
    out = []
    for raw in text.splitlines():
        if "\t" in raw[:len(raw) - len(raw.lstrip())]:
            raise Unsupported("a tab in the indentation")
        stripped = strip_comment(raw)
        if not stripped.strip():
            continue
        if stripped.strip() in ("---", "..."):
            raise Unsupported("more than one document")
        indent = len(stripped) - len(stripped.lstrip())
        body = stripped.strip()
        if body.startswith(("&", "*")) or re.search(r":\s+[&*]\w", body) or body.startswith("<<:"):
            raise Unsupported("an anchor, an alias, or a merge key")
        out.append((indent, body, raw.strip()))
    return out


def flow(text):
    """A flow sequence or mapping on one line, the shallow way these files use it."""
    inner = text[1:-1].strip()
    parts, depth, current, quote = [], 0, [], ""
    for c in inner:
        if quote:
            current.append(c)
            if c == quote:
                quote = ""
            continue
        if c in "'\"":
            quote = c
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(c)
    if "".join(current).strip():
        parts.append("".join(current))
    if text.startswith("["):
        return [scalar(p.strip()) for p in parts]
    out = {}
    for p in parts:
        k, _, v = p.partition(":")
        out[unquote(k)] = scalar(v.strip())
    return out


def scalar(text):
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return flow(text)
    if text.startswith("{") and text.endswith("}"):
        return flow(text)
    return unquote(text)


def block_scalar(lines, pos, indent):
    """The lines of a `|` or `>` scalar, joined. Only the text matters here, never the folding."""
    body = []
    while pos < len(lines) and lines[pos][0] > indent:
        body.append(lines[pos][2])
        pos += 1
    return "\n".join(body), pos


def parse_block(lines, pos, indent):
    """One mapping or one sequence at `indent`, and the position after it."""
    if pos >= len(lines):
        return None, pos
    if lines[pos][1].startswith("-"):
        return parse_seq(lines, pos, indent)
    return parse_map(lines, pos, indent)


def parse_seq(lines, pos, indent):
    out = []
    while pos < len(lines) and lines[pos][0] == indent and lines[pos][1].startswith("-"):
        ind, body = lines[pos][0], lines[pos][1]
        m = re.match(r"-(\s*)(.*)$", body)
        rest, inner = m.group(2), ind + 1 + len(m.group(1))
        pos += 1
        if not rest:
            value, pos = parse_block(lines, pos, lines[pos][0]) if pos < len(lines) \
                and lines[pos][0] > ind else (None, pos)
            out.append(value)
            continue
        if KEY.match(rest):
            sub = [(inner, rest, rest)] + [lines[i] for i in range(pos, len(lines))
                                           if lines[i][0] >= inner]
            take = 0
            while pos + take < len(lines) and lines[pos + take][0] >= inner:
                take += 1
            value, _ = parse_map(sub[:take + 1], 0, inner)
            pos += take
            out.append(value)
            continue
        out.append(scalar(rest))
    return out, pos


def parse_map(lines, pos, indent):
    out = {}
    while pos < len(lines) and lines[pos][0] == indent:
        ind, body = lines[pos][0], lines[pos][1]
        m = KEY.match(body)
        if not m:
            raise Unsupported(f"a line that is not a key: {body[:40]!r}")
        key, rest = unquote(m.group(1)), (m.group(2) or "").strip()
        pos += 1
        if BLOCK.fullmatch(rest):
            out[key], pos = block_scalar(lines, pos, ind)
            continue
        if rest:
            out[key] = scalar(rest)
            continue
        if pos < len(lines) and lines[pos][0] > ind:
            out[key], pos = parse_block(lines, pos, lines[pos][0])
        else:
            out[key] = None
    return out, pos


def parse_yaml(text):
    """The subset of the format these checks need. Anything else raises Unsupported."""
    lines = tokenize(text)
    if not lines:
        return {}
    value, pos = parse_block(lines, 0, lines[0][0])
    if pos != len(lines):
        raise Unsupported("a block that does not line up with the one above it")
    return value



def run(*args, expect=0):
    r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    assert r.returncode == expect, f"exit {r.returncode}: {r.stdout}{r.stderr}"
    return r.stdout + r.stderr


def written(d, *extra):
    run("--root", d, "--oss", "pragmatic", "--target", "vercel", "--today", TODAY, *extra)
    return (Path(d) / "stack.yaml").read_text(encoding="utf-8")


class ResolveTest(unittest.TestCase):
    def test_all_fifteen_pairs_resolve_to_eight_adapters(self):
        for level in declare.LEVELS:
            for target in declare.TARGETS:
                ports, _ = declare.resolve(level, target)
                self.assertEqual(sorted(ports), sorted(declare.PORTS), (level, target))
                self.assertTrue(all(ports.values()), (level, target))

    def test_full_puts_storage_on_the_generic_client_everywhere(self):
        for target in declare.TARGETS:
            self.assertEqual(declare.resolve("full", target)[0]["storage"], "s3", target)
        self.assertEqual(declare.resolve("pragmatic", "vercel")[0]["storage"], "vercel-blob")

    def test_the_caveat_stands_only_where_full_meets_a_target_without_a_server(self):
        self.assertTrue(declare.resolve("full", "vercel")[1])
        self.assertTrue(declare.resolve("full", "cloudflare")[1])
        self.assertEqual(declare.resolve("full", "fly")[1], "")
        self.assertEqual(declare.resolve("pragmatic", "vercel")[1], "")

    def test_each_port_hangs_on_one_axis(self):
        both = set(declare.BY_TARGET) & set(declare.BY_LEVEL)
        self.assertEqual(both, set())
        self.assertEqual(set(declare.BY_TARGET) | set(declare.BY_LEVEL), set(declare.PORTS))

    def test_an_unknown_axis_value_is_refused_with_the_allowed_list(self):
        out = run("--root", ".", "--oss", "huge", "--target", "vercel", "--show", expect=1)
        self.assertIn("minimal, pragmatic, full", out)
        out = run("--root", ".", "--oss", "full", "--target", "moon", "--show", expect=1)
        self.assertIn("vercel, cloudflare, fly, hetzner, railway", out)

    def test_an_unknown_generator_is_refused_with_the_allowed_list(self):
        out = run("--root", ".", "--oss", "pragmatic", "--target", "vercel", "--generator", "vite",
                  "--show", expect=1)
        self.assertIn("create-next-app", out)

    def test_an_unknown_package_manager_is_refused_with_the_allowed_list(self):
        out = run("--root", ".", "--oss", "pragmatic", "--target", "vercel", "--package-manager",
                  "npm@10", "--show", expect=1)
        self.assertIn("pnpm", out)

    def test_a_package_manager_without_a_version_is_refused(self):
        out = run("--root", ".", "--oss", "pragmatic", "--target", "vercel", "--package-manager",
                  "pnpm", "--show", expect=1)
        self.assertIn("pnpm@<version>", out)

    def test_the_matrix_prints_fifteen_lines(self):
        lines = [l for l in run("--matrix").splitlines() if l.strip()]
        self.assertEqual(len(lines), 15)
        self.assertEqual(sum(1 for l in lines if "caveat" in l), 2)


class WriteTest(unittest.TestCase):
    def test_no_placeholder_survives_and_the_file_parses(self):
        with tempfile.TemporaryDirectory() as d:
            text = written(d)
            self.assertNotIn("{{", text)
            data = parse_yaml(text)
            self.assertEqual(data["oss_level"], "pragmatic")
            self.assertEqual(data["target"], "vercel")
            self.assertEqual(data["ports"]["db"], "neon-http")
            self.assertEqual(data["declared"], TODAY)
            self.assertEqual(data["gates"]["coverage_lines"], "70")
            self.assertEqual(len(data["open_decisions"]), 7)
            self.assertEqual(data["open_decisions"][0]["until"], "2026-12-13")
            self.assertEqual(data["waivers"], [])
            self.assertEqual(data["enforcement"], ["gate"])
            self.assertEqual(len(data["rules"]), 6)
            self.assertEqual(len(data["workspaces"]), 5)

    def test_the_name_defaults_to_the_root_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "my-app"
            run("--root", str(root), "--oss", "minimal", "--target", "fly", "--today", TODAY)
            data = parse_yaml((root / "stack.yaml").read_text(encoding="utf-8"))
            self.assertEqual(data["name"], "my-app")
            self.assertEqual(data["ports"]["auth"], "clerk")
            self.assertEqual(data["oss_caveat"], "")

    def test_the_caveat_is_written_when_the_pair_carries_one(self):
        with tempfile.TemporaryDirectory() as d:
            run("--root", d, "--oss", "full", "--target", "cloudflare", "--today", TODAY)
            data = parse_yaml((Path(d) / "stack.yaml").read_text(encoding="utf-8"))
            self.assertEqual(data["oss_caveat"], declare.CAVEAT)
            self.assertEqual(data["ports"]["storage"], "s3")

    def test_the_three_profiles_write_their_ten_bars(self):
        for profile, bars in declare.PROFILES.items():
            with tempfile.TemporaryDirectory() as d:
                data = parse_yaml(written(d, "--profile", profile))
                self.assertEqual([int(data["gates"][b]) for b in declare.BARS], list(bars), profile)

    def test_show_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = run("--root", d, "--oss", "pragmatic", "--target", "railway", "--show")
            self.assertIn("pool", out)
            self.assertFalse((Path(d) / "stack.yaml").exists())

    def test_show_json_carries_the_ports_and_the_bars(self):
        out = run("--root", ".", "--oss", "full", "--target", "hetzner", "--show", "--json")
        data = json.loads(out)
        self.assertEqual(data["ports"]["jobs"], "systemd-timer")
        self.assertEqual(data["bars"]["gate_max_seconds"], 90)

    def test_an_existing_file_is_refused_without_force(self):
        with tempfile.TemporaryDirectory() as d:
            written(d)
            out = run("--root", d, "--oss", "full", "--target", "fly", "--today", TODAY, expect=1)
            self.assertIn("exists", out)
            self.assertIn("pragmatic", (Path(d) / "stack.yaml").read_text(encoding="utf-8"))
            run("--root", d, "--oss", "full", "--target", "fly", "--today", TODAY, "--force")
            self.assertIn("oss_level: full", (Path(d) / "stack.yaml").read_text(encoding="utf-8"))

    def test_a_decide_by_date_that_is_not_a_date_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--oss", "full", "--target",
                                "fly", "--decide-by", "soon"], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse((Path(d) / "stack.yaml").exists())

    def test_the_template_names_every_placeholder_the_script_substitutes_and_no_other(self):
        text = declare.TEMPLATE.read_text(encoding="utf-8")
        found = set(re.findall(r"\{\{([A-Z_]+)\}\}", text))
        expected = {"NAME", "DECLARED", "OSS_LEVEL", "TARGET", "OSS_CAVEAT", "NODE",
                    "PACKAGE_MANAGER", "GENERATOR", "DECIDE_BY"}
        expected |= {p.upper() for p in declare.PORTS} | {b.upper() for b in declare.BARS}
        self.assertEqual(found, expected)


class ContractTest(unittest.TestCase):
    def test_help_prints_the_docstring(self):
        self.assertIn("Write the declaration of a repository", run("--help"))

    def test_the_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn("\033[", run("--root", d, "--oss", "full", "--target", "fly"))

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--oss", "full", "--target",
                                "fly"], capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
