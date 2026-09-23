#!/usr/bin/env python3
"""Do the guards of a generated repository still stand, and did anybody walk around one.

Usage:
  guards.py [--root DIR] [--today YYYY-MM-DD] [--accept SPEC ...] [--snapshot FILE]
            [--protection-file FILE] [--previous FILE] [--fixes FILE] [--json]
  guards.py [--root DIR] --explain RANK|ID    the chain behind one finding
  guards.py --measures                        the unit every check id is measured in

Seventeen checks in three namespaces. `escape.*` is every way past a lock: a guard nothing
enforces on the server, a contract file nobody owns, a suppression in the code that no waiver in
`stack.yaml` names, a waiver past its date. `guard.*` is the locks themselves: a declared guard
with no command, one no workflow runs, one its own configuration switches off, a bar that stands
in no configuration, a rule class with no rule or no test, and the bars of coverage, assertions
and gate time. `dead.*` is what nobody uses, against the three bars.

This pass runs nothing. It reads the tree, the declaration, and what the gate left under
`.stack/` and `coverage/`. An artefact the gate never wrote leaves its measure `null`, never
zero, because a zero there would settle a log row with a figure nobody took (decisions/0030).

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import os
import argparse
import datetime as dt
import fnmatch
import json
import re
import sys
import textwrap
from pathlib import Path

# Colour is a hint on a report that reads the same without it (decisions/0022). It is off unless
# the output is a terminal, so a pipe, a redirect and a captured test all read plain text.
# NO_COLOR turns it off everywhere, FORCE_COLOR turns it on, which is how a test proves both.
PAINT = {"FAIL": "1;31", "WARN": "33", "PASS": "32", "INFO": "36", "head": "1", "id": "1",
         "dim": "2"}


def colour_on(stream=sys.stdout):
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return stream.isatty() and os.environ.get("TERM", "") != "dumb"


COLOUR = colour_on()


def paint(text, key):
    """`text` in the colour its role carries. Every escape removed leaves the same report."""
    return f"\033[{PAINT[key]}m{text}\033[0m" if COLOUR and key in PAINT else text


LEVEL_ORDER = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
# The unit of every check id this script measures. A measure counts what the finding costs, so
# lower is better and zero means the check no longer fires (decisions/0014). `--measures` prints
# this table and scripts/check.sh compares it to the unit named in the theme's fixes.md.
MEASURES = {"escape.unenforced": "count", "escape.unowned": "count", "escape.expired": "count",
            "escape.type": "count", "escape.lint": "count", "escape.test": "count",
            "guard.missing": "count", "guard.disabled": "count", "guard.unwired": "count",
            "guard.unbarred": "count", "guard.rulegap": "count", "guard.coverage": "percent",
            "guard.assertionless": "count", "guard.slow": "seconds",
            "dead.export": "count", "dead.file": "count", "dead.dep": "count"}
# What the number in a row counts, per check id.
ROW_WORD = {"escape.unenforced": ("guard", "guards"), "escape.unowned": ("file", "files"),
            "escape.expired": ("waiver", "waivers"), "escape.type": ("suppression", "suppressions"),
            "escape.lint": ("suppression", "suppressions"), "escape.test": ("test", "tests"),
            "guard.missing": ("guard", "guards"), "guard.disabled": ("switch", "switches"),
            "guard.unwired": ("guard", "guards"), "guard.unbarred": ("bar", "bars"),
            "guard.rulegap": ("rule", "rules"), "guard.coverage": ("point", "points"),
            "guard.assertionless": ("test", "tests"), "guard.slow": ("second", "seconds"),
            "dead.export": ("export", "exports"), "dead.file": ("file", "files"),
            "dead.dep": ("dependency", "dependencies")}
# A finding that is a way past a lock, or a lock that is gone, fails. A bar that is not reached
# warns: the guard exists and runs, and the number under it is what the row then measures.
FAIL_IDS = {"escape.unenforced", "escape.unowned", "escape.expired", "escape.type",
            "escape.lint", "escape.test", "guard.missing", "guard.unwired", "guard.rulegap"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "coverage", ".stack", ".turbo", ".tsout",
             "out", ".vercel", ".wrangler"}
SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
TEST_MARK = re.compile(r"\.(?:test|spec)\.|(?:^|/)(?:e2e|__tests__)/")
# The three kinds of suppression, and the waiver kind that excuses each. Another spelling of the
# same escape is not counted; adding one is a change here and in the generated scanner.
ESCAPES = {"type": re.compile(r"@ts-ignore|@ts-expect-error|\bas any\b"),
           "lint": re.compile(r"eslint-disable"),
           "test": re.compile(r"\b(?:it|test|describe)\.(?:skip|only)\s*\(")}
WAIVER_SCANNER = "scripts/waivers.mjs"     # holds the patterns as code, never as a suppression
PLACEHOLDER_OWNER = "@OWNER"
# The contract files (references/contracts.md). A directory entry counts once when it exists.
CONTRACT_FILES = ("stack.yaml", "CODEOWNERS", "rules/", "scripts/gate.sh", "scripts/waivers.mjs",
                  "scripts/dead.mjs", "scripts/drift.mjs", "scripts/stack-yaml.mjs", "lefthook.yml",
                  ".github/workflows/", "tsconfig.base.json", "eslint.config.mjs",
                  "vitest.config.ts", "knip.json", ".gitleaks.toml")
CODEOWNERS_PLACES = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
# Every bar of the declaration and the one file that carries its number (references/declaration.md).
BAR_FILE = {"coverage_lines": "vitest.config.ts", "coverage_branches": "vitest.config.ts",
            "max_function_lines": "eslint.config.mjs", "max_file_lines": "eslint.config.mjs",
            "max_complexity": "eslint.config.mjs", "max_params": "eslint.config.mjs",
            "dead_exports_max": "scripts/dead.mjs", "dead_files_max": "scripts/dead.mjs",
            "dead_deps_max": "scripts/dead.mjs", "gate_max_seconds": "scripts/gate.sh"}
# The closed list of switches a configuration can flip against its own guard (references/contracts.md).
SWITCHES = [
    ("tsconfig.base.json", re.compile(r'"strict"\s*:\s*false'), "strict set to false"),
    ("eslint.config.mjs",
     re.compile(r"""(complexity|max-lines-per-function|max-lines|max-params)['"]?\s*:\s*(['"]off['"]|0)\b"""),
     "a complexity bar set to off"),
    ("vitest.config.ts", re.compile(r"requireAssertions\s*:\s*false"), "requireAssertions set to false"),
    ("lefthook.yml", re.compile(r"skip:\s*true"), "a hook skipped"),
]
COVERAGE_OFF = re.compile(r"coverage\s*:\s*\{[^}]*enabled\s*:\s*false", re.S)
KNIP_BROAD = ("packages/**", "packages/", "apps/**", "apps/")
GATE_COMMANDS = ("pnpm check", "scripts/gate.sh")
PATH_TOKEN = re.compile(r"^(?:scripts|rules|\.github)/\S+$")
TEST_OPEN = re.compile(r"\b(?:it|test)\s*\(")
ASSERT = re.compile(r"\bexpect\s*\(|\bassert\b")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ENFORCED = re.compile(r"^(?P<name>[A-Za-z0-9_-]+)(?:@(?P<date>\d{4}-\d{2}-\d{2}))?$")
GATE_TIME = re.compile(r"^\S+\s+(\d+(?:\.\d+)?)\s+full\s*$")
DEAD_KEYS = {"dead.export": ("exports", "dead_exports_max"), "dead.file": ("files", "dead_files_max"),
             "dead.dep": ("dependencies", "dead_deps_max")}
GATE_TIMES = ".stack/gate-times.log"
DEAD_FILE = ".stack/dead.json"
COVERAGE_FILE = "coverage/coverage-summary.json"
# The checks that read a bar or a list from the declaration. Without it they measure nothing.
NEEDS_DECLARATION = ("escape.unenforced", "escape.expired", "guard.missing", "guard.unwired",
                     "guard.unbarred", "guard.rulegap", "guard.coverage", "guard.slow",
                     "dead.export", "dead.file", "dead.dep")


class Unsupported(Exception):
    """The reader met a construction it does not parse. The file counts as unread, not as clean."""


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None, unknown=False):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one file grades against it.
        `unknown` carries the unit with no value: the pass could not take the measure."""
        unit = MEASURES.get(cid)
        block = None
        if unit and (measure is not None or unknown):
            block = {"value": measure, "unit": unit, "by": by or {}}
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": block})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# The subset of the declaration's format these checks need, copied from the pipeline pass of
# jorekai-security on purpose: each skill stays standalone. Anything else raises Unsupported.
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
    """Lines that carry content, as (indent, body, raw). Everything a reader cannot follow raises."""
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


