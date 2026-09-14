#!/usr/bin/env python3
"""Lay the guards of a declared repository out as files, wire its ports, or adopt one that exists.

Usage:
  lay.py [--root DIR] --flags            the generator command and the install command
  lay.py [--root DIR] --plan             one line per file: path | action | reason, nothing written
  lay.py [--root DIR]                    write every file the plan names, and the manifest
  lay.py [--root DIR] --wire             copy the adapter the two axes resolve to, per port
  lay.py [--root DIR] --check            the manifest against the tree, the four parts per port
  lay.py [--root DIR] --disown PATH      hand a generated file over to the project
  lay.py [--root DIR] --adopt [--plan]   the same contracts into a repository that exists

Reads stack.yaml in the root; nothing runs without it. A file that exists and is not in the
manifest is never overwritten: the plan names it and moves on. The generator owns what it
writes (decisions/0034): every owned file is listed with its hash in .stack/generated.json, and
a change made by hand is what `jorekai-stack:drift` reports.

Stdlib only. Exit 1 when --check finds a problem or the root holds no declaration.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
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


TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
MANIFEST = ".stack/generated.json"
PORTS = ("db", "storage", "jobs", "host", "auth", "mail", "analytics", "errors")
PORT_DIR = "packages/ports/src"
ADAPTER_SUFFIX = ".adapter" + ".ts"
# The parts of a port. A port that lacks one is what `adapter.missing` counts.
PORT_PARTS = ("contract.ts", "memory" + ADAPTER_SUFFIX, "wired.ts", "smoke.test.ts")
# One adapter per port, decided by exactly one axis (references/ports.md). Duplicated in the
# choose and drift skills on purpose: each skill stays standalone.
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
LEVELS = ("minimal", "pragmatic", "full")
TARGETS = ("vercel", "cloudflare", "fly", "hetzner", "railway")
# The vendor modules an adapter imports, and the range the wire step writes into the manifest.
# A range is resolved by the install, and the weekly workflow of the collection proves it.
VENDOR_OF = {"db/neon-http": ["@neondatabase/serverless"], "db/pool": ["pg"],
             "db/hyperdrive": ["pg"], "storage/vercel-blob": ["@vercel/blob"],
             "storage/r2": ["@aws-sdk/client-s3"], "storage/tigris": ["@aws-sdk/client-s3"],
             "storage/s3": ["@aws-sdk/client-s3"], "auth/clerk": ["@clerk/backend"],
             "auth/better-auth": ["better-auth"], "mail/smtp": ["nodemailer"],
             "errors/sentry": ["@sentry/node"]}
VENDOR_DEPS = {"@neondatabase/serverless": "^1", "pg": "^8", "@vercel/blob": "^1",
               "@aws-sdk/client-s3": "^3", "@clerk/backend": "^2", "better-auth": "^1",
               "nodemailer": "^7", "@sentry/node": "^10"}
# The app generator, as data. A second one is a second entry here and a row in
# references/generators.md, never a second template tree.
GENERATORS = {
    "create-next-app": {
        "dir": "apps/web",
        "command": 'pnpm dlx create-next-app@latest apps/web --ts --eslint --app --src-dir '
                   '--import-alias "@/*" --use-pnpm --skip-install --no-tailwind --webpack --disable-git --no-agents-md --yes',
        "replaces": ["apps/web/tsconfig.json", "apps/web/next.config.ts", "apps/web/src/app/page.tsx"],
        # The generator writes a repository and a workspace file of its own inside the app; the
        # root carries both, and a nested one makes the package manager and the hooks read two.
        "removes": ["apps/web/eslint.config.mjs", "apps/web/.gitignore", "apps/web/.git",
                    "apps/web/pnpm-workspace.yaml", "apps/web/AGENTS.md", "apps/web/CLAUDE.md"],
    },
}
# What the project owns among the files the templates write: the manifest never lists these.
PROJECT_OWNED = re.compile(
    r"^(?:stack\.yaml|rules/[^/]+\.(?:rule|test)\.mjs|packages/(?:config|ui)/src/index\.ts"
    r"|.*\.test\.tsx?|.*\.spec\.tsx?|apps/web/src/app/.*|apps/web/e2e/.*"
    r"|packages/ports/src/[^/]+/contract\.ts)$")
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "coverage", ".stack", ".turbo",
             "out", ".tsout"}
SOURCE = re.compile(r"\.(?:ts|tsx|js|jsx|mjs|cjs)$")
# The three kinds of suppression an adopted repository carries, one waiver proposed per hit.
ESCAPES = {"type": re.compile(r"@ts-ignore|@ts-expect-error|\bas any\b"),
           "lint": re.compile(r"eslint-disable"),
           "test": re.compile(r"\b(?:it|test|describe)\.(?:skip|only)\s*\(")}
WAIVER_DAYS = 90


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
    """Lines that carry content, as (indent, body, raw). Anything unsupported raises."""
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
    body = []
    while pos < len(lines) and lines[pos][0] > indent:
        body.append(lines[pos][2])
        pos += 1
    return "\n".join(body), pos


def parse_block(lines, pos, indent):
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
            take = 0
            while pos + take < len(lines) and lines[pos + take][0] >= inner:
                take += 1
            sub = [(inner, rest, rest)] + lines[pos:pos + take]
            value, _ = parse_map(sub, 0, inner)
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
    """The parsed stack.yaml, or an exit with the reason nothing can run without it."""
    path = root / "stack.yaml"
    if not path.is_file():
        sys.exit(f"no stack.yaml in {root}: run jorekai-stack:choose first")
    try:
        data = parse_yaml(path.read_text(encoding="utf-8"))
    except Unsupported as e:
        sys.exit(f"stack.yaml could not be read ({e}), and nothing is laid out over a declaration nobody can read")
    if not isinstance(data, dict):
        sys.exit("stack.yaml is not a map of sections")
    return data


def resolve(level, target):
    """The eight adapters the two axes decide, with the one override (references/ports.md)."""
    out = {}
    for port, table in BY_TARGET.items():
        out[port] = table.get(target, "")
    for port, table in BY_LEVEL.items():
        out[port] = table.get(level, "")
    if level == "full":
        out["storage"] = "s3"
    return out


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_manifest(root):
    path = root / MANIFEST
    if not path.is_file():
        return {"generator": "create-next-app", "written": "", "files": {}, "disowned": [],
                "wired": [], "replaced": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        sys.exit(f"{MANIFEST} is not JSON; delete it and lay out again")
    data.setdefault("files", {})
    data.setdefault("disowned", [])
    data.setdefault("wired", [])
    data.setdefault("replaced", [])
    return data


def write_manifest(root, manifest, today):
    manifest["written"] = today.isoformat()
    manifest["files"] = dict(sorted(manifest["files"].items()))
    path = root / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def render(text, subs):
    for k, v in subs.items():
        text = text.replace("{{%s}}" % k, str(v))
    return text


def substitutions(decl, owner, port=""):
    runtime = decl.get("runtime") or {}
    subs = {"NAME": decl.get("name") or "app", "NODE": runtime.get("node") or "22",
            "PACKAGE_MANAGER": runtime.get("package_manager") or "pnpm@10.17.1",
            "OWNER": owner, "TARGET": decl.get("target") or ""}
    if port:
        subs["PORT"] = port
        subs["Port"] = port[:1].upper() + port[1:]
    return subs


def template_files(base):
    """Every file under a template directory, as (relative path, absolute path)."""
    if not base.is_dir():
        return []
    out = []
    for p in sorted(base.rglob("*")):
        if p.is_file():
            out.append((p.relative_to(base).as_posix(), p))
    return out


def owned(rel):
    return not PROJECT_OWNED.match(rel)


def planned_files(root, decl, owner):
    """Every file the templates produce for this declaration: (path, content, owned)."""
    subs = substitutions(decl, owner)
    out = []
    for rel, src in template_files(TEMPLATES / "root"):
        out.append((rel, render(src.read_text(encoding="utf-8"), subs), owned(rel)))
    for pkg in ("config", "env", "ui", "ports"):
        for rel, src in template_files(TEMPLATES / "packages" / pkg):
            if rel.startswith("src/_port/"):
                continue
            path = f"packages/{pkg}/{rel}"
            out.append((path, render(src.read_text(encoding="utf-8"), subs), owned(path)))
    for port in PORTS:
        for rel, src in template_files(TEMPLATES / "packages" / "ports" / "src" / "_port"):
            path = f"{PORT_DIR}/{port}/{rel}"
            text = render(src.read_text(encoding="utf-8"), substitutions(decl, owner, port))
            if rel == "wired.ts":
                # A port already wired stays wired: laying out again is not unwiring.
                text = wired_text(root, decl, port, text)
            out.append((path, text, owned(path)))
        for name in ("contract.ts", "memory" + ADAPTER_SUFFIX, "smoke.test.ts"):
            src = TEMPLATES / "ports" / port / name
            if src.is_file():
                path = f"{PORT_DIR}/{port}/{name}"
                out.append((path, render(src.read_text(encoding="utf-8"),
                                         substitutions(decl, owner, port)), owned(path)))
    gen = GENERATORS["create-next-app"]
    if (root / gen["dir"] / "package.json").is_file():
        for rel, src in template_files(TEMPLATES / "apps" / "web"):
            path = f"apps/web/{rel}"
            out.append((path, render(src.read_text(encoding="utf-8"), subs), owned(path)))
    return out


def wired_text(root, decl, port, memory_text):
    """The wired.ts line for a port whose chosen adapter file already stands in the tree."""
    level, target = str(decl.get("oss_level") or ""), str(decl.get("target") or "")
    try:
        adapter = resolve(level, target).get(port, "")
    except (KeyError, ValueError):
        return memory_text
    if adapter and (root / PORT_DIR / port / (adapter + ADAPTER_SUFFIX)).is_file():
        return memory_text.replace('from "./memory.adapter";', f'from "./{adapter}.adapter";')
    return memory_text


def plan(root, decl, owner, adopt=False):
    """One line per file: path, action, reason. Nothing is written here."""
    manifest = read_manifest(root)
    disowned = set(manifest["disowned"])
    gen = GENERATORS["create-next-app"]
    rows = []
    for path, content, is_owned in planned_files(root, decl, owner):
        full = root / path
        if path in disowned:
            rows.append((path, "skip", "disowned, the project owns it now", content, False))
        elif path in manifest["wired"] and full.exists():
            rows.append((path, "skip", "wired, --wire regenerates it", content, False))
        elif not full.exists():
            rows.append((path, "write", "owned by the generator" if is_owned else "written once, then the project's", content, is_owned))
        elif adopt:
            rows.append((path, "skip", "exists, left alone", content, False))
        elif path in gen["replaces"] and path not in manifest["files"] and path not in manifest["replaced"]:
            rows.append((path, "replace", "the generator's file, replaced by the one that reads the base config", content, is_owned))
        elif not is_owned:
            rows.append((path, "skip", "exists and belongs to the project", content, False))
        elif path not in manifest["files"]:
            rows.append((path, "skip", "exists and is not in the manifest, so it is left alone", content, False))
        elif sha256(full) != manifest["files"][path]:
            rows.append((path, "skip", "changed by hand; --disown it, or revert it and lay out again", content, False))
        else:
            rows.append((path, "write", "owned, regenerated", content, True))
    if not adopt and (root / gen["dir"] / "package.json").is_file():
        for path in gen["removes"]:
            if (root / path).exists():
                rows.append((path, "remove", "the generator's file, the root carries it", "", False))
    return rows


def print_plan(rows):
    width = max((len(r[0]) for r in rows), default=4)
    key = {"write": "PASS", "skip": "dim", "replace": "WARN", "remove": "WARN"}
    for path, action, reason, _, _ in rows:
        print(f"{path.ljust(width)} | {paint(action.ljust(7), key[action])} | {reason}")
    counts = {}
    for _, action, _, _, _ in rows:
        counts[action] = counts.get(action, 0) + 1
    print(" · ".join(f"{n} {a}" for a, n in sorted(counts.items())) or "nothing to do")


def lay(root, decl, owner, today, adopt=False):
    rows = plan(root, decl, owner, adopt=adopt)
    manifest = read_manifest(root)
    for path, action, reason, content, is_owned in rows:
        full = root / path
        if action in ("write", "replace"):
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            if path.endswith(".sh"):
                full.chmod(full.stat().st_mode | 0o111)
            if is_owned:
                manifest["files"][path] = sha256(full)
            elif action == "replace" and path not in manifest["replaced"]:
                # Replaced once, then the project's: a later lay-out leaves it alone.
                manifest["replaced"].append(path)
            print(f"{paint(action, 'PASS')}  {path}")
        elif action == "remove":
            shutil.rmtree(full) if full.is_dir() else full.unlink()
            print(f"{paint('removed', 'WARN')}  {path}")
        else:
            print(f"{paint('skip', 'dim')}  {path}  {reason}")
    for line in orphans(root, manifest, {r[0] for r in rows}):
        print(line)
    write_manifest(root, manifest, today)
    gen = GENERATORS["create-next-app"]
    if not (root / gen["dir"] / "package.json").is_file():
        # The generator refuses a parent directory that does not exist yet.
        (root / gen["dir"]).parent.mkdir(parents=True, exist_ok=True)
        print(paint("next", "head") + f"  run the generator, then lay out again for {gen['dir']}:")
        print(f"      {gen['command']}")
    else:
        for line in app_manifest(root / gen["dir"] / "package.json"):
            print(line)
        print(paint("next", "head") + "  lay.py --wire, then the install command from --flags")


def orphans(root, manifest, produced):
    """Owned files no template produces any more: dropped from the manifest, and deleted when
    they still carry the hash they were written with, so a stale copy cannot outlive its template."""
    out = []
    for path in sorted(set(manifest["files"]) - produced - set(manifest["wired"])):
        full = root / path
        if full.is_file() and sha256(full) == manifest["files"][path]:
            full.unlink()
            out.append(f"{paint('removed', 'WARN')}  {path}  no template produces it any more")
        elif full.is_file():
            out.append(f"{paint('released', 'WARN')}  {path}  no template produces it any more, and "
                       "it was changed by hand, so it stays as the project's")
        manifest["files"].pop(path, None)
    return out


APP_DEPS = ("@app/env", "@app/ports")


def app_manifest(path):
    """The app depends on the packages its routes import; the generator's manifest does not know them yet."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"{paint('skip', 'dim')}  {path.name} could not be read, add the workspace packages by hand"]
    deps = data.setdefault("dependencies", {})
    added = [d for d in APP_DEPS if d not in deps]
    for d in added:
        deps[d] = "workspace:*"
    if added:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return [f"{paint('declared', 'PASS')}  {', '.join(added)} in {path.parent.name}/package.json"]
    return []


