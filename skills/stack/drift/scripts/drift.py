#!/usr/bin/env python3
"""Whether the tree still matches its declaration: boundaries, adapters, the lock, generated files.

Usage:
  drift.py [--root DIR] [--today YYYY-MM-DD] [--accept SPEC ...] [--snapshot FILE]
           [--explain RANK|ID] [--previous FILE] [--fixes FILE] [--json]
  drift.py --measures              the unit every check id is measured in

Thirteen checks, read from `stack.yaml` and the tree alone: a declaration that is missing a section
or points at nothing, a generated file changed by hand, a package the declaration does not name, an
open decision past its date, a lock that does not resolve a workspace manifest, a pinning place
that contradicts the declared runtime, an import over a forbidden edge, two packages that import
each other, an import past an entry point, a vendor module outside its adapter, a port missing one
of its parts, and a port whose adapter is not the one the two axes resolve to.

Nothing is run and nothing is installed. An artefact that cannot be read carries no measure
rather than a zero (decisions/0030).

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
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
MEASURES = {"decl.absent": "count", "decl.unmatched": "count", "decl.generated": "count",
            "decl.undeclared": "count", "decl.undecided": "count",
            "lock.incomplete": "count", "lock.runtime": "count",
            "boundary.crossed": "count", "boundary.cycle": "count", "boundary.deep-import": "count",
            "adapter.bypassed": "count", "adapter.missing": "count", "adapter.untargeted": "count"}
# What the number in a row counts, per check id.
ROW_WORD = {"decl.absent": ("missing declaration", "missing declarations"),
            "decl.unmatched": ("entry", "entries"),
            "decl.generated": ("generated file", "generated files"),
            "decl.undeclared": ("package", "packages"),
            "decl.undecided": ("open decision", "open decisions"),
            "lock.incomplete": ("manifest", "manifests"),
            "lock.runtime": ("pinning place", "pinning places"),
            "boundary.crossed": ("import", "imports"),
            "boundary.cycle": ("pair", "pairs"),
            "boundary.deep-import": ("import", "imports"),
            "adapter.bypassed": ("import", "imports"),
            "adapter.missing": ("part", "parts"),
            "adapter.untargeted": ("port", "ports")}
# Which ids fail the pass above zero; the rest warn. The declaration wrong, an edge crossed, a
# cycle, a vendor outside its adapter and a port off its axes are the ones that cost more each day.
FAIL_IDS = {"decl.absent", "decl.unmatched", "boundary.crossed", "boundary.cycle",
            "adapter.bypassed", "adapter.untargeted"}
# The sections every pass reads. `open_decisions`, `port_exceptions` and `human_steps` are optional.
REQUIRED = ("name", "oss_level", "target", "runtime", "ports", "gates", "guards", "enforcement",
            "workspaces", "rules", "waivers")
PORTS = ("db", "storage", "jobs", "host", "auth", "mail", "analytics", "errors")
# The parts of a port under packages/ports/src/<port>/ (references/ports.md).
PARTS = ("contract.ts", "memory.adapter.ts", "wired.ts", "smoke.test.ts")
PORTS_DIR = "packages/ports/src"
# The adapter table (references/ports.md), duplicated in choose and new on purpose: each skill
# stays standalone, and a test in each compares it to the table.
BY_TARGET = {
    "db": {"vercel": "neon-http", "cloudflare": "hyperdrive", "fly": "pool", "hetzner": "pool",
           "railway": "pool"},
    "storage": {"vercel": "vercel-blob", "cloudflare": "r2", "fly": "tigris", "hetzner": "s3",
                "railway": "s3"},
    "jobs": {"vercel": "vercel-cron", "cloudflare": "worker-cron", "fly": "machine-schedule",
             "hetzner": "systemd-timer", "railway": "railway-cron"},
    "host": {"vercel": "vercel", "cloudflare": "workers", "fly": "fly", "hetzner": "docker",
             "railway": "railway"},
}
BY_LEVEL = {
    "auth": {"minimal": "clerk", "pragmatic": "better-auth", "full": "better-auth"},
    "mail": {"minimal": "resend", "pragmatic": "resend", "full": "smtp"},
    "analytics": {"minimal": "posthog", "pragmatic": "posthog", "full": "posthog"},
    "errors": {"minimal": "sentry", "pragmatic": "sentry", "full": "sentry"},
}
# The modules an adapter may import and nothing else may (references/ports.md).
VENDORS = {"@neondatabase/serverless": "db/neon-http", "pg": "db/pool, db/hyperdrive",
           "@vercel/blob": "storage/vercel-blob",
           "@aws-sdk/client-s3": "storage/r2, storage/tigris, storage/s3",
           "@clerk/backend": "auth/clerk", "better-auth": "auth/better-auth",
           "nodemailer": "mail/smtp", "@sentry/node": "errors/sentry"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "coverage", ".stack", ".turbo", ".tsout",
             "out", ".vercel", ".wrangler"}
SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
IMPORT_RES = (re.compile(r"""^\s*(?:import|export)\b[^'"]*?from\s*['"]([^'"]+)['"]"""),
              re.compile(r"""^\s*import\s*['"]([^'"]+)['"]"""),
              re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)"""),
              re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""))
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
MANIFEST = ".stack/generated" + ".json"
LOCK = "pnpm-lock.yaml"


def resolve_adapters(level, target):
    """One adapter per port from the two axes. Every port hangs on one axis, never both."""
    out = {}
    for port, table in BY_TARGET.items():
        out[port] = table.get(target)
    for port, table in BY_LEVEL.items():
        out[port] = table.get(level)
    if level == "full":
        out["storage"] = "s3"
    return out


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one place grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


class Unsupported(Exception):
    """A shape of the format this reader does not follow. The file counts as unread."""


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
    """Lines that carry content, as (indent, body, raw). Everything a reader cannot follow
    raises, and the file counts as unread."""
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


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_yaml(path):
    """(data, state): state is `read`, `missing`, or `unread: <why>`."""
    p = Path(path)
    if not p.is_file():
        return None, "missing"
    try:
        data = parse_yaml(read(p))
    except Unsupported as e:
        return None, f"unread: {e}"
    return (data if isinstance(data, dict) else {}), "read"


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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
    stack.yaml names that place, and workspace matching reads it too, so reporting the resolved
    target instead would make both miss.
    """
    try:
        return Path(path).relative_to(Path(root)).as_posix()
    except ValueError:
        return Path(path).as_posix()