def read_declaration(root):
    """The declaration as a dict, and one word saying how it was read."""
    p = root / "stack.yaml"
    if not p.is_file():
        return None, "missing"
    try:
        data = parse_yaml(read(p))
    except Unsupported as e:
        return None, f"unread: {e}"
    return (data if isinstance(data, dict) else {}), "read"


def rel(path, root):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def contained(path, root):
    """Whether the real target of `path` stands inside the real root.

    A symlink that resolves outside the tree fails this, so a walk never reads a file outside the
    repository as though it stood inside it.
    """
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def walked_rel(path, root):
    """The path exactly where the walk found it, relative to the root.

    A symlink is named at the place it stands, never at the place it points to: a waiver in
    stack.yaml names that place, and CODEOWNERS matches it, so reporting the resolved target
    instead would make both miss.
    """
    try:
        return Path(path).relative_to(Path(root)).as_posix()
    except ValueError:
        return Path(path).as_posix()


def source_files(root):
    """Every source file of the tree, as a path relative to the root with forward slashes.

    A walked entry whose real target lies outside the root is skipped: a symlink there would
    otherwise be read and reported as if it stood inside the tree.
    """
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for n in sorted(names):
            if Path(n).suffix in SOURCE_EXT:
                p = Path(base) / n
                if contained(p, root):
                    out.append(walked_rel(p, root))
    return out


def is_test(path):
    return bool(TEST_MARK.search(path))


def as_list(value):
    if isinstance(value, list):
        return [v for v in value if v is not None]
    if value is None or value == "":
        return []
    return [value]


def as_map(value):
    return value if isinstance(value, dict) else {}


