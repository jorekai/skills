#!/usr/bin/env python3
"""The month on this repository: what changed, what was done, and what is still open.

Usage:
  report.py [--root ~/sec] [REPO ...] --month YYYY-MM [--today YYYY-MM-DD] [--json]
  report.py [--root ~/sec] [REPO ...] --month YYYY-MM --write

Reads the workspace only: the audits of the month and the one before it, and the log weeks that
fall inside it. Nothing is measured again here, so a month with no audit says so instead of
reporting a repository nobody looked at.

`--write` renders repos/<slug>/reports/security/<month>.md from templates/report.md. Every number
in it comes from a file that already exists, and every action row names its log id.
Stdlib only. Exit code 2 when the workspace or a named repository folder does not exist.
"""
import argparse
import datetime as dt
import json
import os
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


# A verdict is coloured by what it says about the cost, not by being a verdict.
VERDICT_PAINT = {"won": "PASS", "no-change": "WARN", "returned": "FAIL", "dropped": "dim"}
VERDICTS = ("won", "no-change", "returned", "dropped")
OPEN_STATUS = ("todo", "applied", "verify")
THEME = "security"          # this theme's log and report folder in the repository folder
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "report.md"
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
WEEK_FILE = re.compile(r"^(\d{4})-W(\d{2})$")
# The closed set of units a measure may carry. Duplicated from the grade skill on purpose: each
# skill stays standalone.
UNITS = {"B": ("bytes", 1), "KB": ("bytes", 1024), "MB": ("bytes", 1024 ** 2),
         "GB": ("bytes", 1024 ** 3), "TB": ("bytes", 1024 ** 4), "bytes": ("bytes", 1),
         "count": ("count", 1), "percent": ("percent", 1), "seconds": ("seconds", 1)}
MEASURE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$")
# The tools of this theme, whose audits this report reads. A folder that ever holds another
# theme's audit would otherwise tell this repository's story with
# numbers. Duplicated from the grade skill's table on purpose: each skill stays standalone.
TOOLS = ("secrets", "pipeline", "deps", "review")
# The priority ladder of the router, as data. Duplicated in the and-now skill on purpose: this
# one orders what a month leaves open, so the three next steps are the three that cost most.
RUNG = {"access.single-path": 1, "secret.plaintext": 1, "secret.in-repo": 1, "secret.mode": 1,
        "key.orphan": 1, "key.duplicate": 1, "backup.missing": 1, "backup.stale": 1,
        "ssh.root-login": 2, "ssh.password-auth": 2, "port.world-open": 2, "panel.exposed": 2,
        "fw.disabled": 2, "tls.expired": 2,
        "service.down": 3, "service.failed": 3, "timer.disabled": 3, "timer.missed": 3,
        "deploy.absent": 3, "deploy.no-key": 3,
        "pkg.security": 4, "boot.pending": 4, "tls.expiring": 4, "os.eol": 4, "intrusion.off": 4,
        "ssh.weak-crypto": 4, "key.weak": 4, "key.past-rotation": 4, "sudo.nopasswd": 4,
        "service.restarts": 5, "code.behind": 5, "unit.unhardened": 5, "pkg.pending": 5,
        "pkg.unattended-off": 5, "ssh.no-limit": 5, "backup.untested": 5, "secret.missing": 5,
        "backup.offsite": 5,
        "port.unexpected": 6, "fw.rule-orphan": 6, "user.unlisted": 6, "log.no-retention": 6,
        "log.growth": 6, "plane.outdated": 6}


def rung(check_id):
    return RUNG.get(check_id, 5)


def split_cells(line):
    """Markdown table cells; `\\|` inside a cell is an escaped pipe, not a separator.
    Duplicated from the setup skill on purpose: each skill stays standalone."""
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def escape(text):
    """One table cell: a pipe inside it is escaped, and a line break would end the row."""
    return " ".join(str(text).split()).replace("|", "\\|")