def source_files(root):
    """Every source file in the tree, relative to the root, forward slashes.

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


def imports_of(text):
    """Every import specifier in a file, with the line it stands on."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for rx in IMPORT_RES:
            for m in rx.finditer(line):
                out.append((n, m.group(1)))
    return out


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v is not None]
    return [value]


def as_dict(value):
    return value if isinstance(value, dict) else {}


def workspaces_of(decl):
    """Workspace path to the list of paths it may import, both as forward-slash strings."""
    out = {}
    for key, allowed in as_dict(decl.get("workspaces")).items():
        out[str(key).strip("/")] = [str(a).strip("/") for a in as_list(allowed)]
    return out


def package_name(root, path):
    """The package name of a workspace: its manifest's `name`, else `@app/<basename>`."""
    data = read_json(Path(root) / path / "package.json")
    name = data.get("name") if isinstance(data, dict) else None
    if name:
        return str(name)
    base = path.rsplit("/", 1)[-1]
    return base if path.startswith("apps/") else f"@app/{base}"


def workspace_of(path, workspaces):
    """The workspace a file belongs to: the longest workspace path that prefixes it."""
    best = ""
    for ws in workspaces:
        if (path == ws or path.startswith(ws + "/")) and len(ws) > len(best):
            best = ws
    return best