def flags(root, decl):
    gen = GENERATORS["create-next-app"]
    runtime = decl.get("runtime") or {}
    print(f"generator: {runtime.get('generator') or 'create-next-app'}")
    print(f"command: {gen['command']}")
    print("install: pnpm install")
    print("browser: pnpm exec playwright install chromium")
    print(f"replaces: {', '.join(gen['replaces'])}")
    print(f"removes: {', '.join(gen['removes'])}")
    level, target = decl.get("oss_level") or "", decl.get("target") or ""
    adapters = resolve(level, target)
    print("adapters: " + ", ".join(f"{p}={adapters[p] or '?'}" for p in PORTS))


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def remember(manifest, path, full):
    """A file the wire step wrote: hashed like every owned file, and listed under `wired` so the
    next lay-out leaves it to --wire instead of regenerating it from the unwired template."""
    manifest["files"][path] = sha256(full)
    if path not in manifest["wired"]:
        manifest["wired"].append(path)


def wire(root, decl, owner, today):
    """The adapter each port resolves to, copied in, wired, and its vendor modules declared."""
    level, target = decl.get("oss_level") or "", decl.get("target") or ""
    if level not in LEVELS or target not in TARGETS:
        sys.exit(f"stack.yaml names oss_level {level!r} and target {target!r}; "
                 f"one of {', '.join(LEVELS)} and one of {', '.join(TARGETS)}")
    adapters = resolve(level, target)
    manifest = read_manifest(root)
    deps = {}
    for port in PORTS:
        adapter = adapters[port]
        src = TEMPLATES / "ports" / port / (adapter + ADAPTER_SUFFIX)
        if not src.is_file():
            print(f"{paint('missing', 'FAIL')}  no template for {port}/{adapter}: {src}")
            continue
        dest_dir = root / PORT_DIR / port
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / (adapter + ADAPTER_SUFFIX)
        dest.write_text(render(src.read_text(encoding="utf-8"), substitutions(decl, owner, port)),
                        encoding="utf-8")
        remember(manifest, f"{PORT_DIR}/{port}/{adapter}{ADAPTER_SUFFIX}", dest)
        wired_tpl = TEMPLATES / "packages" / "ports" / "src" / "_port" / "wired.ts"
        if wired_tpl.is_file():
            text = render(wired_tpl.read_text(encoding="utf-8"), substitutions(decl, owner, port))
            text = text.replace("./memory.adapter", f"./{adapter}.adapter")
            (dest_dir / "wired.ts").write_text(text, encoding="utf-8")
            remember(manifest, f"{PORT_DIR}/{port}/wired.ts", dest_dir / "wired.ts")
        for module in VENDOR_OF.get(f"{port}/{adapter}", []):
            deps[module] = VENDOR_DEPS[module]
        print(f"{paint('wired', 'PASS')}  {port}  {adapter}")
    pkg_path = root / "packages" / "ports" / "package.json"
    pkg = read_json(pkg_path) if pkg_path.is_file() else None
    if isinstance(pkg, dict):
        pkg.setdefault("dependencies", {}).update(deps)
        pkg["dependencies"] = dict(sorted(pkg["dependencies"].items()))
        pkg_path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
        remember(manifest, "packages/ports/package.json", pkg_path)
        print(f"{paint('declared', 'PASS')}  {', '.join(sorted(deps)) or 'no vendor module'} in packages/ports/package.json")
    else:
        print(f"{paint('missing', 'FAIL')}  packages/ports/package.json: lay out first")
    for rel, src in template_files(TEMPLATES / "hosts" / target):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(src.read_text(encoding="utf-8"), substitutions(decl, owner)),
                        encoding="utf-8")
        remember(manifest, rel, dest)
        print(f"{paint('host', 'PASS')}  {rel}")
    library = TEMPLATES / "wizard" / "wizard.sh"
    stages = TEMPLATES / "wizard" / "stages.sh"
    if library.is_file() and stages.is_file():
        dest = root / "scripts" / "wizard.sh"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(library.read_text(encoding="utf-8") + stages.read_text(encoding="utf-8"),
                        encoding="utf-8")
        dest.chmod(dest.stat().st_mode | 0o111)
        remember(manifest, "scripts/wizard.sh", dest)
        print(f"{paint('wizard', 'PASS')}  scripts/wizard.sh")
    write_manifest(root, manifest, today)
    print(paint("next", "head") + "  pnpm install, then pnpm exec playwright install chromium, then pnpm check")