def table_rows(text, heading):
    """Rows of the first markdown table after `heading`, as dicts keyed by header."""
    if heading not in text:
        return []
    section = []
    for line in text.split(heading, 1)[1].splitlines():
        if line.startswith("## "):
            break              # a later table is another section's, and its rows are not actions
        section.append(line)
    lines = [l for l in section if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    head = [c.strip().lower() for c in split_cells(lines[0])]
    rows = []
    for line in lines[2:]:
        cells = split_cells(line)
        if len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    return rows


def parse_measure(text):
    """`40 GB` as (40.0, "GB"); None when the number or the unit is not one a script recomputes."""
    m = MEASURE_RE.match(text or "")
    if not m or m.group(2) not in UNITS:
        return None
    return float(m.group(1)), m.group(2)


def base(value, unit):
    """A measure in the base unit of its family, so two numbers in different units compare."""
    family, factor = UNITS[unit]
    return family, value * factor


def show(value, unit):
    """A measure back in the unit it was written in, so both numbers read the same way."""
    return f"{value / UNITS[unit][1]:g} {unit}"


def month_bounds(month):
    """The first and the last day of `YYYY-MM`."""
    try:
        first = dt.date.fromisoformat(month + "-01")
    except ValueError:
        sys.exit(f"not a month: {month!r}. Expected YYYY-MM")
    return first, (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)


def week_bounds(name):
    """The Monday and Sunday of a `YYYY-Www` log file, or None when the name is another shape."""
    m = WEEK_FILE.match(name)
    if not m:
        return None
    try:
        start = dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError:
        return None
    return start, start + dt.timedelta(days=6)


def file_date(p):
    m = DATE_RE.search(p.name)
    return dt.date.fromisoformat(m.group(1)) if m else dt.date.fromtimestamp(p.stat().st_mtime)


def audits(base_dir):
    """Every audit, by tool, oldest first, read from the `tool` field inside the file."""
    found, other = {}, set()
    folder = base_dir / "audits"
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        tool = str(data.get("tool") or f.stem)
        if tool not in TOOLS:
            other.add(tool)
            continue
        found.setdefault(tool, []).append({"file": f.name, "date": file_date(f),
                                           "items": data.get("items", [])})
    for tool in found:
        found[tool].sort(key=lambda e: e["date"])
    return found, sorted(other)


def pick(entries, first, last):
    """The audit that opens the month and the one that closes it.

    The opening one is the newest audit before the month, because that is the repository the month
    started from. Without one the first audit inside the month opens it, and the report says so.
    """
    before = [e for e in entries if e["date"] < first]
    inside = [e for e in entries if first <= e["date"] <= last]
    if not inside:
        return None, None
    if before:
        return before[-1], inside[-1]
    return (inside[0], inside[-1]) if len(inside) > 1 else (None, inside[-1])


def measures(entry):
    """Every check id in an audit that carries a measure, as {id: (value, unit)}."""
    out = {}
    for item in entry["items"]:
        m = item.get("measure") or {}
        if m.get("value") is None or m.get("unit") not in UNITS:
            continue
        out[item.get("id", "")] = (float(m["value"]), m["unit"])
    return out


def movement(found, first, last):
    """What every check id cost when the month opened and what it costs now."""
    rows, no_audit, opening_only = [], [], []
    for tool in sorted(found):
        start, end = pick(found[tool], first, last)
        if end is None:
            no_audit.append(tool)
            continue
        if start is None:
            opening_only.append(tool)
            continue
        then, now = measures(start), measures(end)
        for cid in sorted(set(then) & set(now)):
            (tv, tu), (nv, nu) = then[cid], now[cid]
            family, tb = base(tv, tu)
            now_family, nb = base(nv, nu)
            if family != now_family:
                continue
            rows.append({"check": cid, "tool": tool, "then": show(tb, tu), "now": show(nb, tu),
                         "change": nb - tb, "family": family, "unit": tu,
                         "from": start["file"], "to": end["file"]})
    rows.sort(key=lambda r: (rung(r["check"]), r["change"]))
    notes = []
    if no_audit:
        subject, vb = ("it", "measures") if len(no_audit) == 1 else ("they", "measure")
        notes.append(f"no {', '.join(no_audit)} audit inside the month, so nothing {subject} "
                     f"{vb} is in this report")
    if opening_only:
        poss = "its" if len(opening_only) == 1 else "their"
        notes.append(f"one {', '.join(opening_only)} audit inside the month and none before it, "
                     f"so {poss} numbers open the next report instead of closing this one")
    return rows, notes


def in_month(row, week, first, last):
    """Whether an action belongs to this month: by the day it was applied, else by its week.

    A week that straddles two months belongs to the month holding most of its days, so an action
    is counted once across the year and never twice.
    """
    applied = row.get("applied", "")
    if ISO_DATE.match(applied):
        return first <= dt.date.fromisoformat(applied) <= last
    if not week:
        return False
    days = [week[0] + dt.timedelta(days=i) for i in range(7)]
    return sum(1 for d in days if first <= d <= last) >= 4


def log_rows(base_dir, first, last):
    """The month's actions, every open action whatever its month, and the verdicts written down."""
    actions, still_open, verdicts, weeks = [], [], {}, []
    folder = base_dir / "log" / THEME
    for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        text = f.read_text(encoding="utf-8")
        week = week_bounds(f.stem)
        for r in table_rows(text, "## Outcomes of earlier actions"):
            if r.get("verdict"):
                verdicts[r.get("id", "")] = r
        for r in table_rows(text, "## Actions"):
            r["_week"] = f.name
            if in_month(r, week, first, last):
                actions.append(r)
                if f.name not in weeks:
                    weeks.append(f.name)
            if r.get("status") in OPEN_STATUS:
                still_open.append(r)
    # A row graded in the outcomes table is settled even when nobody rewrote its status cell.
    # Listing it as open puts a finished action in the next month's three next steps.
    still_open = [r for r in still_open if not verdict_of(r, verdicts)]
    still_open.sort(key=lambda r: (rung(r.get("check", "")), r.get("id", "")))
    return actions, still_open, verdicts, weeks


def verdict_of(row, verdicts):
    """What a row ended as. The status carries it once graded; the outcomes table proves it."""
    status = row.get("status", "")
    if status in VERDICTS:
        return status
    settled = verdicts.get(row.get("id", ""))
    return settled.get("verdict", "") if settled else ""


def state_of(row, verdicts):
    """What a row reads as in the report: its verdict, or why it does not have one yet."""
    return (verdict_of(row, verdicts)
            or ("not done yet" if row.get("status") == "todo" else "still measuring"))


def counted(actions, verdicts):
    c = {v: 0 for v in VERDICTS}
    c["open"] = 0
    for row in actions:
        v = verdict_of(row, verdicts)
        if v in c:
            c[v] += 1
        elif row.get("status") in OPEN_STATUS:
            c["open"] += 1
    return c


def share(row):
    """What a movement is worth against what the check cost before, so two units compare."""
    then = parse_measure(row["then"])
    size = abs(base(*then)[1]) if then else 0
    return row["change"] / size if size else row["change"]


def headline(actions, counts, moved):
    """One sentence with the number that carries the month."""
    if not actions and not moved:
        return "Nothing was logged this month and no audit pair covers it."
    parts = [f"{plural(len(actions), 'action')} logged, {counts['won']} held"]
    # Biggest means biggest, and two checks in different units only compare as a share of what
    # they cost before. The table stays in ladder order; this one sentence does not.
    falls = sorted((r for r in moved if r["change"] < 0), key=share)
    if falls:
        best = falls[0]
        parts.append(f"the biggest fall is {best['check']}, from {best['then']} to {best['now']}")
    rises = sorted((r for r in moved if r["change"] > 0), key=share)
    if rises:
        worst = rises[-1]
        parts.append(f"the biggest rise is {worst['check']}, from {worst['then']} to {worst['now']}")
    return ", ".join(parts) + "."


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one row waits, two rows wait."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 action(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def table(head, rows):
    """One markdown table, or the sentence that stands in for an empty one."""
    if not rows:
        return "Nothing in this section this month."
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(escape(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def render(slug, month, data):
    """The report file, from the template beside this script."""
    text = TEMPLATE.read_text(encoding="utf-8")
    moved = table(["Check", "When the month opened", "Now", "Where the numbers come from"],
                  [[r["check"], r["then"], r["now"], f"{r['from']} to {r['to']}"]
                   for r in data["movement"][:12]])
    actions = table(["id", "Check", "Target", "What happened", "Class", "Verdict"],
                    [[r.get("id", ""), r.get("check", ""), r.get("target", ""),
                      r.get("action", ""), r.get("class", ""),
                      data["verdict_of"].get(r.get("id", ""), "")]
                     for r in data["actions"]])
    still_open = table(["id", "Check", "Target", "Status", "Verify after"],
                       [[r.get("id", ""), r.get("check", ""), r.get("target", ""),
                         r.get("status", ""), r.get("verify after", "")] for r in data["open"][:10]])
    nxt = "\n".join(f"{i}. {r.get('check', '')} on {r.get('target', '') or 'this repository'} "
                    f"(log {r.get('id', '')})" for i, r in enumerate(data["next"], 1)) \
        or "Nothing is open, so the next month starts with a measuring pass."
    subs = {"SLUG": slug, "MONTH": month, "HEADLINE": data["headline"],
            "MOVEMENT": moved, "ACTIONS": actions, "OPEN": still_open, "NEXT": nxt,
            "WEEKS": ", ".join(data["weeks"]) or "no log week",
            "NOTES": "\n".join(f"- {n}" for n in data["notes"]) or "- Nothing was left out.",
            "WON": str(data["counts"]["won"]), "NO_CHANGE": str(data["counts"]["no-change"]),
            "RETURNED": str(data["counts"]["returned"]),
            "STILL": str(data["counts"]["open"])}
    for key, value in subs.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def collect(base_dir, first, last):
    found, other = audits(base_dir)
    moved, notes = movement(found, first, last)
    if other:
        notes.append(f"the {', '.join(other)} audits in this folder belong to another theme "
                     "and are not read here")
    missing = [tool for tool in TOOLS if tool not in found]
    if missing:
        subject, vb = ("it", "measures") if len(missing) == 1 else ("they", "measure")
        notes.append(f"no {', '.join(missing)} audit at all, so nothing {subject} {vb} has ever "
                     "been in a report")
    actions, still_open, verdicts, weeks = log_rows(base_dir, first, last)
    counts = counted(actions, verdicts)
    return {"movement": moved, "notes": notes, "actions": actions, "open": still_open,
            "weeks": weeks, "counts": counts,
            "verdict_of": {r.get("id", ""): state_of(r, verdicts) for r in actions},
            "next": still_open[:3],
            "headline": headline(actions, counts, moved)}


def bar(won, no_change, returned, still_open):
    """Four counts in one line, a zero dimmed, a count above zero in the colour of its word."""
    cells = [(won, "won", "PASS"), (no_change, "no-change", "WARN"),
             (returned, "returned", "FAIL"), (still_open, "open", "INFO")]
    return " · ".join(paint(f"{n} {word}", key if n else "dim") for n, word, key in cells)


def console(slug, month, data, written=""):
    """The console report: the month in one line, then what moved, then what is still open."""
    c = data["counts"]
    out = [paint(f"report  {slug}  {month}", "head"),
           f"log weeks  {', '.join(data['weeks']) or 'none'}", "",
           bar(c["won"], c["no-change"], c["returned"], c["open"]), "", data["headline"]]
    if data["movement"]:
        out += ["", paint("moved", "head")]
        for r in data["movement"][:8]:
            arrow = "fell" if r["change"] < 0 else ("rose" if r["change"] > 0 else "held")
            level = "PASS" if r["change"] < 0 else ("FAIL" if r["change"] > 0 else "dim")
            out.append(f"      {paint(r['check'].ljust(28), 'dim')}  {r['then']} to {r['now']}  "
                       + paint(arrow, level))
    if data["actions"]:
        out += ["", paint("done", "head")]
        for r in data["actions"]:
            v = data["verdict_of"].get(r.get("id", ""), "")
            out.append(f"      {paint(r.get('id', '').ljust(14), 'id')}  {r.get('check', '')}  "
                       + paint(v, VERDICT_PAINT.get(v, "INFO")))
    if data["open"]:
        out += ["", paint("open", "head")]
        for r in data["open"][:5]:
            out.append(f"      {paint(r.get('id', '').ljust(14), 'id')}  {r.get('check', '')}  "
                       f"{r.get('status', '')}")
    for note in data["notes"]:
        out += ["", paint("note  " + note, "dim")]
    if written:
        out += ["", paint("next", "head") + f"  read {written}, then turn the three open rows at the "
                "top of the ladder into rows for the coming month"]
    else:
        out += ["", paint("next", "head") + "  run the same command with --write to put this month in "
                "reports/" + THEME + "/, then read the three open rows at the top of the ladder"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--root", default="~/sec")
    ap.add_argument("--month", default=None, help="YYYY-MM, the month the report covers")
    ap.add_argument("--write", action="store_true", help="write the report file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args(argv)
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    month = a.month or (today.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
    first, last = month_bounds(month)
    root = Path(a.root).expanduser()
    for m in a.repos:         # a folder name, never a path: keep every write inside --root
        if "/" in m or m.startswith("."):
            sys.exit(f"not a repository folder name: {m!r}")
    folder = root / "repos"
    if not folder.is_dir():
        print(f"no workspace at {root}: run `jorekai-security:setup` first")
        return 2
    names = a.repos or sorted(p.name for p in folder.iterdir()
                                 if p.is_dir() and (p / "config.md").exists())
    if not names:
        print(f"no repository folder under {folder}: run `jorekai-security:setup` first")
        return 2
    results, texts = {}, []
    for m in names:
        if not (folder / m).is_dir():
            print(f"no folder {folder / m}: run `jorekai-security:setup {m}` first")
            return 2
        data = collect(folder / m, first, last)
        written = ""
        if a.write:
            target = folder / m / "reports" / THEME / f"{month}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(m, month, data), encoding="utf-8")
            written = str(target)
        results[m] = {"month": month, "counts": data["counts"], "headline": data["headline"],
                      "movement": [{k: v for k, v in r.items() if k != "family"}
                                   for r in data["movement"]],
                      "actions": [{k: v for k, v in r.items() if not k.startswith("_")}
                                  for r in data["actions"]],
                      "open": [{k: v for k, v in r.items() if not k.startswith("_")}
                               for r in data["open"]],
                      "weeks": data["weeks"], "notes": data["notes"], "written": written}
        texts.append(console(m, month, data, written))
        if written:
            texts.append(f"written: {written}")
    if a.json:
        print(json.dumps({"tool": "report", "month": month, "repos": results},
                         indent=2, ensure_ascii=False))
    else:
        print("\n\n".join(texts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
