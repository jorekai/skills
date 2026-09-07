#!/usr/bin/env python3
"""Where a machine stands in the developer experience loop, read from the workspace alone.

Usage:
  status.py [--root ~/dx] [MACHINE ...] [--today YYYY-MM-DD]

No argument: every machine folder under <root>/machines. Reads config.md, standards.md, the
machine's config, the newest audit per kind under audits/, the log tables, and proposals/.
Never touches the machine itself and never the network.
Stdlib only. Exit code 2 when the workspace or a named machine folder does not exist.
"""
import os
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^-\s*([A-Za-z_]+):\s*(.*)$")
AUDIT_MAX_AGE = 30          # days; overridden by audit_max_age_days in standards.md
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


THEME = "dx"                # this theme's log folder inside the machine folder (decisions/0015)
KIND_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")

# Which skill produces and fixes a check id, by namespace. Naming the skill is the difference
# between a report and a next step.
SKILL_OF = {"git": "jorekai-dx:repos", "repo": "jorekai-dx:repos",
            "disk": "jorekai-dx:machine", "mem": "jorekai-dx:machine",
            "container": "jorekai-dx:machine", "ci": "jorekai-dx:github",
            "pr": "jorekai-dx:github", "alert": "jorekai-dx:github",
            "branch": "jorekai-dx:github", "agent": "jorekai-dx:agent-config",
            "friction": "jorekai-dx:friction"}
# The priority ladder of the router, as data. Duplicated there on purpose: the router explains it
# to a person, this ranks it for a machine. An id nobody listed sits in the middle.
# It names every id the tools emit, so it is also the table that answers whether an id exists at
# all: a log row naming an id outside it can never be graded, because no script recomputes it.
RUNG = {"repo.secret-exposed": 1, "git.dirty": 1, "git.unpushed": 1, "repo.no-remote": 1,
        "git.detached": 1, "git.stash-old": 1,
        "disk.low": 2, "mem.pressure": 2,
        "pr.review-requested": 3, "ci.failing": 3, "alert.open": 3,
        "repo.lock-drift": 4, "git.no-upstream": 4, "git.identity": 4, "branch.unprotected": 4,
        "agent.no-pointer": 4, "agent.pointer-drift": 4, "agent.hook-broken": 4,
        "agent.permission-drift": 4, "agent.server-unreachable": 4, "pr.stale": 4,
        "disk.cache": 5, "disk.large-dir": 5, "container.reclaimable": 5,
        "friction.repeat-command": 5, "friction.repeat-sequence": 5, "friction.failed-command": 5,
        "friction.retry-prompt": 5, "friction.slow-command": 5, "friction.agent-sessions": 5,
        "git.stale-branch": 6, "repo.no-readme": 6, "repo.no-ignore": 6, "repo.no-ci": 6}


def skill_for(check_id):
    return SKILL_OF.get(check_id.split(".", 1)[0], "")


def rung(check_id):
    return RUNG.get(check_id, 5)