def check(root):
    """The manifest against the tree, and the four parts of every port. `ok` or one line each."""
    problems = []
    path = root / MANIFEST
    if not path.is_file():
        problems.append(f"no {MANIFEST}: lay out first")
    else:
        manifest = read_manifest(root)
        disowned = set(manifest["disowned"])
        for rel, digest in sorted(manifest["files"].items()):
            if rel in disowned:
                continue
            full = root / rel
            if not full.is_file():
                problems.append(f"missing  {rel}  generated and gone; lay out again, or --disown it")
            elif sha256(full) != digest:
                problems.append(f"changed  {rel}  changed by hand; regenerate it, or --disown it")
    for port in PORTS:
        for part in PORT_PARTS:
            if not (root / PORT_DIR / port / part).is_file():
                problems.append(f"missing  {PORT_DIR}/{port}/{part}  a port has four parts; lay out again")
    for line in problems:
        word, _, rest = line.partition("  ")
        print(f"{paint(word, 'WARN')}  {rest}" if rest else paint(line, "WARN"))
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def disown(root, rel, today):
    manifest = read_manifest(root)
    if rel not in manifest["files"]:
        sys.exit(f"{rel} is not a generated file in {MANIFEST}")
    if rel not in manifest["disowned"]:
        manifest["disowned"].append(rel)
    write_manifest(root, manifest, today)
    print(f"disowned  {rel}  the project owns it now, and drift no longer reads it")