def valid_waiver(w, today):
    """A waiver counts when it carries a reason, an owner and a date that has not passed."""
    if not isinstance(w, dict):
        return False
    until = str(w.get("until") or "")
    if not (w.get("reason") and w.get("owner") and ISO_DATE.match(until)):
        return False
    return dt.date.fromisoformat(until) >= today


def boundary_waivers(decl, today):
    out = set()
    for w in as_list(decl.get("waivers")):
        if valid_waiver(w, today) and str(w.get("kind")) == "boundary":
            out.add((str(w.get("file")), str(w.get("line"))))
    return out


def pairs(specs, fields=2):
    """The first `fields` words of every spec. The reason and the date are for a person to read."""
    out = set()
    for spec in specs or []:
        parts = spec.split()
        if len(parts) >= fields:
            out.add(tuple(parts[:fields]))
    return out


def owned(accepted):
    """The accepted entries this pass owns; an entry another pass owns is not this one's."""
    return {p for p in accepted if p[0] in MEASURES}


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one file is, two files are."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 import(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def report_rows(rep, cid, rows, bad, good, skip, one=None, by=None):
    """One finding per check, or the passing line with a zero that settles a row."""
    kept = [r for r in rows if (cid, r["target"]) not in skip]
    if len(kept) != len(rows):
        by = None             # a per-target count no longer matches the rows that stay
    rows = kept
    if rows:
        by = by or {r["target"]: 1 for r in rows}
        total = sum(by.values())
        word = ROW_WORD.get(cid, ("finding", "findings"))
        level = "FAIL" if cid in FAIL_IDS else "WARN"
        rep.add(level, cid, f"{plural(total, *word)} " + (one if total == 1 and one else bad),
                data=rows, measure=total, by=by)
    else:
        rep.add("PASS", cid, good, measure=0)


def unread(rep, cid, state):
    """A check that needs the declaration and has none carries no number."""
    why = "the declaration is missing" if state == "missing" else f"the declaration could not be read ({state[8:]})"
    rep.add("INFO", cid, f"{why}, so this check measured nothing")


# Every check below reads and never writes. Each takes the context and adds to the report.

def check_absent(rep, decl, state, skip):
    if decl is None:
        if state == "missing":
            rep.add("FAIL", "decl.absent", f"{plural(len(REQUIRED), 'missing declaration')}: "
                    "no stack.yaml stands in the root, so every guard reads no bar",
                    data=[{"target": "stack.yaml", "value": "missing"}],
                    measure=len(REQUIRED), by={"stack.yaml": len(REQUIRED)})
        else:
            unread(rep, "decl.absent", state)
        return
    rows = [{"target": f"stack.yaml:{k}", "value": "section missing"} for k in REQUIRED if k not in decl]
    report_rows(rep, "decl.absent", rows, "are missing from stack.yaml, and every pass reads them",
                "stack.yaml carries every section a pass reads", skip,
                one="is missing from stack.yaml, and every pass reads it")


def check_unmatched(rep, decl, root, skip):
    rows = []
    for i, w in enumerate(as_list(decl.get("waivers"))):
        f = str(as_dict(w).get("file") or "")
        if f and not (Path(root) / f).is_file():
            rows.append({"target": f"waivers[{i}].file", "value": f})
    ws = workspaces_of(decl)
    for key, allowed in ws.items():
        if not (Path(root) / key).is_dir():
            rows.append({"target": f"workspaces.{key}", "value": key})
        for j, a in enumerate(allowed):
            if a not in ws:
                rows.append({"target": f"workspaces.{key}[{j}]", "value": a})
    for i, e in enumerate(as_list(decl.get("port_exceptions"))):
        port = str(as_dict(e).get("port") or "")
        if port not in PORTS:
            rows.append({"target": f"port_exceptions[{i}].port", "value": port or "(empty)"})
    report_rows(rep, "decl.unmatched", rows, "of the declaration point at nothing",
                "every entry of the declaration points at something that exists", skip,
                one="of the declaration points at nothing")


