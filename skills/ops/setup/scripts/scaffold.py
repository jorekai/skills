#!/usr/bin/env python3
"""Scaffold and inspect the ops side of the machines workspace.

Usage:
  scaffold.py [--root ~/dx] [HOST ...]      create folders and files; never overwrites
  scaffold.py [--root ~/dx] --check         list missing files, directories and template sections
  scaffold.py [--root ~/dx] --flags         the arguments each measuring script takes
  scaffold.py [--root ~/dx] --log           this week's log path, the next action id, its trailer
  scaffold.py [--root ~/dx] --due           actions whose verify-after date has passed
  scaffold.py [--root ~/dx] --append-row --check-id ID --target T --action A --class C
                              --then "N unit" [--status applied]

The workspace is shared with jorekai-dx: one folder per host under machines/, one log folder per
theme (decisions/0015). This theme writes machines/<host>/log/ops/ and nothing else of dx's.

HOST defaults to this machine's host name. Stdlib only.
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
THEME = "ops"
ROOT_FILES = {"README.md": "workspace-README.md", "config.md": "config.md",
              "standards.md": "standards.md"}
HOST_FILES = {"config.md": "host-config.md"}
DIRS = ["audits", f"log/{THEME}", "proposals"]
ID_RE = re.compile(r"\b(\d{4}-W\d{2})-(\d{2})\b")
CHECK_RE = re.compile(r"[a-z]+\.[a-z][a-z-]*")
CLASSES = ("safe", "confirm", "ask")
# The closed set of units a measure may carry. A measure counts what a finding costs, so lower is
# better and zero means the check no longer fires (decisions/0014). Duplicated from the dx theme
# on purpose: each plugin stays standalone.
UNITS = {"B": ("bytes", 1), "KB": ("bytes", 1024), "MB": ("bytes", 1024 ** 2),
         "GB": ("bytes", 1024 ** 3), "TB": ("bytes", 1024 ** 4), "bytes": ("bytes", 1),
         "count": ("count", 1), "percent": ("percent", 1), "seconds": ("seconds", 1)}
MEASURE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$")
KEY_RE = re.compile(r"^-\s*([A-Za-z_]+):\s*(.*)$")
HINT_RE = re.compile(r"\s*\([^()]*\)\s*$")
# Host names, lower case, dots allowed for a fully qualified name. Every folder below is named
# after this value, so "..", "." and a name with a separator never become a path segment.
HOST_RE = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?")


def host_name(raw=None):
    """Only a missing argument falls back to this machine. An empty string is a typo."""
    name = (platform.node() or "unknown") if raw is None else raw
    name = name.strip().lower().replace(" ", "-")
    if not HOST_RE.fullmatch(name):
        sys.exit(f"not a host name: {raw!r}")
    return name


def render(name, **subs):
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    for k, v in subs.items():
        text = text.replace("{{%s}}" % k, v)
    return text


def hosts(root):
    base = root / "machines"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "config.md").exists())


def create(root, host):
    root.mkdir(parents=True, exist_ok=True)
    for target, tpl in ROOT_FILES.items():
        p = root / target
        if p.exists():
            print(paint("exists", "dim") + f"  {p}")
        else:
            p.write_text(render(tpl), encoding="utf-8")
            print(paint("created", "PASS") + f" {p}")
    base = root / "machines" / host
    for d in DIRS:
        if not (base / d).is_dir():
            print(paint("created", "PASS") + f" {base / d}/")
        (base / d).mkdir(parents=True, exist_ok=True)
        keep = base / d / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")   # git does not track empty directories
    for target, tpl in HOST_FILES.items():
        p = base / target
        if p.exists():
            print(paint("exists", "dim") + f"  {p}")
        else:
            p.write_text(render(tpl, HOST=host), encoding="utf-8")
            print(paint("created", "PASS") + f" {p}")


def headings(text):
    return [l.strip() for l in text.splitlines() if l.startswith("## ")]


def check(root):
    """Missing files and directories, plus a heading this theme's template has and a file lacks.

    The workspace is shared, so a file created by another theme holds that theme's sections only.
    Naming the missing heading is what turns a shared file into one both themes can read.
    """
    missing, stale = [], []
    for f, tpl in ROOT_FILES.items():
        p = root / f
        if not p.exists():
            missing.append(p)
        else:
            have = headings(p.read_text(encoding="utf-8"))
            stale += [(p, h) for h in headings(render(tpl)) if h not in have]
    found = hosts(root)
    if not found:
        missing.append(root / "machines" / "<hostname>" / "config.md")
    for h in found:
        base = root / "machines" / h
        if value(base / "config.md", "role") != "server":
            continue                       # a workstation is the dx theme's business, not this one
        for f, tpl in HOST_FILES.items():
            p = base / f
            if not p.exists():
                missing.append(p)
                continue
            have = headings(p.read_text(encoding="utf-8"))
            stale += [(p, hd) for hd in headings(render(tpl, HOST=h)) if hd not in have]
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

    A template line may carry a default and an explanation, `report: pull (what pull means)`. The
    trailing parenthesis is the explanation, so it is stripped; a line that is only a parenthesis
    is still a hint and reads blank, which turns its check off.
    """
    if not Path(path).exists():
        return ""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = KEY_RE.match(line.strip())
        if m and m.group(1).lower() == key.lower():
            v = HINT_RE.sub("", m.group(2).strip()).strip()
            return "" if not v or v.startswith("(") else v
    return ""


