#!/usr/bin/env python3
"""Scaffold and inspect the SEO workspace (docs/seo/<domain>/).

Usage:
  scaffold.py [--root docs/seo] DOMAIN [DOMAIN ...]   create folders and files; never overwrites
  scaffold.py [--root docs/seo] --check               list missing files, directories and template sections
  scaffold.py [--root docs/seo] DOMAIN --log          print this week's log path (created if missing), the next action id, and its commit trailer
  scaffold.py [--root docs/seo] DOMAIN --due          print actions whose verify-after date has passed

Stdlib only. Exit code 1 only when --check finds missing files.
"""
import os
import argparse
import datetime as dt
import re
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
FILES = {"config.md": "config.md", "connections.md": "connections.md",
         "strategy.md": "strategy.md", "glossary.md": "glossary.md"}
DIRS = ["log", "briefs", "drafts", "exports", "audits", "reports"]
ID_RE = re.compile(r"\b(\d{4}-W\d{2})-(\d{2})\b")
LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
HOST_RE = re.compile(rf"{LABEL}(?:\.{LABEL})+")


def host(domain):
    d = domain.strip().lower()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    # Two labels or more, letters, digits and hyphens only. Every folder below is named after
    # this value, so "..", "." and a name with a separator in it never become a path segment.
    if not HOST_RE.fullmatch(d):
        sys.exit(f"not a host name: {domain!r}")
    return d


def render(name, **subs):
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    for k, v in subs.items():
        text = text.replace("{{%s}}" % k, v)
    return text


def create(root, domain):
    base = root / domain
    for d in DIRS:
        if not (base / d).is_dir():
            print(paint("created", "PASS") + f" {base / d}/")
        (base / d).mkdir(parents=True, exist_ok=True)
        keep = base / d / ".gitkeep"
        if d != "exports" and not keep.exists():
            keep.write_text("", encoding="utf-8")   # git does not track empty directories
    gi = base / "exports" / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n!.gitignore\n", encoding="utf-8")
        print(paint("created", "PASS") + f" {gi}")
    for target, tpl in FILES.items():
        p = base / target
        if p.exists():
            print(paint("exists", "dim") + f"  {p}")
        else:
            p.write_text(render(tpl, DOMAIN=domain), encoding="utf-8")
            print(paint("created", "PASS") + f" {p}")


def filled(root, domain):
    """Which of the four files differ from their template (edited by someone)."""
    out = []
    for target, tpl in FILES.items():
        p = root / domain / target
        if p.exists() and p.read_text(encoding="utf-8") != render(tpl, DOMAIN=domain):
            out.append(target.replace(".md", ""))
    return ", ".join(out) or "nothing yet"


def update_readme(root):
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(render("workspace-README.md"), encoding="utf-8")
        print(paint("created", "PASS") + f" {readme}")
    text = readme.read_text(encoding="utf-8")
    domains = sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "config.md").exists())
    rows = ["| Domain | Folder | Filled |", "|---|---|---|"]
    rows += [f"| {d} | `{d}/` | {filled(root, d)} |" for d in domains]
    table = "\n".join(rows)
    new = re.sub(r"<!-- domains:start -->.*?<!-- domains:end -->",
                 "<!-- domains:start -->\n" + table + "\n<!-- domains:end -->", text, flags=re.S)
    if new != text:
        readme.write_text(new, encoding="utf-8")
        print(paint("updated", "PASS") + f" {readme} (domain table)")


def headings(text):
    return [l.strip() for l in text.splitlines() if l.startswith("## ")]


def check(root):
    """Missing files and directories, plus a heading a template has and the workspace file lacks.

    A template gains a section between releases; the file scaffolded before it never does, because
    create() never overwrites. Without this the gap is silent and the skill that reads the section
    finds nothing.
    """
    missing, stale = [], []
    if not (root / "README.md").exists():
        missing.append(root / "README.md")
    for p in sorted(root.iterdir()) if root.exists() else []:
        if not p.is_dir():
            continue
        for f, tpl in FILES.items():
            if not (p / f).exists():
                missing.append(p / f)
                continue
            have = headings((p / f).read_text(encoding="utf-8"))
            stale += [(p / f, h) for h in headings(render(tpl, DOMAIN=p.name)) if h not in have]
        for d in DIRS:
            if not (p / d).is_dir():
                missing.append(p / d)
    for m in missing:
        print(paint("missing", "WARN") + f" {m}")
    for f, h in stale:
        print(paint("section missing", "WARN") + f" {f}: {h}")
    total = len(missing) + len(stale)
    print("ok" if not total else f"{total} missing")
    return 1 if total else 0


def week_bounds(day):
    year, week, wd = day.isocalendar()
    start = day - dt.timedelta(days=wd - 1)
    return f"{year}-W{week:02d}", start, start + dt.timedelta(days=6)


def log(root, domain, today):
    week, start, end = week_bounds(today)
    logdir = root / domain / "log"
    logdir.mkdir(parents=True, exist_ok=True)
    p = logdir / f"{week}.md"
    if not p.exists():
        p.write_text(render("log-week.md", WEEK=week, START=start.isoformat(), END=end.isoformat()),
                     encoding="utf-8")
    used = [int(n) for f in logdir.glob("*.md") for w, n in ID_RE.findall(f.read_text(encoding="utf-8")) if w == week]
    nid = f"{week}-{(max(used) + 1) if used else 1:02d}"
    print(f"log: {p}")
    print(f"next id: {nid}")
    # The commit that carries out the action ends with this line, so `git log --grep` finds it later.
    print(f"commit trailer: SEO-Log: {nid}")


def split_cells(line):
    """Markdown table cells; `\\|` inside a cell is an escaped pipe, not a separator.
    Duplicated in and-now/scripts/status.py on purpose: each skill stays standalone."""
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table_rows(text, heading):
    """Rows of the first markdown table after `heading`, as dicts keyed by header."""
    if heading not in text:
        return []
    section = text.split(heading, 1)[1]
    lines = [l for l in section.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    head = [c.strip().lower() for c in split_cells(lines[0])]
    rows = []
    for line in lines[2:]:
        cells = split_cells(line)
        if len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    return rows


def due(root, domain, today):
    found = 0
    for f in sorted((root / domain / "log").glob("*.md")):
        for r in table_rows(f.read_text(encoding="utf-8"), "## Actions"):
            status = r.get("status", "")
            after = r.get("verify after", "")
            if status in ("applied", "verify") and re.match(r"\d{4}-\d{2}-\d{2}$", after) \
                    and dt.date.fromisoformat(after) <= today:
                found += 1
                # Then is the starting value the verdict is measured from: printing the row without
                # it means opening the file again before anything can be graded.
                print(f"{r.get('id')} | {r.get('bucket')} | {r.get('url')} | {r.get('query')} | "
                      f"{r.get('action')} | then {r.get('then')} | applied {r.get('applied')} | "
                      f"verify after {after} | {f.name}")
    print("nothing due" if not found else f"{found} due")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("domains", nargs="*")
    ap.add_argument("--root", default="docs/seo")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args()
    root = Path(a.root)
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    if a.check:
        sys.exit(check(root))
    if not a.domains:
        ap.error("give at least one domain, or --check")
    domains = [host(d) for d in a.domains]
    if a.log or a.due:
        for d in domains:
            (log if a.log else due)(root, d, today)
        return
    root.mkdir(parents=True, exist_ok=True)
    for d in domains:
        create(root, d)
    update_readme(root)


if __name__ == "__main__":
    main()