def waivers_of(decl, today):
    """Valid waivers keyed by (kind, file, line), and the valid ones past their date.

    An entry missing reason, until or owner is not a waiver at all: it excuses nothing and it is
    not expired either, because it never counted (decisions/0036).
    """
    valid, expired = {}, []
    for entry in as_list(as_map(decl).get("waivers")):
        if not isinstance(entry, dict):
            continue
        kind, file, line = str(entry.get("kind") or ""), str(entry.get("file") or ""), str(entry.get("line") or "")
        reason, until, owner = entry.get("reason"), str(entry.get("until") or ""), entry.get("owner")
        if not (kind and file and line.isdigit() and reason and owner and ISO_DATE.match(until)):
            continue
        key = (kind, file, int(line))
        valid[key] = until
        if dt.date.fromisoformat(until) < today:
            expired.append(key)
    return valid, expired


def escapes(root, files):
    """Every suppression in the tree, as (kind, file, line, what it spelled)."""
    hits = []
    for f in files:
        if f == WAIVER_SCANNER:
            continue
        for n, line in enumerate(read(root / f).splitlines(), 1):
            for kind, rx in ESCAPES.items():
                m = rx.search(line)
                if m:
                    hits.append((kind, f, n, m.group(0).strip()))
    return hits


def enforcement_entries(decl):
    """Guard names under `enforcement`, each with the date a person confirmed it, or ''."""
    out = []
    for entry in as_list(as_map(decl).get("enforcement")):
        m = ENFORCED.match(str(entry).strip())
        if m:
            out.append((m.group("name"), m.group("date") or ""))
    return out or [("gate", "")]


def read_protection(path):
    """The branch protection a capture proves, or None when no file was captured at all.

    A guard is enforced only when the server itself says so (a source: references/sources.md of
    jorekai-stack:stack). Without `--protection-file` this reads None, and `escape.unenforced`
    then reports unknown rather than trusting a date nobody checked against the forge.
    """
    if not path:
        return None
    try:
        data = json.loads(read(path) or "{}")
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    checks = as_map(data.get("required_status_checks"))
    contexts = checks.get("contexts") or [c.get("context") for c in as_list(checks.get("checks"))
                                          if isinstance(c, dict)]
    admins = data.get("enforce_admins")
    if isinstance(admins, dict):
        admins = admins.get("enabled")
    reviews = as_map(data.get("required_pull_request_reviews"))
    return {"contexts": [str(c) for c in contexts or [] if c], "enforce_admins": bool(admins),
            "require_code_owner_reviews": bool(reviews.get("require_code_owner_reviews"))}


def codeowners(root):
    """The owner lines of CODEOWNERS, as (pattern, owners), or None when no file exists."""
    for place in CODEOWNERS_PLACES:
        p = root / place
        if p.is_file():
            rules = []
            for line in read(p).splitlines():
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split()
                rules.append((parts[0].lstrip("/"), [o for o in parts[1:] if o != PLACEHOLDER_OWNER]))
            return rules
    return None


def covered(path, rules):
    """Whether the last matching CODEOWNERS line names a real owner for this path."""
    owners = None
    for pattern, names in rules:
        if pattern == path or pattern.rstrip("/") == path.rstrip("/") \
                or (pattern.endswith("/") and path.startswith(pattern)) \
                or path.startswith(pattern.rstrip("/") + "/") \
                or fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.rstrip("/"), pattern):
            owners = [o for o in names if o != PLACEHOLDER_OWNER]
    return bool(owners)


def contract_paths(root):
    """The contract files that exist in this tree, directories with their trailing slash."""
    return [c for c in CONTRACT_FILES
            if ((root / c).is_dir() if c.endswith("/") else (root / c).is_file())]


def guards_of(decl):
    """Guard name to command, in the declaration's order."""
    return {str(k): ("" if v is None else str(v)) for k, v in as_map(as_map(decl).get("guards")).items()}


def missing_paths(command, root):
    """The path-like tokens of a command that name no file."""
    return [t for t in command.split() if PATH_TOKEN.match(t) and not (root / t).exists()]


def workflow_runs(root):
    """Every `run` text of every workflow step, and the workflows the reader could not follow."""
    runs, unread = [], []
    folder = root / ".github" / "workflows"
    for p in sorted(folder.iterdir()) if folder.is_dir() else []:
        if p.suffix not in (".yml", ".yaml") or not p.is_file():
            continue
        try:
            data = parse_yaml(read(p))
        except Unsupported as e:
            unread.append(f"{rel(p, root)}: {e}")
            continue
        for job in as_map(as_map(data).get("jobs")).values():
            for step in as_list(as_map(job).get("steps")):
                if isinstance(step, dict) and step.get("run"):
                    runs.append(str(step["run"]))
    return runs, unread


def wired(command, runs, gate_text):
    """A guard is wired when a workflow runs its command, or runs the gate and the gate exists.

    The gate reads the guards from the declaration, so it runs every declared command by
    construction; a step switched off inside it is `guard.disabled`, not this check."""
    if any(command in r for r in runs):
        return True
    return bool(gate_text) and any(g in r for g in GATE_COMMANDS for r in runs)