def values(path, key, sep=","):
    """A separated value as a list, empty when the key is blank.

    `services` uses a semicolon, because a service spec carries commas of its own. A comma there
    turned one service into four arguments that named nothing.
    """
    v = value(path, key)
    return [p.strip() for p in v.split(sep) if p.strip()] if v else []


PROVED = re.compile(r"^(?P<name>[^@]+)@(?P<date>\d{4}-\d{2}-\d{2})$")


def proved_paths(entries):
    """Ways in split into proved and unproved. `name@YYYY-MM-DD` is proved, a bare name is not.

    `access.single-path` decides whether anything may touch access at all, and it counts what it
    is given. An entry somebody typed is a belief; the date is the day a fresh connection answered
    on that path. Only the proved ones become `--path`, so the count is of paths and not of names.
    """
    proved, unproved = [], []
    for e in entries:
        m = PROVED.match(e)
        (proved.append(m.group("name").strip()) if m else unproved.append(e))
    return proved, unproved


def flags(root, host):
    """The arguments each measuring script takes, built from the workspace.

    A step that retypes these gets them wrong or leaves them out, and then the script measures
    against its own defaults instead of against the standard. A blank value is left out on
    purpose: it turns that check off, which is an answer.
    """
    std = root / "standards.md"
    cfg = root / "machines" / host / "config.md"

    def add(out, flag, v):
        if v:
            out.append(f"{flag} {v}")

    access_target = value(cfg, "access")
    print(f"access as: {access_target or '(access is blank in ' + str(cfg) + ')'}")
    print(f"control plane: {value(cfg, 'control_plane') or '(not detected yet)'}")
    print(f"report mode: {value(cfg, 'report') or 'pull'}")

    acc = []
    for user in values(cfg, "allow_users"):
        acc.append(f"--allow-user {user}")
    proved, unproved = proved_paths(values(cfg, "access_paths"))
    for path in proved:
        acc.append(f"--path {path}")
    if unproved:
        print("unproved ways in: " + ", ".join(unproved)
              + " (no date, so not counted; open a fresh connection and write `name@YYYY-MM-DD`)")
    add(acc, "--paths-bar", value(std, "access_paths_min"))
    add(acc, "--min-key-bits", value(std, "key_min_bits"))
    add(acc, "--key-rotation", value(std, "key_rotation_after"))
    add(acc, "--max-auth-tries", value(std, "ssh_max_auth_tries"))
    for cmd in values(std, "sudo_allowed_commands"):
        acc.append(f"--allow-sudo-command {cmd}")
    print("access: " + (" ".join(acc) or "(no standard set, the script uses its own defaults)"))

    av = []
    for spec in values(cfg, "services", sep=";"):
        av.append(f"--service {spec}")
    for opt in values(std, "unit_required_options"):
        av.append(f"--require-option {opt}")
    for pair in values(cfg, "unit_exceptions"):
        av.append(f"--except {pair}")
    add(av, "--restart-bar", value(std, "service_restart_bar"))
    print("availability: " + (" ".join(av) or "(no service is recorded for this host)"))

    verify = value(std, "verify_window_days")
    print(f"verify after: {verify} days" if verify else
          "verify after: (verify_window_days is blank, so no row can be graded)")
    print(f"allow safe: {value(std, 'allow_safe') or 'no'}")


def week_bounds(day):
    year, week, wd = day.isocalendar()
    start = day - dt.timedelta(days=wd - 1)
    return f"{year}-W{week:02d}", start, start + dt.timedelta(days=6)


def log_dir(root, host):
    """This theme's log folder inside the shared host folder (decisions/0015)."""
    return root / "machines" / host / "log" / THEME


def week_log(root, host, today):
    week, start, end = week_bounds(today)
    logdir = log_dir(root, host)
    logdir.mkdir(parents=True, exist_ok=True)
    p = logdir / f"{week}.md"
    if not p.exists():
        p.write_text(render("log-week.md", WEEK=week, START=start.isoformat(),
                            END=end.isoformat(), HOST=host), encoding="utf-8")
    return p, week


