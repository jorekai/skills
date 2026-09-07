#!/usr/bin/env python3
"""Scaffold and inspect the developer experience workspace.

Usage:
  scaffold.py [--root ~/dx] [MACHINE ...]   create folders and files; never overwrites
  scaffold.py [--root ~/dx] --check         list missing files, directories and template sections
  scaffold.py [--root ~/dx] --migrate-log   move week files from log/ down into log/dx/
  scaffold.py [--root ~/dx] --log           print this week's log path (created if missing), the next action id, and its commit trailer
  scaffold.py [--root ~/dx] --due           print actions whose verify-after date has passed
  scaffold.py [--root ~/dx] --append-row --check-id ID --target T --action A --class C
                              --then "N unit" [--status applied]
                                            add one action row to this week's log and print its id

MACHINE defaults to this machine's host name. Stdlib only.
Exit code 1 only when --check finds something missing.
"""
import os
import argparse
import datetime as dt
import platform
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
# One log folder per theme under a shared machine folder (decisions/0015). Two themes measure
# the same host, and a flat log/ would put two appenders into one week file.
THEME = "dx"
ROOT_FILES = {"config.md": "config.md", "standards.md": "standards.md"}
MACHINE_FILES = {"config.md": "machine-config.md"}
DIRS = ["audits", f"log/{THEME}", "proposals"]
ID_RE = re.compile(r"\b(\d{4}-W\d{2})-(\d{2})\b")
CHECK_RE = re.compile(r"[a-z]+\.[a-z][a-z-]*")
CLASSES = ("safe", "confirm", "ask")
# The closed set of units a measure may carry, with what one of them is worth in the base unit of
# its family. A measure counts what a finding costs, so lower is better and zero means the check no
# longer fires. Duplicated in grade/scripts/grade.py on purpose: each skill stays standalone.
UNITS = {"B": ("bytes", 1), "KB": ("bytes", 1024), "MB": ("bytes", 1024 ** 2),
         "GB": ("bytes", 1024 ** 3), "TB": ("bytes", 1024 ** 4), "bytes": ("bytes", 1),
         "count": ("count", 1), "percent": ("percent", 1), "seconds": ("seconds", 1)}
MEASURE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$")
KEY_RE = re.compile(r"^-\s*([A-Za-z_]+):\s*(.*)$")
# Host names, lower case, dots allowed for a fully qualified name. Every folder below is named
# after this value, so "..", "." and a name with a separator in it never become a path segment.
MACHINE_RE = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?")


def machine_name(raw=None):
    # Only a missing argument falls back to this machine. An empty string is a typo, not a default.
    name = (platform.node() or "unknown") if raw is None else raw
    name = name.strip().lower().replace(" ", "-")
    if not MACHINE_RE.fullmatch(name):
        sys.exit(f"not a machine name: {raw!r}")
    return name


def render(name, **subs):
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    for k, v in subs.items():
        text = text.replace("{{%s}}" % k, v)
    return text


def machines(root):
    base = root / "machines"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "config.md").exists())


def create(root, machine):
    root.mkdir(parents=True, exist_ok=True)
    for target, tpl in ROOT_FILES.items():
        p = root / target
        if p.exists():
            print(paint("exists", "dim") + f"  {p}")
        else:
            p.write_text(render(tpl), encoding="utf-8")
            print(paint("created", "PASS") + f" {p}")
    base = root / "machines" / machine
    for d in DIRS:
        if not (base / d).is_dir():
            print(paint("created", "PASS") + f" {base / d}/")
        (base / d).mkdir(parents=True, exist_ok=True)
        keep = base / d / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")   # git does not track empty directories
    for target, tpl in MACHINE_FILES.items():
        p = base / target
        if p.exists():
            print(paint("exists", "dim") + f"  {p}")
        else:
            p.write_text(render(tpl, MACHINE=machine), encoding="utf-8")
            print(paint("created", "PASS") + f" {p}")


def filled(root, machine):
    """Whether the machine's config differs from its template, so someone edited it."""
    p = root / "machines" / machine / "config.md"
    if not p.exists():
        return "missing"
    return "filled" if p.read_text(encoding="utf-8") != render("machine-config.md", MACHINE=machine) else "template"