def unsettled(rows):
    """Log rows naming a check id no tool measures. A typo, a renamed check, or an id someone
    invented for a row: each one is a row `jorekai-dx:grade` refuses at its verify date, weeks
    after it was written. Reading it here costs nothing and says so the same week."""
    return [r for r in rows if r.get("check") and r["check"] not in RUNG]


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


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one row waits, two rows wait."""
    return (one or form + "s") if n == 1 else form


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

    # One audit per kind, newest of each. A single newest file across all kinds hides every
    # other measurement: a full disk goes quiet the moment a repository pass runs after it.
    files = [p for p in (base / "audits").glob("*.json") if p.is_file()] if (base / "audits").is_dir() else []
    by_kind = {}
    for f in files:
        entry = {"file": f.name, "age": (today - file_date(f)).days,
                 "fail": None, "warn": None, "fail_ids": []}
        kind = (KIND_RE.match(f.stem).group(1) if KIND_RE.match(f.stem) else f.stem)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            kind = str(data.get("tool") or kind)
            counts = data.get("counts", {})
            entry["fail"] = int(counts.get("FAIL", 0))
            entry["warn"] = int(counts.get("WARN", 0))
            entry["fail_ids"] = sorted({i.get("id", "?") for i in data.get("items", []) if i.get("level") == "FAIL"})
        except (ValueError, AttributeError, TypeError):
            pass
        entry["kind"] = kind
        if kind not in by_kind or by_kind[kind]["age"] > entry["age"]:
            by_kind[kind] = entry
    s["audits"] = dict(sorted(by_kind.items()))
    max_age = value((root / "standards.md").read_text(encoding="utf-8"), "audit_max_age_days") \
        if (root / "standards.md").exists() else ""
    s["max_age"] = int(max_age) if max_age.isdigit() else AUDIT_MAX_AGE

    rows = []
    logdir = base / "log" / THEME
    for f in sorted(logdir.glob("*.md")) if logdir.is_dir() else []:
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
    # A week file left at the old flat path is read by nobody, so it is reported, not merged.
    s["stray_logs"] = sorted(p.name for p in (base / "log").glob("*.md")) \
        if (base / "log").is_dir() else []
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

    started = bool(s["audits"] or s["rows"] or s["proposals"])
    if setup_open and not started:
        return "setup", setup_open, then

    stage = "loop"
    # A verdict is what makes the log learn, so a row past its verify date outranks everything else.
    if s["due"]:
        ids = ", ".join(r.get("id", "?") for r in s["due"][:3])
        now.append(f"grade {plural(len(s['due']), 'row')} past the verify date ({ids}): "
                   "`jorekai-dx:grade` recomputes each measure and writes the verdict")
    if s["stray_logs"]:
        names = ", ".join(s["stray_logs"][:3])
        now.append(f"{plural(len(s['stray_logs']), 'week file')} "
                   f"{verb(len(s['stray_logs']), 'sit')} at the old flat log path "
                   f"({names}): `jorekai-dx:setup` with `--migrate-log` moves what it finds into "
                   "log/dx/, and until then no reader here sees those rows")
    orphan = unsettled(s["rows"])
    if orphan:
        ids = sorted({r["check"] for r in orphan})
        where = ", ".join(sorted({r["_file"] for r in orphan})[:2])
        now.append(f"{plural(len(orphan), 'log row')} {verb(len(orphan), 'name')} a check id no tool measures "
                   f"({', '.join(ids[:3])} in {where}): correct the id or drop the row, "
                   "because nothing recomputes its measure at the verify date")
    audits = s["audits"]
    if not audits:
        stage = "measure"
        now.append("nothing has measured this machine yet: `jorekai-dx:repos` first, because every "
                   "destructive action depends on it, then `jorekai-dx:machine`")
    else:
        # Every failing id from every kind, ranked by the router's ladder, not by which pass ran last.
        failing = [(rung(cid), cid, e) for e in audits.values() for cid in e["fail_ids"]]
        for _, cid, e in sorted(failing, key=lambda x: (x[0], x[1]))[:4]:
            stage = "measure"
            owner = skill_for(cid)
            now.append(f"`{cid}` still fails in {e['file']}" + (f": `{owner}` names the fix" if owner else "")
                       + ", then one log row for it")
        stale = [e for e in audits.values() if e["age"] > s["max_age"]]
        if stale:
            names = ", ".join(f"{e['kind']} ({plural(e['age'], 'day')})" for e in sorted(stale, key=lambda x: -x["age"])[:3])
            now.append(f"{plural(len(stale), 'audit')} describe a machine that has moved on: {names}. Measure again before acting")
        if "repos" not in audits:
            now.append("no `jorekai-dx:repos` audit exists: nothing destructive may run until one does")

    for r in s["todo"]:
        now.append(f"open row {r.get('id', '?')} ({r.get('check', '?')} on {r.get('target', '?')}): "
                   f"{r.get('action', '?')}, then set Status, Applied, and Verify after")
    for slug in s["proposals"]:
        now.append(f"proposals/{slug}.md waits for a decision: give it a measure and it becomes a log row, or drop it")
    now += setup_open
    if not now:
        now.append("nothing open: measure again when the newest audit ages out")
    if s["next_verify"]:
        then.append(f"{s['next_verify'].isoformat()}: first verify date reached, "
                    "`jorekai-dx:grade` settles the row it belongs to")
    return stage, now, then


def report(s, today):
    """The console report: what the workspace holds, then the stage and the next steps."""
    out = [paint(f"and-now  {s['machine']}  {today.isoformat()}, week {week_of(today)}", "head"),
           "",
           "setup      config " + ("filled" if s["config"] else "TEMPLATE")
           + " \u00b7 standards " + ("filled" if s["standards"] else "TEMPLATE")
           + " \u00b7 machine config " + ("filled" if s["machine_config"] else "TEMPLATE")]
    if s["audits"]:
        label = "audits    "
        for kind, a in s["audits"].items():
            out.append(f"{label} {kind.ljust(8)} {a['file']}, {plural(a['age'], 'day')} old, "
                       f"{a['fail']} FAIL, {a['warn']} WARN")
            label = "          "
    else:
        out.append("audits     none, so nothing here is measured yet")
    by = {}
    for r in s["rows"]:
        by[r.get("status", "?")] = by.get(r.get("status", "?"), 0) + 1
    orphan = unsettled(s["rows"])
    out.append(f"log        {plural(len(s['rows']), 'row')}: "
               + (", ".join(f"{v} {k}" for k, v in sorted(by.items())) or "empty")
               + f" \u00b7 {len(s['due'])} due for a verdict"
               + (f" \u00b7 {len(orphan)} with an unknown check id" if orphan else "")
               + (f" \u00b7 next verify {s['next_verify'].isoformat()}" if s["next_verify"] else ""))
    out.append(f"proposals  {', '.join(s['proposals']) or 'none'}")
    if s["stray_logs"]:
        out.append(f"stray log  {plural(len(s['stray_logs']), 'week file')} still at log/, not log/dx/")
    stage, now, then = decide(s, today)
    out += ["", f"{paint('stage', 'head')}  {stage}", "", paint("now", "head")]
    out += [f"  {i}. {short_paths(step)}" for i, step in enumerate(now, 1)]
    if then:
        out += ["", paint("then", "head")] + [f"  - {short_paths(t)}" for t in then]
    return "\n".join(out)


def short_paths(text):
    """The home directory inside a sentence written as `~`, so a step fits one line."""
    return text.replace(str(Path.home()), "~")


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