def source_files(root):
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if SOURCE.search(n):
                yield Path(base, n).relative_to(root).as_posix()


def suppressions(root):
    """Every suppression in the tree, as (kind, file, line)."""
    out = []
    for rel in sorted(source_files(root)):
        if rel == "scripts/waivers.mjs":
            continue
        try:
            lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for kind, pattern in ESCAPES.items():
                if pattern.search(line):
                    out.append((kind, rel, i))
    return out


def waiver_block(hits, until):
    lines = []
    for kind, rel, line in hits:
        lines += [f"  - kind: {kind}", f"    file: {rel}", f"    line: {line}",
                  '    reason: ""', f"    until: {until}", '    owner: ""']
    return "\n".join(lines)


def measured_bars(root):
    """The bars an adopted repository starts from: what the gate measured, where it ran."""
    bars = {}
    dead = read_json(root / ".stack" / ("dead" + ".json"))
    if isinstance(dead, dict):
        for key, bar in (("exports", "dead_exports_max"), ("files", "dead_files_max"),
                         ("dependencies", "dead_deps_max")):
            if isinstance(dead.get(key), int):
                bars[bar] = dead[key]
    cov = read_json(root / "coverage" / "coverage-summary.json")
    total = (cov or {}).get("total") if isinstance(cov, dict) else None
    if isinstance(total, dict):
        for key, bar in (("lines", "coverage_lines"), ("branches", "coverage_branches")):
            pct = (total.get(key) or {}).get("pct")
            if isinstance(pct, (int, float)):
                bars[bar] = int(pct)
    return bars