def update_readme(root):
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(render("workspace-README.md"), encoding="utf-8")
        print(paint("created", "PASS") + f" {readme}")
    text = readme.read_text(encoding="utf-8")
    rows = ["| Machine | Folder | Config |", "|---|---|---|"]
    rows += [f"| {m} | `machines/{m}/` | {filled(root, m)} |" for m in machines(root)]
    table = "\n".join(rows)
    new = re.sub(r"<!-- machines:start -->.*?<!-- machines:end -->",
                 "<!-- machines:start -->\n" + table + "\n<!-- machines:end -->", text, flags=re.S)
    if new != text:
        readme.write_text(new, encoding="utf-8")
        print(paint("updated", "PASS") + f" {readme} (machine table)")


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
    for f, tpl in ROOT_FILES.items():
        p = root / f
        if not p.exists():
            missing.append(p)
        else:
            have = headings(p.read_text(encoding="utf-8"))
            stale += [(p, h) for h in headings(render(tpl)) if h not in have]
    found = machines(root)
    if not found:
        missing.append(root / "machines" / "<hostname>" / "config.md")
    for m in found:
        base = root / "machines" / m
        for f in stray_logs(root, m):
            stale.append((f, "at the old flat path, run --migrate-log"))
        for f, tpl in MACHINE_FILES.items():
            p = base / f
            if not p.exists():
                missing.append(p)
                continue
            have = headings(p.read_text(encoding="utf-8"))
            stale += [(p, h) for h in headings(render(tpl, MACHINE=m)) if h not in have]
        for d in DIRS:
            if not (base / d).is_dir():
                missing.append(base / d)
    for m in missing:
        print(paint("missing", "WARN") + f" {m}")
    for f, h in stale:
        print(paint("section missing", "WARN") + f" {f}: {h}")
    total = len(missing) + len(stale)
    print("ok" if not total else f"{total} missing")
    return 1 if total else 0


def value(path, key):
    """Value of `- key: ...` in a workspace file; blank when empty or still the template's hint.
    Duplicated in and-now/scripts/status.py on purpose: each skill stays standalone."""
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        m = KEY_RE.match(line.strip())
        if m and m.group(1).lower() == key.lower():
            v = m.group(2).strip()
            return "" if not v or v.startswith("(") else v
    return ""


def flags(root, machine):
    """The arguments each measuring script takes, built from config.md and standards.md.

    A step that retypes these numbers gets them wrong or leaves them out, and then the script
    measures against its own defaults instead of against the standard. A blank value is left out
    on purpose: it turns that check off, which is an answer.
    """
    cfg, std = root / "config.md", root / "standards.md"
    mcfg = root / "machines" / machine / "config.md"

    def pick(key, *sources):
        for s in sources:
            v = value(s, key)
            if v:
                return v
        return ""

    def add(out, flag, v):
        if v:
            out.append(f"{flag} {v}")

    roots = pick("project_roots", mcfg)
    index = pick("projects_index", mcfg)
    print(f"paths: {roots or '(project_roots is blank in ' + str(mcfg) + ')'}")
    if index:
        print(f"index: {index}")

    repos = []
    add(repos, "--depth", pick("scan_max_depth", mcfg))
    add(repos, "--stale-days", pick("branch_stale_days", std))
    add(repos, "--stash-days", pick("stash_stale_days", std))
    add(repos, "--expect-email", pick("git_email", cfg))
    print("repos: " + (" ".join(repos) or "(no standard set, the script uses its own defaults)"))

    mach = []
    add(mach, "--min-free-gb", pick("disk_free_min_gb", mcfg, std))
    add(mach, "--runtime", pick("container_runtime", mcfg))
    print("machine: " + (" ".join(mach) or "(no standard set, the script uses its own defaults)"))

    fric = []
    for key in ("shell_history", "extra_history"):
        for one in (v.strip() for v in pick(key, mcfg).split(",")):
            add(fric, "--history", one)
    add(fric, "--db", pick("shell_history_db", mcfg))
    add(fric, "--sessions", pick("agent_sessions", mcfg))
    add(fric, "--slow-seconds", pick("slow_command_seconds", std))
    print("friction: " + (" ".join(fric) or "(no history source is recorded for this machine)"))

    verify = pick("verify_window_days", std)
    print(f"verify after: {verify} days" if verify else
          "verify after: (verify_window_days is blank, so no row can be graded)")


