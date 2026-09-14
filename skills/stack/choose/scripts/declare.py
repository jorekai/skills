#!/usr/bin/env python3
"""Write the declaration of a repository: two axes, eight adapters, ten bars, as stack.yaml.

Usage:
  declare.py --root DIR --oss LEVEL --target TARGET [--profile P] [--name N] [--owner @X]
             [--node V] [--package-manager PM] [--generator G] [--decide-by YYYY-MM-DD]
             [--today YYYY-MM-DD] [--force] [--json]
  declare.py --oss LEVEL --target TARGET --show      the resolution, nothing written
  declare.py --matrix                                every axis pair and its eight adapters

The two axes are `oss_level` (minimal, pragmatic, full) and `target` (vercel, cloudflare, fly,
hetzner, railway). Each port hangs on exactly one axis, so fifteen pairs resolve through
eighteen table rows. One override: `full` puts storage on the generic client everywhere. One
caveat: `full` on vercel or cloudflare cannot run three servers there, and the file says so.

The profile sets the ten bars. The file is written from templates/stack.yaml with every
placeholder substituted, and an existing file is never overwritten without --force.
Stdlib only. Exit 1 when the file exists and --force is missing, 2 on an unknown axis value.
"""
import argparse
import datetime as dt
import json
import os
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


TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "stack.yaml"
DECLARATION = "stack.yaml"
LEVELS = ("minimal", "pragmatic", "full")
TARGETS = ("vercel", "cloudflare", "fly", "hetzner", "railway")
PORTS = ("db", "storage", "jobs", "host", "auth", "mail", "analytics", "errors")
# The adapter table of references/ports.md in the router, held as data. Duplicated in the new and
# drift skills on purpose: each skill stays standalone, and a test compares the three copies.
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
# The one override and the one caveat. Both are what keeps fifteen pairs from being fifteen trees.
FULL_STORAGE = "s3"
NO_SERVER_TARGETS = ("vercel", "cloudflare")
CAVEAT = "mail, analytics and errors run on a host of their own; this target runs no server"
BARS = ("coverage_lines", "coverage_branches", "max_function_lines", "max_file_lines",
        "max_complexity", "max_params", "dead_exports_max", "dead_files_max", "dead_deps_max",
        "gate_max_seconds")
PROFILES = {
    "strict": (80, 70, 40, 300, 8, 3, 0, 0, 0, 60),
    "standard": (70, 60, 60, 400, 10, 4, 0, 0, 0, 90),
    "lenient": (50, 40, 80, 600, 15, 5, 0, 0, 0, 120),
}
DECIDE_DAYS = 90


def resolve(level, target):
    """The eight adapters for one axis pair, and the caveat when the pair carries one."""
    if level not in LEVELS:
        sys.exit(f"not an oss level: {level!r}, one of {', '.join(LEVELS)}")
    if target not in TARGETS:
        sys.exit(f"not a target: {target!r}, one of {', '.join(TARGETS)}")
    ports = {}
    for port in PORTS:
        ports[port] = BY_TARGET[port][target] if port in BY_TARGET else BY_LEVEL[port][level]
    if level == "full":
        ports["storage"] = FULL_STORAGE
    caveat = CAVEAT if level == "full" and target in NO_SERVER_TARGETS else ""
    return ports, caveat


def matrix():
    """Every axis pair with its eight adapters, one line each."""
    out = []
    for level in LEVELS:
        for target in TARGETS:
            ports, caveat = resolve(level, target)
            line = f"{level} {target}  " + " ".join(f"{p}={ports[p]}" for p in PORTS)
            out.append(line + (f"  caveat: {caveat}" if caveat else ""))
    return out


def render(subs):
    """The template with every placeholder replaced. A placeholder left over is a bug, not data."""
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, v in subs.items():
        text = text.replace("{{%s}}" % key, str(v))
    if "{{" in text:
        left = sorted({t.split("}}")[0] for t in text.split("{{")[1:]})
        sys.exit(f"the template still carries a placeholder: {', '.join(left)}")
    return text


def substitutions(a, ports, caveat, today):
    bars = PROFILES[a.profile]
    subs = {"NAME": a.name, "DECLARED": today.isoformat(), "OSS_LEVEL": a.oss, "TARGET": a.target,
            "OSS_CAVEAT": caveat, "NODE": a.node, "PACKAGE_MANAGER": a.package_manager,
            "GENERATOR": a.generator, "DECIDE_BY": a.decide_by}
    for port in PORTS:
        subs[port.upper()] = ports[port]
    for bar, n in zip(BARS, bars):
        subs[bar.upper()] = n
    return subs


def show(a, ports, caveat):
    out = [paint(f"declare  {a.oss} {a.target}  profile {a.profile}", "head")]
    width = max(len(p) for p in PORTS)
    out += [f"  {paint(p.ljust(width), 'dim')}  {ports[p]}" for p in PORTS]
    if caveat:
        out.append(paint("caveat", "WARN") + f"  {caveat}")
    bars = PROFILES[a.profile]
    out.append("bars  " + " · ".join(f"{b} {n}" for b, n in zip(BARS, bars)))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repository the declaration is written into")
    ap.add_argument("--oss", default="", metavar="LEVEL", help=", ".join(LEVELS))
    ap.add_argument("--target", default="", help=", ".join(TARGETS))
    ap.add_argument("--profile", default="standard", choices=sorted(PROFILES),
                    help="the bars; default standard")
    ap.add_argument("--name", default="", help="the project name; default the root directory's name")
    ap.add_argument("--owner", default="@OWNER", help="the owner CODEOWNERS starts with")
    ap.add_argument("--node", default="22", help="the runtime major the declaration pins")
    ap.add_argument("--package-manager", default="pnpm@10.17.1", metavar="PM")
    ap.add_argument("--generator", default="create-next-app")
    ap.add_argument("--decide-by", default="", metavar="YYYY-MM-DD",
                    help="the date the open decisions are taken by; default today plus 90 days")
    ap.add_argument("--today", default=None, metavar="YYYY-MM-DD", help="for tests")
    ap.add_argument("--force", action="store_true", help="overwrite an existing declaration")
    ap.add_argument("--show", action="store_true", help="print the resolution, write nothing")
    ap.add_argument("--matrix", action="store_true", help="every axis pair and its adapters")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.matrix:
        print("\n".join(matrix()))
        return 0
    if not a.oss or not a.target:
        ap.error("--oss and --target are both needed")
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    a.decide_by = a.decide_by or (today + dt.timedelta(days=DECIDE_DAYS)).isoformat()
    dt.date.fromisoformat(a.decide_by)          # a date that is not a date fails here, not later
    root = Path(a.root).expanduser()
    a.name = a.name or root.resolve().name
    ports, caveat = resolve(a.oss, a.target)
    if a.show:
        print(json.dumps({"oss_level": a.oss, "target": a.target, "profile": a.profile,
                          "ports": ports, "caveat": caveat,
                          "bars": dict(zip(BARS, PROFILES[a.profile]))}, indent=2)
              if a.json else show(a, ports, caveat))
        return 0
    path = root / DECLARATION
    if path.exists() and not a.force:
        print(f"{path} exists; --force overwrites it, and that is a review of a contract file")
        return 1
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(render(substitutions(a, ports, caveat, today)), encoding="utf-8")
    if a.json:
        print(json.dumps({"written": str(path), "oss_level": a.oss, "target": a.target,
                          "profile": a.profile, "ports": ports, "caveat": caveat}, indent=2))
    else:
        print(paint("written", "PASS") + f" {path}")
        print(show(a, ports, caveat))
    return 0


if __name__ == "__main__":
    sys.exit(main())