def check_generated(rep, root, skip):
    manifest = read_json(Path(root) / MANIFEST)
    if not isinstance(manifest, dict):
        rep.add("INFO", "decl.generated", f"no {MANIFEST} in the tree, so nothing here says which "
                "files the generator owns")
        return
    disowned = set(as_list(manifest.get("disowned")))
    rows = []
    for path, digest in sorted(as_dict(manifest.get("files")).items()):
        if path in disowned:
            continue
        p = Path(root) / path
        if not p.is_file():
            rows.append({"target": path, "value": "missing"})
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            rows.append({"target": path, "value": "changed"})
    report_rows(rep, "decl.generated", rows, "the generator owns were changed by hand",
                "every generated file is as the generator wrote it", skip,
                one="the generator owns was changed by hand")


def check_undeclared(rep, decl, root, skip):
    ws = workspaces_of(decl) if decl is not None else {}
    rows = []
    for parent in ("apps", "packages"):
        folder = Path(root) / parent
        if not folder.is_dir():
            continue
        for d in sorted(folder.iterdir()):
            if d.is_dir() and (d / "package.json").is_file() and f"{parent}/{d.name}" not in ws:
                rows.append({"target": f"{parent}/{d.name}", "value": "not under workspaces"})
    report_rows(rep, "decl.undeclared", rows, "sit in the tree and the declaration does not name them",
                "every package in the tree stands under workspaces", skip,
                one="sits in the tree and the declaration does not name it")


def check_undecided(rep, decl, today, skip):
    rows = []
    for i, d in enumerate(as_list(decl.get("open_decisions"))):
        until = str(as_dict(d).get("until") or "")
        if ISO_DATE.match(until) and dt.date.fromisoformat(until) < today:
            rows.append({"target": str(as_dict(d).get("what") or f"open_decisions[{i}]"),
                         "value": f"due {until}"})
    report_rows(rep, "decl.undecided", rows, "are past the date they were to be taken by",
                "no open decision is past its date", skip,
                one="is past the date it was to be taken by")


def importers_of(text):
    """The `importers` map of the lock, by indentation alone: one entry per workspace path, the
    names under its dependency keys. The rest of the lock uses shapes the subset reader does not
    follow, and this check needs nothing from them."""
    out, inside, ws, section = {}, False, "", ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            inside = line == "importers:"
            continue
        if not inside or not line.endswith(":"):
            continue
        key = unquote(line.strip()[:-1])
        if indent == 2:
            ws, section = key, ""
            out.setdefault(ws, set())
        elif indent == 4:
            section = key
        elif indent == 6 and section in ("dependencies", "devDependencies", "optionalDependencies") and ws:
            out[ws].add(key)
    return out


def check_lock(rep, decl, root, skip):
    text = read(Path(root) / LOCK)
    if not text:
        rep.add("INFO", "lock.incomplete", f"{LOCK} is missing, so nothing here says what the "
                "lock resolves")
        return
    importers = importers_of(text)
    if not importers:
        rep.add("INFO", "lock.incomplete", f"{LOCK} carries no importers map this reader can "
                "follow, so nothing here says what it resolves")
        return
    rows, by = [], {}
    for ws in workspaces_of(decl):
        manifest = read_json(Path(root) / ws / "package.json")
        if not isinstance(manifest, dict):
            continue
        wanted = set(as_dict(manifest.get("dependencies"))) | set(as_dict(manifest.get("devDependencies")))
        have = importers.get(ws) or importers.get("./" + ws) or set()
        missing = sorted(wanted - have)
        if missing:
            rows.append({"target": ws, "value": ", ".join(missing)})
            by[ws] = len(missing)
    report_rows(rep, "lock.incomplete", rows, "name a dependency the lock does not resolve",
                "the lock resolves every workspace manifest", skip,
                one="names a dependency the lock does not resolve", by=by)