def next_id(logdir, week):
    """The next free action id in this week, read from every log file so none is reused."""
    used = [int(n) for f in logdir.glob("*.md")
            for w, n in ID_RE.findall(f.read_text(encoding="utf-8")) if w == week]
    return f"{week}-{(max(used) + 1) if used else 1:02d}"


def log(root, host, today):
    p, week = week_log(root, host, today)
    nid = next_id(p.parent, week)
    print(f"log: {p}")
    print(f"next id: {nid}")
    # The commit that carries out the action ends with this line, so `git log --grep` finds it.
    print(f"commit trailer: Ops-Log: {nid}")


def parse_measure(text):
    """`4 count` as (4.0, "count"); None when the number or the unit is not one a script recomputes."""
    m = MEASURE_RE.match(text or "")
    if not m or m.group(2) not in UNITS:
        return None
    return float(m.group(1)), m.group(2)


def escape(text):
    """One table cell: a pipe inside it is escaped, and a line break would end the row."""
    return " ".join(str(text).split()).replace("|", "\\|")


def split_cells(line):
    """Markdown table cells; `\\|` inside a cell is an escaped pipe, not a separator."""
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


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
    lines.insert(end + 1, "| " + " | ".join(escape(cells.get(c, "")) for c in columns) + " |")
    return "\n".join(lines) + "\n", lines[end + 1]


def append_row(root, host, today, a):
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
    klass = a.klass
    # `safe` is off until a host turns it on (decisions/0017): on a host that serves other people
    # nothing changes without a sentence saying so, and the row records the class that ran.
    if klass == "safe" and (value(root / "standards.md", "allow_safe") or "no").lower() != "yes":
        klass = "confirm"
        print("class safe is off for this workspace (allow_safe), the row runs as confirm")
    status = "applied" if a.applied else a.status
    applied = a.applied or (today.isoformat() if status == "applied" else "")
    verify = ""
    if applied:
        days = a.verify_days if a.verify_days is not None else \
            (int(value(root / "standards.md", "verify_window_days") or 0) or None)
        if not days:
            sys.exit("no verify window: set verify_window_days in standards.md or pass --verify-days")
        verify = (dt.date.fromisoformat(applied) + dt.timedelta(days=days)).isoformat()
    p, week = week_log(root, host, today)
    nid = next_id(p.parent, week)
    value_, unit = measure
    text, row = insert_row(p.read_text(encoding="utf-8"), "## Actions",
                           {"id": nid, "check": a.check_id, "target": a.target, "action": a.action,
                            "class": klass, "then": f"{value_:g} {unit}", "status": status,
                            "applied": applied, "verify after": verify})
    p.write_text(text, encoding="utf-8")
    print(f"log: {p}")
    print(f"id: {nid}")
    print(row)
    print(f"commit trailer: Ops-Log: {nid}")
    if verify:
        print(f"verify after: {verify}")


def table_rows(text, heading):
    """Rows of the first markdown table after `heading`, as dicts keyed by header."""
    if heading not in text:
        return []
    lines = [l for l in text.split(heading, 1)[1].splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    head = [c.strip().lower() for c in split_cells(lines[0])]
    rows = []
    for line in lines[2:]:
        cells = split_cells(line)
        if len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    return rows


def due(root, host, today):
    found = 0
    for f in sorted(log_dir(root, host).glob("*.md")):
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
    ap.add_argument("hosts", nargs="*")
    ap.add_argument("--root", default="~/dx")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--flags", action="store_true")
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--append-row", action="store_true", help="add one action row to this week's log")
    ap.add_argument("--check-id", default="", metavar="ID", help="the check id the action closes")
    ap.add_argument("--target", default="", help="the host, unit, or service the action is about")
    ap.add_argument("--action", default="", help="what happens, in one sentence")
    ap.add_argument("--class", dest="klass", default="", metavar="CLASS",
                    help="the risk class from the fixes table: " + ", ".join(CLASSES))
    ap.add_argument("--then", default="", metavar="MEASURE",
                    help="the measure before the action, a number and a unit: " + ", ".join(sorted(UNITS)))
    ap.add_argument("--status", default="todo", choices=("todo", "applied"))
    ap.add_argument("--applied", default="", metavar="YYYY-MM-DD")
    ap.add_argument("--verify-days", type=int, default=None,
                    help="days until the verdict; without it standards.md decides")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    if a.check:
        sys.exit(check(root))
    names = [host_name(h) for h in a.hosts] or [host_name()]
    if a.flags:
        for h in names:
            flags(root, h)
        return
    if a.append_row:
        for h in names:
            append_row(root, h, today, a)
        return
    if a.log or a.due:
        for h in names:
            (log if a.log else due)(root, h, today)
        return
    for h in names:
        create(root, h)


if __name__ == "__main__":
    main()
