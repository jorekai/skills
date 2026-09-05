#!/usr/bin/env python3
"""Where a machine stands in the developer experience loop, read from the workspace alone.

Usage:
  status.py [--root ~/dx] [MACHINE ...] [--today YYYY-MM-DD]

No argument: every machine folder under <root>/machines. Reads config.md, standards.md, the
machine's config, the newest audits/*.json, the log tables, and proposals/. Never touches the
machine itself and never the network.
Stdlib only. Exit code 2 when the workspace or a named machine folder does not exist.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^-\s*([A-Za-z_]+):\s*(.*)$")
AUDIT_MAX_AGE = 30          # days; a measurement older than this describes a machine that moved on


def week_of(day):
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def value(text, key):
    """Value of `- key: ...`; blank when empty or still the template's parenthesised hint."""
    for line in text.splitlines():
        m = KEY_RE.match(line.strip())
        if m and m.group(1).lower() == key.lower():
            v = m.group(2).strip()
            return "" if not v or v.startswith("(") else v
    return ""


def any_value(path):
    """A config counts as filled once at least one key has a value beyond the template's hint."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    keys = [m.group(1) for m in (KEY_RE.match(l.strip()) for l in text.splitlines()) if m]
    return any(value(text, k) for k in keys)


def split_cells(line):
    """Markdown table cells; `\\|` inside a cell is an escaped pipe, not a separator.
    Duplicated from setup/scripts/scaffold.py on purpose: each skill stays standalone."""
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table_rows(text, heading):
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


def plural(n, word):
    """"1 day", "2 days"."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def file_date(p):
    m = DATE_RE.search(p.name)
    return dt.date.fromisoformat(m.group(1)) if m else dt.date.fromtimestamp(p.stat().st_mtime)


def latest(paths):
    paths = list(paths)
    return max(paths, key=lambda p: (file_date(p), p.name)) if paths else None


def read_machine(root, machine, today):
    base = root / "machines" / machine
    s = {"machine": machine}
    s["config"] = any_value(root / "config.md")
    s["standards"] = any_value(root / "standards.md")
    s["machine_config"] = any_value(base / "config.md")

    audits = [p for p in (base / "audits").glob("*.json") if p.is_file()] if (base / "audits").is_dir() else []
    newest = latest(audits)
    s["audit"] = None
    if newest:
        entry = {"file": newest.name, "age": (today - file_date(newest)).days,
                 "fail": None, "warn": None, "fail_ids": []}
        try:
            data = json.loads(newest.read_text(encoding="utf-8"))
            counts = data.get("counts", {})
            entry["fail"] = int(counts.get("FAIL", 0))
            entry["warn"] = int(counts.get("WARN", 0))
            entry["fail_ids"] = sorted({i.get("id", "?") for i in data.get("items", []) if i.get("level") == "FAIL"})
        except (ValueError, AttributeError, TypeError):
            pass
        s["audit"] = entry

    rows = []
    for f in sorted((base / "log").glob("*.md")) if (base / "log").is_dir() else []:
        for r in table_rows(f.read_text(encoding="utf-8"), "## Actions"):
            r["_file"] = f.name
            rows.append(r)
    s["rows"] = rows
    s["todo"] = [r for r in rows if r.get("status") == "todo"]
    s["due"] = [r for r in rows if r.get("status") in ("applied", "verify")
                and ISO_DATE.match(r.get("verify after", ""))
                and dt.date.fromisoformat(r["verify after"]) <= today]
    future = [dt.date.fromisoformat(r["verify after"]) for r in rows
              if r.get("status") in ("applied", "verify") and ISO_DATE.match(r.get("verify after", ""))
              and dt.date.fromisoformat(r["verify after"]) > today]
    s["next_verify"] = min(future) if future else None
    s["proposals"] = sorted(p.stem for p in (base / "proposals").glob("*.md")) if (base / "proposals").is_dir() else []
    return s