def major(text):
    m = re.search(r"(\d+)", str(text or ""))
    return m.group(1) if m else ""


def manager_key(text):
    """`pnpm@10.4.1` as (pnpm, 10): the name and the major are what two places must agree on."""
    name, _, version = str(text or "").partition("@")
    return name.strip(), major(version)


def node_versions_in(data):
    """Every `node-version` value in a parsed workflow, wherever it stands."""
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "node-version":
                out.append(v)
            else:
                out += node_versions_in(v)
    elif isinstance(data, list):
        for v in data:
            out += node_versions_in(v)
    return out


def check_runtime(rep, decl, root, skip):
    runtime = as_dict(decl.get("runtime"))
    node, manager = major(runtime.get("node")), manager_key(runtime.get("package_manager"))
    rows = []

    def place(name, says, wants):
        rows.append({"target": name, "value": f"says {says}, declaration says {wants}"})

    for f in (".nvmrc", ".node-version"):
        text = read(Path(root) / f).strip()
        if node and text and major(text) != node:
            place(f, text, node)
    manifest = read_json(Path(root) / "package.json")
    if isinstance(manifest, dict):
        engine = as_dict(manifest.get("engines")).get("node")
        if node and engine and major(engine) != node:
            place("package.json engines.node", engine, node)
        pm = manifest.get("packageManager")
        if manager[0] and pm and manager_key(pm) != manager:
            place("package.json packageManager", pm, runtime.get("package_manager"))
    folder = Path(root) / ".github" / "workflows"
    for p in sorted(folder.iterdir()) if folder.is_dir() else []:
        if p.suffix not in (".yml", ".yaml"):
            continue
        data, state = read_yaml(p)
        if data is None:
            rep.add("INFO", "lock.runtime", f"{rel(p, root)} could not be read ({state[8:]}), "
                    "so its runtime pin is not compared")
            continue
        for v in node_versions_in(data):
            if node and major(v) and major(v) != node:
                place(f"{rel(p, root)} node-version", v, node)
    for line in read(Path(root) / "Dockerfile").splitlines():
        m = re.match(r"\s*FROM\s+node:(\S+)", line)
        if m and node and major(m.group(1)) != node:
            place("Dockerfile FROM node", m.group(1), node)
    report_rows(rep, "lock.runtime", rows, "pin a runtime the declaration does not name",
                "every pinning place agrees with the declared runtime", skip,
                one="pins a runtime the declaration does not name")


def scan_imports(root, files, decl, today):
    """Every edge, deep import and vendor import in the tree, from the import lines alone."""
    ws = workspaces_of(decl) if decl is not None else {}
    names = {package_name(root, w): w for w in ws}
    exports = {w: set(as_dict(as_dict(read_json(Path(root) / w / "package.json")).get("exports")))
               for w in ws}
    waived = boundary_waivers(decl, today) if decl is not None else set()
    crossed, deep, vendor, graph = [], [], [], {}
    for f in files:
        own = workspace_of(f, ws)
        text = read(Path(root) / f)
        for line, spec in imports_of(text):
            vendor_hit(vendor, f, line, spec)
            if spec.startswith("."):
                target = rel(Path(root) / Path(f).parent / spec, root)
                other = workspace_of(target, ws)
                if own and other and other != own:
                    graph.setdefault(own, set()).add(other)
                    deep.append({"target": f"{f}:{line}", "value": f"{spec} reaches into {other}"})
                    edge(crossed, waived, f, line, own, other, ws)
                continue
            name = longest_match(spec, names)
            if not name:
                continue
            other = names[name]
            if not own or other == own:
                continue
            graph.setdefault(own, set()).add(other)
            edge(crossed, waived, f, line, own, other, ws)
            sub = spec[len(name):].lstrip("/")
            if sub and "./" + sub not in exports.get(other, set()):
                deep.append({"target": f"{f}:{line}", "value": f"{spec} reaches past the entry point of {name}"})
    return crossed, deep, vendor, graph