def switches(root, commands):
    """Every switch of the closed list that is flipped in this tree, as (file, what)."""
    found = []
    for file, rx, what in SWITCHES:
        if rx.search(read(root / file)):
            found.append((file, what))
    if COVERAGE_OFF.search(read(root / "vitest.config.ts")):
        found.append(("vitest.config.ts", "coverage disabled"))
    if (root / "lefthook.yml").is_file() and "pre-commit" not in read(root / "lefthook.yml"):
        found.append(("lefthook.yml", "no pre-commit block"))
    try:
        knip = json.loads(read(root / "knip.json") or "{}")
    except ValueError:
        knip = {}
    for entry in as_list(knip.get("ignore") if isinstance(knip, dict) else None):
        if any(str(entry).startswith(b) for b in KNIP_BROAD):
            found.append(("knip.json", f"ignore {entry}"))
    for line in read(root / "scripts" / "gate.sh").splitlines():
        s = line.strip()
        if s.startswith("#") and any(c and c in s for c in commands):
            found.append(("scripts/gate.sh", "a step commented out"))
            break
    return found


def rule_gaps(root, decl):
    """Rule ids under `rules` whose rule file or test file is missing."""
    out = []
    for rid in as_list(as_map(decl).get("rules")):
        rid = str(rid)
        parts = [w for w, p in (("rule", f"rules/{rid}.rule.mjs"), ("test", f"rules/{rid}.test.mjs"))
                 if not (root / p).is_file()]
        if parts:
            out.append((rid, "no " + " and no ".join(parts)))
    return out


def coverage_gap(root, gates):
    """The points each coverage bar is missing, or None when the runner never wrote the report."""
    try:
        data = json.loads(read(root / COVERAGE_FILE) or "")
    except ValueError:
        return None
    total = as_map(as_map(data).get("total"))
    gaps = {}
    for bar, key in (("coverage_lines", "lines"), ("coverage_branches", "branches")):
        want = number(gates.get(bar))
        have = number(as_map(total.get(key)).get("pct"))
        if want is not None and have is not None:
            gaps[bar] = round(max(0.0, want - have), 1)
    return gaps


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def assertionless(root, files):
    """Test blocks whose callback carries no assertion, as file:line."""
    out = []
    for f in files:
        # A rule's test holds a fixture that must look like a test without an assertion.
        if not is_test(f) or f.startswith("rules/"):
            continue
        text = read(root / f)
        for m in TEST_OPEN.finditer(text):
            body = callback_body(text, m.end())
            if body is not None and not ASSERT.search(body):
                out.append(f"{f}:{text.count(chr(10), 0, m.start()) + 1}")
    return out


def callback_body(text, start):
    """The body of the callback after `start`: the brace block behind its `=>` or `function`,
    so a destructured parameter like `({ page })` is not mistaken for the body. None without one."""
    arrow = re.search(r"=>|\bfunction\b", text[start:start + 400])
    if not arrow:
        return None
    open_at = text.find("{", start + arrow.end())
    if open_at < 0:
        return None
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1:i]
    return None


def last_gate_seconds(root):
    """The seconds of the last full gate run, or None when the gate never wrote its timing."""
    seconds = None
    for line in read(root / GATE_TIMES).splitlines():
        m = GATE_TIME.match(line.strip())
        if m:
            seconds = float(m.group(1))
    return seconds


def dead_counts(root):
    try:
        data = json.loads(read(root / DEAD_FILE) or "")
    except ValueError:
        return None
    return as_map(data)


def pairs(specs, fields=2):
    """The first `fields` words of every spec. The reason and the date are for a person to read."""
    out = set()
    for spec in specs or []:
        parts = spec.split()
        if len(parts) >= fields:
            out.add(tuple(parts[:fields]))
    return out


def owned(accepted):
    """The accepted entries this pass owns; a check id belongs to exactly one tool."""
    return {p for p in accepted if p[0] in MEASURES}


def report_rows(rep, cid, rows, by, bad, good, one=None, unit_value=None):
    """One finding per check, or the passing line with a zero that settles a row."""
    level = "FAIL" if cid in FAIL_IDS else "WARN"
    if rows:
        total = unit_value if unit_value is not None else sum(by.values())
        word = ROW_WORD.get(cid, ("finding", "findings"))
        rep.add(level, cid, f"{plural(total, *word)} " + (one if total == 1 and one else bad),
                data=rows, measure=total, by=by)
    else:
        rep.add("PASS", cid, good, measure=0)


def unknown(rep, cid, why):
    rep.add("INFO", cid, why, unknown=True)