def decide(s, today):
    """Stage and the ordered list of next steps. Every step names what to run or what to write."""
    now, then = [], []
    if not s["config"] and not s["machine_config"]:
        return "setup", ["`jorekai-dx:setup`: the workspace is still the template, fill config.md and the machine's config.md"], then

    # Unfinished setup is an item, never a gate: a machine with a log or an audit is in the loop,
    # and hiding its open work behind the interview is how a workspace stalls unseen.
    setup_open = []
    if not s["standards"]:
        setup_open.append("`jorekai-dx:setup`: standards.md is still the template, so every check that measures against it is off")
    if not s["machine_config"]:
        setup_open.append("`jorekai-dx:setup`: this machine's config.md is still the template, so nothing knows where its projects and history live")
    if not s["config"]:
        setup_open.append("`jorekai-dx:setup`: config.md is still the template, so identity and the defaults a new machine inherits are unknown")

    started = bool(s["audit"] or s["rows"] or s["proposals"])
    if setup_open and not started:
        return "setup", setup_open, then

    stage = "loop"
    # A verdict is what makes the log learn, so a row past its verify date outranks everything else.
    if s["due"]:
        ids = ", ".join(r.get("id", "?") for r in s["due"][:3])
        now.append(f"grade {len(s['due'])} row(s) past their verify date ({ids}): recompute the measure, "
                   "write Now and the verdict in the outcomes table, and set Status")
    a = s["audit"]
    if a is None:
        stage = "measure"
        now.append("no audit on this machine yet: run a measuring skill and save its JSON to audits/YYYY-MM-DD-<kind>.json")
    elif a["fail"]:
        stage = "measure"
        now.append(f"{a['file']} still reports {a['fail']} FAIL ({', '.join(a['fail_ids'][:4])}): "
                   "fix them in the priority ladder's order, one log row per check id")
    elif a["age"] > AUDIT_MAX_AGE:
        now.append(f"the newest audit is {plural(a['age'], 'day')} old: measure again before acting on it")

    for r in s["todo"]:
        now.append(f"open row {r.get('id', '?')} ({r.get('check', '?')} on {r.get('target', '?')}): "
                   f"{r.get('action', '?')}, then set Status, Applied, and Verify after")
    for slug in s["proposals"]:
        now.append(f"proposals/{slug}.md waits for a decision: give it a measure and it becomes a log row, or drop it")
    now += setup_open
    if not now:
        now.append("nothing open: measure again when the newest audit ages out")
    if s["next_verify"]:
        then.append(f"{s['next_verify'].isoformat()}: first verify date reached, grade the row it belongs to")
    return stage, now, then


def report(s, today):
    out = [f"# {s['machine']}, {today.isoformat()} ({week_of(today)})", ""]
    out.append("setup        config " + ("filled" if s["config"] else "TEMPLATE")
               + " | standards " + ("filled" if s["standards"] else "TEMPLATE")
               + " | machine config " + ("filled" if s["machine_config"] else "TEMPLATE"))
    a = s["audit"]
    out.append("audits       " + (f"{a['file']} ({plural(a['age'], 'day')} old): FAIL {a['fail']}, WARN {a['warn']}"
                                  if a else "none"))
    by = {}
    for r in s["rows"]:
        by[r.get("status", "?")] = by.get(r.get("status", "?"), 0) + 1
    out.append(f"log          {len(s['rows'])} rows: " + (", ".join(f"{k} {v}" for k, v in sorted(by.items())) or "empty")
               + f" | due for verdict {len(s['due'])}"
               + (f" | next verify {s['next_verify'].isoformat()}" if s["next_verify"] else ""))
    out.append(f"proposals    {', '.join(s['proposals']) or 'none'}")
    stage, now, then = decide(s, today)
    out += ["", f"stage: {stage}", "now:"]
    out += [f"  {i}. {step}" for i, step in enumerate(now, 1)]
    if then:
        out += ["then:"] + [f"  - {t}" for t in then]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("machines", nargs="*")
    ap.add_argument("--root", default="~/dx")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    for m in a.machines:      # a folder name, never a path: keep the report inside --root
        if "/" in m or m.startswith("."):
            sys.exit(f"not a machine folder name: {m!r}")
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    base = root / "machines"
    if not base.is_dir():
        print(f"no workspace at {root}: run `jorekai-dx:setup` first")
        sys.exit(2)
    found = a.machines or sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "config.md").exists())
    if not found:
        print(f"no machine folder under {base}: run `jorekai-dx:setup` first")
        sys.exit(2)
    reports = []
    for m in found:
        if not (base / m).is_dir():
            print(f"no folder {base / m}: run `jorekai-dx:setup {m}` first")
            sys.exit(2)
        reports.append(report(read_machine(root, m, today), today))
    print("\n\n".join(reports))


if __name__ == "__main__":
    main()