def longest_match(spec, names):
    best = ""
    for name in names:
        if (spec == name or spec.startswith(name + "/")) and len(name) > len(best):
            best = name
    return best


def edge(crossed, waived, f, line, own, other, ws):
    if other in ws.get(own, []):
        return
    if (f, str(line)) in waived:
        return
    allowed = ", ".join(ws.get(own, [])) or "none"
    crossed.append({"target": f"{f}:{line}", "value": f"{own} imports {other}, allowed: {allowed}",
                    "workspace": own})


def vendor_hit(vendor, f, line, spec):
    for module, adapters in VENDORS.items():
        if spec == module or spec.startswith(module + "/"):
            inside = any(f.startswith(f"{PORTS_DIR}/{p}/") for p in PORTS)
            if not inside:
                vendor.append({"target": f"{f}:{line}", "value": f"{module}, which belongs to {adapters}"})


def check_boundaries(rep, decl, state, scanned, skip):
    crossed, deep, vendor, graph = scanned
    if decl is None:
        unread(rep, "boundary.crossed", state)
        unread(rep, "boundary.deep-import", state)
    else:
        by = {}
        for r in crossed:
            by[r["workspace"]] = by.get(r["workspace"], 0) + 1
        rows = [{"target": r["target"], "value": r["value"]} for r in crossed]
        report_rows(rep, "boundary.crossed", rows, "cross an edge the declaration does not allow",
                    "every import stays inside the edges workspaces allows", skip,
                    one="crosses an edge the declaration does not allow", by=by)
        report_rows(rep, "boundary.deep-import", deep, "reach past a package's entry point",
                    "every import of another package names its entry point", skip,
                    one="reaches past a package's entry point")
    cycles = sorted({tuple(sorted((a, b))) for a, bs in graph.items() for b in bs
                     if a in graph.get(b, set()) and a != b})
    rows = [{"target": f"{a} and {b}", "value": "import each other"} for a, b in cycles]
    report_rows(rep, "boundary.cycle", rows, "of packages import each other",
                "no two packages import each other", skip, one="of packages imports each other")
    report_rows(rep, "adapter.bypassed", vendor, "name a vendor module outside its adapter",
                "every vendor module is imported by its adapter alone", skip,
                one="names a vendor module outside its adapter")


def check_adapters(rep, decl, state, root, skip):
    rows, by = [], {}
    for port in PORTS:
        missing = [part for part in PARTS if not (Path(root) / PORTS_DIR / port / part).is_file()]
        if missing:
            rows.append({"target": port, "value": "missing " + ", ".join(missing)})
            by[port] = len(missing)
    report_rows(rep, "adapter.missing", rows, "of the eight ports are missing",
                "every port carries its contract, its offline adapter, its wired adapter and its smoke test",
                skip, one="of the eight ports is missing", by=by)
    if decl is None:
        unread(rep, "adapter.untargeted", state)
        return
    level, target = str(decl.get("oss_level") or ""), str(decl.get("target") or "")
    if level not in BY_LEVEL["auth"] or target not in BY_TARGET["db"]:
        rep.add("INFO", "adapter.untargeted", f"the axes read {level or '(empty)'} and "
                f"{target or '(empty)'}, which the adapter table does not know, so no port is compared")
        return
    wanted = resolve_adapters(level, target)
    excepted = {str(as_dict(e).get("port")) for e in as_list(decl.get("port_exceptions"))}
    rows = []
    for port in PORTS:
        declared = str(as_dict(decl.get("ports")).get(port) or "")
        if port in excepted or declared == wanted[port]:
            continue
        rows.append({"target": port, "value": f"declared {declared or '(empty)'}, axes resolve to {wanted[port]}"})
    report_rows(rep, "adapter.untargeted", rows, "declare an adapter the two axes do not resolve to",
                "every port declares the adapter its axes resolve to", skip,
                one="declares an adapter the two axes do not resolve to")