def adopt(root, decl, owner, today, dry):
    """The same contracts into a repository that exists: nothing overwritten, every existing
    file named, one waiver proposed per suppression, the bars set to what was measured."""
    rows = plan(root, decl, owner, adopt=True)
    if dry:
        print_plan(rows)
    else:
        lay(root, decl, owner, today, adopt=True)
    hits = suppressions(root)
    until = (today + dt.timedelta(days=WAIVER_DAYS)).isoformat()
    bars = measured_bars(root)
    print("")
    print(paint("waivers", "head") + f"  {len(hits)} suppression(s) found, one entry proposed each, "
          f"until {until}; the reason and the owner are a person's to write, and an entry without "
          "them does not count")
    for kind, rel, line in hits[:20]:
        print(f"      {kind.ljust(5)} {rel}:{line}")
    if len(hits) > 20:
        print(f"      +{len(hits) - 20} more")
    print(paint("bars", "head") + ("  " + ", ".join(f"{k}={v}" for k, v in sorted(bars.items()))
                                  if bars else "  nothing measured yet: the bars stay at the "
                                  "defaults until the gate ran once, then adopt again"))
    if dry:
        return
    path = root / "stack.yaml"
    text = path.read_text(encoding="utf-8")
    if hits:
        block = waiver_block(hits, until)
        if re.search(r"^waivers:\s*\[\]\s*$", text, re.M):
            text = re.sub(r"^waivers:\s*\[\]\s*$", "waivers:\n" + block, text, count=1, flags=re.M)
        elif re.search(r"^waivers:\s*$", text, re.M):
            text = re.sub(r"^waivers:\s*$", "waivers:\n" + block, text, count=1, flags=re.M)
        else:
            text = text.rstrip("\n") + "\nwaivers:\n" + block + "\n"
    for key, v in bars.items():
        text = re.sub(rf"^(\s*{key}:\s*)\S+", rf"\g<1>{v}", text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")
    print(f"{paint('written', 'PASS')}  stack.yaml: {len(hits)} waiver(s) proposed, "
          f"{len(bars)} bar(s) set from the measured state")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repository, holding stack.yaml")
    ap.add_argument("--flags", action="store_true", help="the generator command and the install command")
    ap.add_argument("--plan", action="store_true", help="print what would be written, write nothing")
    ap.add_argument("--wire", action="store_true", help="copy the adapter each port resolves to")
    ap.add_argument("--check", action="store_true", help="the manifest against the tree")
    ap.add_argument("--adopt", action="store_true", help="into a repository that exists, overwriting nothing")
    ap.add_argument("--disown", default="", metavar="PATH", help="hand a generated file to the project")
    ap.add_argument("--owner", default="@OWNER", metavar="HANDLE", help="the placeholder CODEOWNERS carries")
    ap.add_argument("--today", default=None, metavar="YYYY-MM-DD", help="for tests")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    if a.check:
        return check(root)
    if a.disown:
        disown(root, a.disown, today)
        return 0
    decl = read_declaration(root)
    if a.flags:
        flags(root, decl)
    elif a.wire:
        wire(root, decl, a.owner, today)
    elif a.adopt:
        adopt(root, decl, a.owner, today, a.plan)
    elif a.plan:
        print_plan(plan(root, decl, a.owner))
    else:
        lay(root, decl, a.owner, today)
    return 0


if __name__ == "__main__":
    sys.exit(main())