def collect_escapes(root, decl, files, today, rep, skip, protection):
    valid, expired = waivers_of(decl, today) if decl is not None else ({}, [])
    hits = escapes(root, files)
    for kind in ESCAPES:
        cid = "escape." + kind
        rows, by = [], {}
        for k, f, n, what in hits:
            target = f"{f}:{n}"
            if k != kind or (kind, f, n) in valid or (cid, target) in skip:
                continue
            rows.append({"target": target, "value": what})
            by[target] = 1
        word = {"type": "type suppressions", "lint": "lint suppressions",
                "test": "skipped or exclusive tests"}[kind]
        report_rows(rep, cid, rows, by, f"stand in the code and no waiver in stack.yaml names them",
                    f"no {word} without a waiver", one="stands in the code and no waiver in stack.yaml names it")
    if decl is None:
        unknown(rep, "escape.expired", "the declaration could not be read, so no waiver could be dated")
    else:
        rows = [{"target": f"{f}:{n}", "value": f"{k}, until {valid[(k, f, n)]}"} for k, f, n in expired
                if ("escape.expired", f"{f}:{n}") not in skip]
        report_rows(rep, "escape.expired", rows, {r["target"]: 1 for r in rows},
                    "are past their date, so the suppressions they covered are red again",
                    "no waiver is past its date", one="is past its date, so the suppression it covered is red again")
    if decl is None:
        unknown(rep, "escape.unenforced", "the declaration could not be read, so nothing says which guard the server enforces")
    elif protection is None:
        unknown(rep, "escape.unenforced", "no branch protection was captured (--protection-file), so a "
                "date in stack.yaml is not proof the server enforces anything")
    else:
        rows = []
        for name, date in enforcement_entries(decl):
            enforced = bool(date) and name in protection["contexts"]
            if not enforced and ("escape.unenforced", name) not in skip:
                rows.append({"target": name, "value": "no confirmed date" if not date else "not a required check"})
        if not protection["enforce_admins"] and ("escape.unenforced", "enforce_admins") not in skip:
            rows.append({"target": "enforce_admins", "value": "an administrator can merge past every required check"})
        if not protection["require_code_owner_reviews"] and \
                ("escape.unenforced", "require_code_owner_reviews") not in skip:
            rows.append({"target": "require_code_owner_reviews", "value": "CODEOWNERS is not enforced by the server"})
        report_rows(rep, "escape.unenforced", rows, {r["target"]: 1 for r in rows},
                    "are required by no branch protection, so a local flag walks past them",
                    "every declared guard is a required check with a confirmed date, admin bypass is off, "
                    "and code owner review is required",
                    one="is required by no branch protection, so a local flag walks past it")
    rules = codeowners(root)
    rows = [{"target": c, "value": "no owner line" if rules is None else "no owner"}
            for c in contract_paths(root)
            if (rules is None or not covered(c, rules)) and ("escape.unowned", c) not in skip]
    report_rows(rep, "escape.unowned", rows, {r["target"]: 1 for r in rows},
                "have no owner, so a change to a bar is a commit and not a review",
                "every contract file has an owner", one="has no owner, so a change to a bar is a commit and not a review")


def collect_guards(root, decl, files, rep, skip):
    if decl is None:
        for cid in ("guard.missing", "guard.unwired", "guard.unbarred", "guard.rulegap"):
            unknown(rep, cid, "the declaration could not be read, so nothing says what a guard here should be")
        commands = []
    else:
        guards = guards_of(decl)
        commands = [c for c in guards.values() if c]
        rows = []
        for name, command in guards.items():
            gone = missing_paths(command, root)
            if (not command or gone) and ("guard.missing", name) not in skip:
                rows.append({"target": name, "value": "no command" if not command else "missing " + ", ".join(gone)})
        report_rows(rep, "guard.missing", rows, {r["target"]: 1 for r in rows},
                    "are declared and have no command that runs", "every declared guard has a command",
                    one="is declared and has no command that runs")
        runs, unread = workflow_runs(root)
        gate_text = read(root / "scripts" / "gate.sh")
        rows = [{"target": name, "value": "no workflow runs it"} for name, command in guards.items()
                if command and not wired(command, runs, gate_text) and ("guard.unwired", name) not in skip]
        report_rows(rep, "guard.unwired", rows, {r["target"]: 1 for r in rows},
                    "run in no workflow, so the server never sees their result",
                    "every declared guard runs in a workflow", one="runs in no workflow, so the server never sees its result")
        if unread:
            rep.add("INFO", "guard.unwired", f"{plural(len(unread), 'workflow')} could not be read and "
                    "may run a guard this pass did not see", data=[{"target": u, "value": "unread"} for u in unread])
        gates = as_map(decl.get("gates"))
        rows = [{"target": bar, "value": f"not in {file}"} for bar, file in BAR_FILE.items()
                if bar in gates and bar not in read(root / file) and ("guard.unbarred", bar) not in skip]
        report_rows(rep, "guard.unbarred", rows, {r["target"]: 1 for r in rows},
                    "stand in no configuration, so no tool enforces their number",
                    "every bar stands in its configuration", one="stands in no configuration, so no tool enforces its number")
        rows = [{"target": rid, "value": why} for rid, why in rule_gaps(root, decl)
                if ("guard.rulegap", rid) not in skip]
        report_rows(rep, "guard.rulegap", rows, {r["target"]: 1 for r in rows},
                    "are declared and have no rule file or no test that proves the rule fires",
                    "every declared rule class has a rule and a test",
                    one="is declared and has no rule file or no test that proves the rule fires")
    rows = [{"target": f, "value": what} for f, what in switches(root, commands)
            if ("guard.disabled", f) not in skip]
    report_rows(rep, "guard.disabled", rows, {r["target"]: 1 for r in rows},
                "in their own configuration switch off what the declaration promised",
                "no configuration switches off its own guard",
                one="in its own configuration switches off what the declaration promised")
    rows = [{"target": t, "value": "no assertion"} for t in assertionless(root, files)
            if ("guard.assertionless", t) not in skip]
    report_rows(rep, "guard.assertionless", rows, {r["target"]: 1 for r in rows},
                "assert nothing, so they pass whatever the code does", "every test block asserts something",
                one="asserts nothing, so it passes whatever the code does")