def snapshot_note(rep, decl, path):
    """The keys on which the workspace's snapshot and the repository's declaration differ."""
    snap, state = read_yaml(path)
    if snap is None:
        rep.add("INFO", "decl.absent", f"the snapshot {path} is {state}, so nothing compares it to the declaration")
        return
    if decl is None:
        return
    keys = sorted(k for k in set(snap) | set(decl) if snap.get(k) != decl.get(k))
    if keys:
        rep.add("INFO", "decl.absent", "the declaration differs from the snapshot in the workspace on "
                + ", ".join(keys) + ": copy it there when the change is meant, or revert it",
                data=[{"target": k, "value": "differs"} for k in keys])


def collect(root, today, a):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    rep = Report()
    skip = owned(pairs(a.accept))
    decl, state = read_yaml(Path(root) / "stack.yaml")
    files = source_files(root)
    check_absent(rep, decl, state, skip)
    if decl is None:
        for cid in ("decl.unmatched", "decl.undecided", "lock.incomplete", "lock.runtime"):
            unread(rep, cid, state)
    else:
        check_unmatched(rep, decl, root, skip)
        check_undecided(rep, decl, today, skip)
        check_lock(rep, decl, root, skip)
        check_runtime(rep, decl, root, skip)
    check_generated(rep, root, skip)
    check_undeclared(rep, decl, root, skip)
    check_boundaries(rep, decl, state, scan_imports(root, files, decl, today), skip)
    check_adapters(rep, decl, state, root, skip)
    if a.snapshot:
        snapshot_note(rep, decl, a.snapshot)
    if skip:
        rep.add("INFO", "decl.unmatched",
                f"{plural(len(skip), 'finding')} {verb(len(skip), 'are', 'is')} recorded as accepted "
                "and left out of the counts",
                data=[{"target": t, "value": c} for c, t in sorted(skip)])
    return rep, state, len(files)


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


# The gate of this theme (references/risk-classes.md): a contract file changes through review. An
# id whose fix is a contract file stands under it, and a gate is passed before the class applies.
# Only the ids this pass emits are listed; the guards pass holds its own list.
GATE_REVIEW = ("decl.absent", "decl.unmatched", "decl.undecided", "boundary.crossed",
               "adapter.untargeted")


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
    return "=" if old == now else f"{now - old:+d}"


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
    fix = [" · ".join(filter(None, [klass or "no class", gate_of(item["id"]),
                                    row.get("fix") or "fixes table of jorekai-stack:stack"]))]
    out += field("fix", fix)
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
    out = [paint(f"drift  {target}  {plural(count, 'source file')}", "head"),
           f"measured against  {standards}", "",
           bar(fails, len(findings) - fails, len(notes), len(passed))]
    if findings or notes:
        out += [""] + listing(findings, notes, fixes, previous)
    if passed:
        out += [""] + wrapped("passed", [i["id"] for i in passed])
    if findings:
        out += ["", paint("next", "head") + "  put the declaration right first, then look each id "
                "up in the fixes table of jorekai-stack:stack; a change to stack.yaml is a review"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
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
                    help="the workspace's copy of stack.yaml, noted when it differs")
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
    rep, state, count = collect(root, today, a)
    target = root.resolve().name
    if a.json:
        print(json.dumps({"tool": "drift", "target": target, "generated": today.isoformat(),
                          "counts": rep.counts(), "declaration": state, "files": count,
                          "items": rep.items}, indent=2, ensure_ascii=False))
    elif a.explain:
        print(explain_report(rep, target, load_fixes(a.fixes or None), a.explain,
                             previous_measures(a.previous) if a.previous else None))
    else:
        standards = f"stack.yaml {state} · today {today.isoformat()}"
        print(text_report(count, rep, target, standards, load_fixes(a.fixes or None),
                          previous_measures(a.previous) if a.previous else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