def week_bounds(day):
    year, week, wd = day.isocalendar()
    start = day - dt.timedelta(days=wd - 1)
    return f"{year}-W{week:02d}", start, start + dt.timedelta(days=6)


def log_dir(root, machine):
    """This theme's log folder inside the shared machine folder (decisions/0015)."""
    return root / "machines" / machine / "log" / THEME


def migrate_log(root, machine):
    """Move week files written under the old flat log/ into log/<theme>/. Never overwrites."""
    old = root / "machines" / machine / "log"
    new = log_dir(root, machine)
    moved = 0
    for f in sorted(old.glob("*.md")) if old.is_dir() else []:
        new.mkdir(parents=True, exist_ok=True)
        target = new / f.name
        if target.exists():
            print(paint("exists", "dim") + f"  {target}, left {f} in place")
            continue
        f.rename(target)
        print(f"moved   {f} to {target}")
        moved += 1
    print("nothing to move" if not moved else f"{moved} week file(s) moved")


def stray_logs(root, machine):
    """Week files still sitting in the old flat log/. They are invisible to every reader."""
    old = root / "machines" / machine / "log"
    return sorted(old.glob("*.md")) if old.is_dir() else []


def week_log(root, machine, today):
    """This week's log file, created from the template when it does not exist yet."""
    week, start, end = week_bounds(today)
    logdir = log_dir(root, machine)
    logdir.mkdir(parents=True, exist_ok=True)
    p = logdir / f"{week}.md"
    if not p.exists():
        p.write_text(render("log-week.md", WEEK=week, START=start.isoformat(),
                            END=end.isoformat(), MACHINE=machine), encoding="utf-8")
    return p, week


def next_id(logdir, week):
    """The next free action id in this week, read from every log file so none is reused."""
    used = [int(n) for f in logdir.glob("*.md")
            for w, n in ID_RE.findall(f.read_text(encoding="utf-8")) if w == week]
    return f"{week}-{(max(used) + 1) if used else 1:02d}"


def log(root, machine, today):
    p, week = week_log(root, machine, today)
    nid = next_id(p.parent, week)
    print(f"log: {p}")
    print(f"next id: {nid}")
    # The commit that carries out the action ends with this line, so `git log --grep` finds it later.
    print(f"commit trailer: DX-Log: {nid}")


def parse_measure(text):
    """`40 GB` as (40.0, "GB"); None when the number or the unit is not one a script recomputes.

    Duplicated in grade/scripts/grade.py on purpose: each skill stays standalone."""
    m = MEASURE_RE.match(text or "")
    if not m or m.group(2) not in UNITS:
        return None
    return float(m.group(1)), m.group(2)


def escape(text):
    """One table cell: a pipe inside it is escaped, and a line break would end the row."""
    return " ".join(str(text).split()).replace("|", "\\|")


def insert_row(text, heading, cells):
    """Add one row at the end of the first table under `heading`, in that table's column order."""
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        sys.exit(f"no section {heading} in the log file")
    head = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("|")), None)
    if head is None:
        sys.exit(f"no table under {heading} in the log file")
    columns = [c.strip().lower() for c in split_cells(lines[head])]
    unknown = [k for k in cells if k not in columns]
    if unknown:
        sys.exit(f"the table under {heading} has no column(s): {', '.join(unknown)}")
    end = head
    while end + 1 < len(lines) and lines[end + 1].strip().startswith("|"):
        end += 1
    row = "| " + " | ".join(escape(cells.get(c, "")) for c in columns) + " |"
    lines.insert(end + 1, row)
    return "\n".join(lines) + "\n", row