def collect_bars(root, decl, rep, skip):
    """The measured bars: coverage, gate time, dead code. Each reads an artefact the gate wrote."""
    if decl is None:
        for cid in ("guard.coverage", "guard.slow", "dead.export", "dead.file", "dead.dep"):
            unknown(rep, cid, "the declaration could not be read, so there is no bar to measure against")
        return
    gates = as_map(decl.get("gates"))
    gaps = coverage_gap(root, gates)
    if gaps is None:
        unknown(rep, "guard.coverage", f"{COVERAGE_FILE} was never written, so the last unit run is unknown")
    else:
        rows = [{"target": bar, "value": f"{gap:g} points below"} for bar, gap in gaps.items()
                if gap > 0 and ("guard.coverage", bar) not in skip]
        report_rows(rep, "guard.coverage", rows, {r["target"]: gaps[r["target"]] for r in rows},
                    "below the coverage bar in the last unit run", "the last unit run reached both coverage bars",
                    one="below the coverage bar in the last unit run",
                    unit_value=max((gaps[r["target"]] for r in rows), default=None))
    seconds = last_gate_seconds(root)
    bar = number(gates.get("gate_max_seconds"))
    if seconds is None or bar is None:
        unknown(rep, "guard.slow", f"{GATE_TIMES} holds no full run, so the gate's time is unknown")
    else:
        over = round(max(0.0, seconds - bar), 1)
        rows = [{"target": "scripts/gate.sh", "value": f"{seconds:g}s against {bar:g}s"}] if over > 0 else []
        report_rows(rep, "guard.slow", rows, {"scripts/gate.sh": over} if rows else {},
                    "over the time bar in the last full gate", "the last full gate ran inside the time bar",
                    one="over the time bar in the last full gate", unit_value=over if rows else None)
    dead = dead_counts(root)
    for cid, (key, bar_key) in DEAD_KEYS.items():
        if dead is None:
            unknown(rep, cid, f"{DEAD_FILE} was never written, so the dead-code count is unknown")
            continue
        have, want = number(dead.get(key)), number(gates.get(bar_key))
        if have is None or want is None:
            unknown(rep, cid, f"{DEAD_FILE} carries no {key} count, so this bar is unknown")
            continue
        over = int(max(0, have - want))
        rows = [{"target": key, "value": f"{have:g} against a bar of {want:g}"}] if over else []
        word = ROW_WORD[cid][1]
        report_rows(rep, cid, rows, {key: over} if rows else {},
                    f"over the bar are imported or reached by nobody", f"unused {word} stay inside the bar",
                    one="over the bar is imported or reached by nobody", unit_value=over if rows else None)


def snapshot_note(root, path, decl, rep):
    """The top-level keys where the workspace snapshot and the repository's declaration differ."""
    if not path or decl is None:
        return
    try:
        snap = parse_yaml(read(path))
    except Unsupported:
        snap = None
    if not isinstance(snap, dict):
        rep.add("INFO", "escape.unenforced", f"the snapshot {path} could not be read, so nothing compares it to stack.yaml")
        return
    differ = sorted(k for k in set(snap) | set(decl) if snap.get(k) != decl.get(k))
    if differ:
        rep.add("INFO", "escape.unenforced", "the declaration differs from the snapshot in the workspace: "
                + ", ".join(differ) + ". Copy it there when the change is meant, or revert it here")


def collect(root, decl, how, files, today, a, rep):
    skip = owned(pairs(a.accept))
    collect_escapes(root, decl, files, today, rep, skip, read_protection(a.protection_file))
    collect_guards(root, decl, files, rep, skip)
    collect_bars(root, decl, rep, skip)
    if decl is None:
        rep.add("INFO", "escape.unenforced", f"stack.yaml is {how}: run jorekai-stack:choose, or fix "
                "what the reader names, before any of these numbers means anything")
    snapshot_note(root, a.snapshot, decl, rep)
    if skip:
        rep.add("INFO", "escape.type", f"{plural(len(skip), 'finding')} {verb(len(skip), 'are', 'is')} "
                "recorded as accepted and left out of the counts",
                data=[{"target": t, "value": c} for c, t in sorted(skip)])
    return rep


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one guard is, two guards are."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 guard(s)"."""
    shown = f"{n:g}" if isinstance(n, float) else str(n)
    return f"{shown} {one if n == 1 else (many or one + 's')}"


def cost(item):
    """The cost of a finding as one number and one unit, the column the eye lands on."""
    m = item.get("measure") or {}
    value = m.get("value")
    if value is None:
        return ""
    return plural(value, *ROW_WORD.get(item["id"], ("finding", "findings")))


def block(rows, indent="      "):
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


def detail(item):
    return [(str(d.get("target", "")), str(d.get("value", "")) or "yes") for d in item["data"][:5]]


# The gate of this theme (references/risk-classes.md): a contract file changes through review. It
# stands over every id whose fix is a contract file, before the class applies.
GATE_REVIEW = ("escape.", "decl.absent", "decl.unmatched", "decl.undecided", "guard.disabled",
               "guard.unbarred", "guard.rulegap", "boundary.crossed", "adapter.untargeted")


def gate_of(cid):
    """The gate a fix for this id passes before its class applies, or an empty string."""
    return "review" if cid.startswith(GATE_REVIEW) else ""


# The report answers the questions a person asks, in the order they ask them (decisions/0031):
# what it is and how heavy it weighs stand in the list, the rest waits behind `--explain`.
FIXES_FILE = Path(__file__).resolve().parents[2] / "stack" / "references" / "fixes.md"
FIX_ROW = re.compile(r"\|\s*`([a-z]+\.[a-z-]+)`\s*\|([^|]*)\|([^|]*)\|\s*`([a-z]+)`\s*\|\s*(\d+)\s*\|")


def load_fixes(path=None):
    """Check id to what it means, its fix, its risk class, and the rung of the ladder it sits on."""
    try:
        text = Path(path or FIXES_FILE).read_text(encoding="utf-8")
    except OSError:
        return {}
    rows = {}
    for line in text.splitlines():
        m = FIX_ROW.match(line)
        if m:
            rows[m.group(1)] = {"means": m.group(2).strip(), "fix": m.group(3).strip(),
                                "class": m.group(4), "rung": int(m.group(5))}
    return rows


def previous_measures(path):
    """Every measure of an earlier findings JSON, so a line can carry a direction."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {i["id"]: (i.get("measure") or {}).get("value") for i in data.get("items", [])}


def change_of(item, previous):
    """The direction since that pass: `=`, a signed number, or `new` for an id it never held."""
    now = (item.get("measure") or {}).get("value")
    if now is None:
        return "-"
    old = previous.get(item["id"])
    if old is None:
        return "new"
    return "=" if old == now else f"{now - old:+g}"


def where_of(item, width=20):
    """The first place the finding names, and how many more places the JSON holds."""
    rows = detail(item)
    if not rows:
        return "-"
    more = len(item["data"]) - 1
    text = str(rows[0][0]) + (f" +{more}" if more > 0 else "")
    return text if len(text) <= width else text[:width - 2] + ".."


def ranked_findings(rep, fixes=None):
    """Findings and notes in ladder order: the rank is the address `--explain` takes."""
    fixes = fixes or {}
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              fixes.get(x["id"], {}).get("rung", 9),
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    return ([i for i in ranked if i["level"] in ("FAIL", "WARN")],
            [i for i in ranked if i["level"] == "INFO"],
            [i for i in ranked if i["level"] == "PASS"])


def columns(head, rows, paints, under=None):
    """Fixed columns, padded on the plain text, painted after, so colour never moves a column."""
    under = under or {}
    widths = [max([len(h)] + [len(r[c]) for r in rows]) for c, h in enumerate(head)]
    out = [paint("  ".join(h.ljust(w) for h, w in zip(head, widths)).rstrip(), "dim")]
    indent = " " * (widths[0] + 2 + widths[1] + 2)
    for n, (row, keys) in enumerate(zip(rows, paints)):
        line = "  ".join((paint(v, k) if k else v) + " " * (w - len(v))
                         for v, w, k in zip(row, widths, keys))
        out.append(line.rstrip())
        if under.get(n):
            out.append(paint(indent + under[n], "dim"))
    return out


def said(item, width=70):
    """The sentence a line with no cost carries, because a note's content is its sentence."""
    text = " ".join(item.get("message", "").split())
    return text if len(text) <= width else text[:width - 2] + ".."


def listing(findings, notes, fixes, previous):
    """One line per finding: rank, level, check, measure, change, where, class."""
    head = ["  #", "level", "check", "measure"] + (["change"] if previous is not None else []) \
        + ["where", "class"]
    rows, paints, notes_under = [], [], {}
    for n, i in enumerate(findings + notes, 1):
        level = "note" if i["level"] == "INFO" else i["level"]
        row = [f"{n:>3}", level, i["id"], cost(i) or "-"]
        keys = [None, i["level"], "id", "dim"]
        if previous is not None:
            direction = change_of(i, previous)
            row.append(direction)
            keys.append({"=": "dim", "-": "dim", "new": "WARN"}.get(direction)
                        or ("WARN" if direction.startswith("+") else "PASS"))
        row += [where_of(i), fixes.get(i["id"], {}).get("class", "-")]
        keys += ["dim", "INFO"]
        rows.append(row)
        paints.append(keys)
        notes_under[len(rows) - 1] = None if cost(i) else said(i)
    return columns(head, rows, paints, notes_under)


def field(label, lines, width=6, wrap=80):
    """One field of the chain: the label once, dimmed, its lines wrapped under it."""
    if not lines:
        return []
    pad = " " * (width + 2)
    flowed = []
    for line in lines:
        flowed += textwrap.wrap(line, width=wrap - len(pad), break_long_words=False,
                                break_on_hyphens=False) or [""]
    return [f"{paint(label.ljust(width), 'dim')}  {flowed[0]}"] + [pad + l for l in flowed[1:]]


def undo_line(cid, klass):
    """The way back, read from the gate and the class the id runs under (references/risk-classes.md)."""
    if gate_of(cid):
        return "the change is a branch under review, and the way back is closing the review"
    if klass == "confirm":
        return "the dry run names every path it writes, and the copy it writes first is the way back"
    if klass == "safe":
        return "the class is safe, so the change reports what it did and setting the old value again is the way back"
    if klass == "ask":
        return "the class is ask, so nothing runs from here: the change and the gate that judges it are one commit"
    return ""


def pick(ranked, which):
    """A finding by its rank in this pass or by its check id, whichever the argument holds."""
    if which.isdigit() and 1 <= int(which) <= len(ranked):
        return ranked[int(which) - 1]
    return next((i for i in ranked if i["id"] == which), None)