def append_row(root, machine, today, a):
    """Write one action row. Every field is named, so a miscounted column cannot happen."""
    if not CHECK_RE.fullmatch(a.check_id or ""):
        sys.exit(f"not a check id: {a.check_id!r}")
    if a.klass not in CLASSES:
        sys.exit(f"not a risk class: {a.klass!r}, one of {', '.join(CLASSES)}")
    measure = parse_measure(a.then)
    if not measure:
        sys.exit(f"not a measure: {a.then!r}. A number and one of {', '.join(sorted(UNITS))}")
    if not a.action:
        sys.exit("an action needs a sentence saying what happens")
    # A date without the status is a row nobody grades, so the date decides the status.
    status = "applied" if a.applied else a.status
    applied = a.applied or (today.isoformat() if status == "applied" else "")
    verify = ""
    if applied:
        days = a.verify_days if a.verify_days is not None else \
            (int(value(root / "standards.md", "verify_window_days") or 0) or None)
        if not days:
            sys.exit("no verify window: set verify_window_days in standards.md or pass --verify-days")
        verify = (dt.date.fromisoformat(applied) + dt.timedelta(days=days)).isoformat()
    p, week = week_log(root, machine, today)
    nid = next_id(p.parent, week)
    value_, unit = measure
    text, row = insert_row(p.read_text(encoding="utf-8"), "## Actions",
                           {"id": nid, "check": a.check_id, "target": a.target, "action": a.action,
                            "class": a.klass, "then": f"{value_:g} {unit}", "status": status,
                            "applied": applied, "verify after": verify})
    p.write_text(text, encoding="utf-8")
    print(f"log: {p}")
    print(f"id: {nid}")
    print(row)
    print(f"commit trailer: DX-Log: {nid}")
    if verify:
        print(f"verify after: {verify}")


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


def due(root, machine, today):
    found = 0
    for f in sorted(log_dir(root, machine).glob("*.md")):
        for r in table_rows(f.read_text(encoding="utf-8"), "## Actions"):
            after = r.get("verify after", "")
            if r.get("status", "") in ("applied", "verify") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", after) \
                    and dt.date.fromisoformat(after) <= today:
                found += 1
                # Then is the value the verdict is measured from: printing the row without it
                # means opening the file again before anything can be graded.
                print(f"{r.get('id')} | {r.get('check')} | {r.get('target')} | {r.get('action')} | "
                      f"class {r.get('class')} | then {r.get('then')} | applied {r.get('applied')} | "
                      f"verify after {after} | {f.name}")
    print("nothing due" if not found else f"{found} due")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("machines", nargs="*")
    ap.add_argument("--root", default="~/dx")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--migrate-log", action="store_true",
                    help="move week files from log/ into log/%s/ (decisions/0015)" % THEME)
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--flags", action="store_true")
    ap.add_argument("--append-row", action="store_true", help="add one action row to this week's log")
    ap.add_argument("--check-id", default="", metavar="ID", help="the check id the action closes")
    ap.add_argument("--target", default="", help="the repository, path, or shape the action is about")
    ap.add_argument("--action", default="", help="what happens, in one sentence")
    ap.add_argument("--class", dest="klass", default="", metavar="CLASS",
                    help="the risk class from the fixes table: " + ", ".join(CLASSES))
    ap.add_argument("--then", default="", metavar="MEASURE",
                    help="the measure before the action, a number and a unit: " + ", ".join(sorted(UNITS)))
    ap.add_argument("--status", default="todo", choices=("todo", "applied"),
                    help="applied sets today as the applied date and computes the verify date")
    ap.add_argument("--applied", default="", metavar="YYYY-MM-DD")
    ap.add_argument("--verify-days", type=int, default=None,
                    help="days until the verdict; without it standards.md decides")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    if a.check:
        sys.exit(check(root))
    names = [machine_name(m) for m in a.machines] or [machine_name()]
    if a.migrate_log:
        for m in names:
            migrate_log(root, m)
        return
    if a.flags:
        for m in names:
            flags(root, m)
        return
    if a.append_row:
        for m in names:
            append_row(root, m, today, a)
        return
    if a.log or a.due:
        for m in names:
            (log if a.log else due)(root, m, today)
        return
    for m in names:
        create(root, m)
    update_readme(root)


if __name__ == "__main__":
    main()