def explain_report(rep, target, fixes, which, previous):
    """The chain for one finding: what, weight, means, cause, fix, undo, verify."""
    findings, notes, _ = ranked_findings(rep, fixes)
    ranked = findings + notes
    item = pick(ranked, which)
    if item is None:
        return (f"no finding called {which} in this pass. The list prints a rank per finding, "
                "and --explain takes that rank or the check id.")
    n, row = ranked.index(item) + 1, fixes.get(item["id"], {})
    klass = row.get("class", "")
    out = [f"{paint(item['id'], 'head')}  {paint(f'rank {n} of {len(ranked)}', 'dim')}  "
           f"{paint('note' if item['level'] == 'INFO' else item['level'], item['level'])}  "
           f"{paint(target, 'dim')}", ""]
    out += field("what", [item["message"]])
    out += block(detail(item), indent=" " * 8)
    weight = [cost(item) or "nothing measurable", item["level"].lower()]
    if previous is not None:
        weight.append(f"change {change_of(item, previous)}")
    if gate_of(item["id"]):
        weight.append(gate_of(item["id"]))
    out += field("weight", [" · ".join(weight)])
    out += field("means", [row.get("means") or
                           "no row in the fixes table of jorekai-stack:stack, so nothing explains this id yet"])
    if item.get("cause"):
        out += field("cause", [item["cause"]])
    out += field("fix", [" · ".join(filter(None, [klass or "no class", gate_of(item["id"]),
                                                  row.get("fix") or "fixes table of jorekai-stack:stack"]))])
    out += field("undo", [undo_line(item["id"], klass)] if undo_line(item["id"], klass) else [])
    unit = MEASURES.get(item["id"], "count")
    out += field("verify", [f"{item['id']}  0 {unit}  recomputed by this pass",
                            "the verify date goes in the log row that carries the change"])
    return "\n".join(out)


def bar(fails, warns, notes, passed):
    """Four counts in one line, a zero dimmed, a count above zero in the colour of its word."""
    cells = [(fails, "FAIL", "FAIL"), (warns, "WARN", "WARN"),
             (notes, plural(notes, "note").split()[1], "INFO"),
             (passed, "passed", "PASS")]
    return " · ".join(paint(f"{n} {word}", key if n else "dim") for n, word, key in cells)


def wrapped(label, words, width=80):
    """A dimmed list that wraps at the terminal's width, the label once."""
    lines = textwrap.wrap(", ".join(words), width=width - len(label) - 2, break_on_hyphens=False)
    indent = " " * (len(label) + 2)
    return [paint(f"{label}  {lines[0]}", "dim")] + [paint(indent + l, "dim") for l in lines[1:]]


def text_report(count, rep, target, standards, fixes=None, previous=None):
    """The console report: what was measured, what needs a decision, what is only a note."""
    fixes = {} if fixes is None else fixes
    findings, notes, passed = ranked_findings(rep, fixes)
    fails = sum(1 for i in findings if i["level"] == "FAIL")
    out = [paint(f"guards  {target}  {plural(count, 'source file')}", "head"),
           f"measured against  {standards}", "",
           bar(fails, len(findings) - fails, len(notes), len(passed))]
    if findings or notes:
        out += [""] + listing(findings, notes, fixes, previous)
    if passed:
        out += [""] + wrapped("passed", [i["id"] for i in passed])
    if findings:
        out += ["", paint("next", "head") + "  close every way past the lock first, then look each id "
                "up in the fixes table of jorekai-stack:stack"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again after the next gate run"]
    if findings or notes:
        out.append(paint("      --explain RANK prints what one line means, where it comes from, "
                         "the fix and the way back", "dim"))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repository to read")
    ap.add_argument("--today", default=None, metavar="YYYY-MM-DD", help="for tests")
    ap.add_argument("--accept", action="append", metavar="SPEC",
                    help="`<check id> <target> <reason> <date>` from config.md, left out of the counts")
    ap.add_argument("--snapshot", default="", metavar="FILE",
                    help="the workspace's copy of stack.yaml; a difference is a note")
    ap.add_argument("--protection-file", default="", metavar="FILE",
                    help="a captured branch protection; without it escape.unenforced stays unknown")
    ap.add_argument("--explain", default="", metavar="RANK|ID",
                    help="the chain behind one finding: what, weight, means, fix, undo, verify")
    ap.add_argument("--previous", default="", metavar="FILE",
                    help="an earlier findings JSON, which adds the change column")
    ap.add_argument("--fixes", default="", metavar="FILE",
                    help="the fixes table to read the class and the meaning from")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    root = Path(a.root)
    decl, how = read_declaration(root)
    files = source_files(root)
    rep = collect(root, decl, how, files, today, a, Report())
    target = root.resolve().name
    if a.json:
        print(json.dumps({"tool": "guards", "target": target, "generated": today.isoformat(),
                          "counts": rep.counts(), "declaration": how, "files": len(files),
                          "items": rep.items}, indent=2, ensure_ascii=False))
    elif a.explain:
        print(explain_report(rep, target, load_fixes(a.fixes or None), a.explain,
                             previous_measures(a.previous) if a.previous else None))
    else:
        print(text_report(len(files), rep, target, f"stack.yaml {how} · today {today.isoformat()}",
                          load_fixes(a.fixes or None),
                          previous_measures(a.previous) if a.previous else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
