#!/usr/bin/env python3
"""Grade log rows whose verify date has passed: recompute the measure, propose the verdict.

Usage:
  grade.py [--root ~/sec] [REPO ...] [--today YYYY-MM-DD] [--only ID ...] [--json]
  grade.py [--root ~/sec] [REPO ...] --write       write the verdicts into the log
  grade.py --namespaces                            the tool that owns every check id namespace

A measure counts what a finding costs, so the verdict is arithmetic: the cost fell or reached
zero (`won`), it stayed inside the tolerance (`no-change`), it rose past it (`returned`).
`dropped` is never computed, because it means a person decided not to carry the action out.

Reads the workspace only: the log tables and the newest audit per tool under audits/. Never
reads a repository itself, so a stale audit is reported instead of guessed at.
Stdlib only. Exit code 2 when the workspace or a named repository folder does not exist.
"""
import os
import argparse
import datetime as dt
import json
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
VERDICT_PAINT = {"won": "PASS", "no-change": "WARN", "returned": "FAIL"}


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
THEME = "security"          # this theme's log folder in the repository folder
# The closed set of units a measure may carry, with what one of them is worth in the base unit of
# its family. Duplicated in setup/scripts/scaffold.py on purpose: each skill stays standalone.
UNITS = {"B": ("bytes", 1), "KB": ("bytes", 1024), "MB": ("bytes", 1024 ** 2),
         "GB": ("bytes", 1024 ** 3), "TB": ("bytes", 1024 ** 4), "bytes": ("bytes", 1),
         "count": ("count", 1), "percent": ("percent", 1), "seconds": ("seconds", 1)}
MEASURE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$")
# A count compares exactly. The other families move under a tree that is being worked on, so a
# change inside this share of the starting measure is no change at all.
TOLERANCE = {"bytes": 0.05, "percent": 0.05, "seconds": 0.05, "count": 0.0}
# Which tool measures a check id, by namespace. An audit is chosen by its `tool` field, so the
# verdict is measured by the same script that wrote the row's starting number.
# `--namespaces` prints this table, and scripts/check.sh compares it to the ids the theme's
# fixes table names: a namespace missing here is a row nothing can ever recompute.
TOOL_OF = {"dep": "deps", "cred": "secrets", "build": "pipeline", "vuln": "review"}


def tool_for(check_id):
    return TOOL_OF.get(check_id.split(".", 1)[0], "")


def split_cells(line):
    """Markdown table cells; `\\|` inside a cell is an escaped pipe, not a separator.
    Duplicated from setup/scripts/scaffold.py on purpose: each skill stays standalone."""
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def escape(text):
    """One table cell: a pipe inside it is escaped, and a line break would end the row."""
    return " ".join(str(text).split()).replace("|", "\\|")


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


def parse_measure(text):
    """`40 GB` as (40.0, "GB"); None when the number or the unit is not one a script recomputes."""
    m = MEASURE_RE.match(text or "")
    if not m or m.group(2) not in UNITS:
        return None
    return float(m.group(1)), m.group(2)


def base(value, unit):
    """A measure in the base unit of its family, so two rows in different units still compare."""
    family, factor = UNITS[unit]
    return family, value * factor


def show(value, unit):
    """A measure back in the unit the row was written in, so both numbers read the same way."""
    return f"{value / UNITS[unit][1]:g} {unit}"


def file_date(p):
    m = DATE_RE.search(p.name)
    return dt.date.fromisoformat(m.group(1)) if m else dt.date.fromtimestamp(p.stat().st_mtime)


def audits(base_dir):
    """The newest audit per tool, read from the `tool` field so the file name cannot mislead."""
    newest = {}
    folder = base_dir / "audits"
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        tool = str(data.get("tool") or f.stem)
        entry = {"file": f, "date": file_date(f), "items": data.get("items", [])}
        if tool not in newest or newest[tool]["date"] <= entry["date"]:
            newest[tool] = entry
    return newest


def same_target(a, b):
    """Two targets are the same when they name the same path, `~` expanded, no trailing slash."""
    def norm(t):
        return str(Path(t).expanduser()).rstrip("/") if t else ""
    return a == b or norm(a) == norm(b)


def measure_now(item, target):
    """What the check costs now for this row: the target's own share, or the total without one."""
    m = item.get("measure")
    if not m or m.get("value") is None or m.get("unit") not in UNITS:
        return None, "", "the finding carries no measure, so this check cannot be graded yet"
    by = m.get("by") or {}
    if target and by:
        for key, v in by.items():
            if same_target(key, target):
                return float(v), m["unit"], ""
        return 0.0, m["unit"], "the target no longer appears in the finding"
    if target and not by:
        # A passing check carries zero and names no target, which is the answer for every target.
        if float(m["value"]) == 0:
            return 0.0, m["unit"], ""
        return float(m["value"]), m["unit"], "the finding is not measured per target, so the total is used"
    return float(m["value"]), m["unit"], ""


def verdict_for(then, now, family):
    tolerance = TOLERANCE.get(family, 0.0) * abs(then)
    if then <= 0:
        return "returned" if now > tolerance else "no-change"
    if now < then - tolerance:
        return "won"
    if now > then + tolerance:
        return "returned"
    return "no-change"


def grade_row(row, found):
    """One due row against the newest audit of its tool. A row that cannot be graded says why."""
    out = {"id": row.get("id", ""), "check": row.get("check", ""), "target": row.get("target", ""),
           "applied": row.get("applied", ""), "then": row.get("then", ""), "now": "",
           "verdict": "", "note": "", "audit": ""}
    measure = parse_measure(row.get("then", ""))
    if not measure:
        out["note"] = "the row carries no measure a script can recompute, so it needs a person"
        return out
    tool = tool_for(out["check"])
    if not tool:
        out["note"] = f"no tool owns {out['check']}, so nothing recomputes it"
        return out
    audit = found.get(tool)
    if not audit:
        out["note"] = f"no {tool} audit in the workspace: run that skill again, then grade"
        return out
    out["audit"] = audit["file"].name
    if out["applied"] and ISO_DATE.match(out["applied"]) and audit["date"] < dt.date.fromisoformat(out["applied"]):
        out["note"] = f"the newest {tool} audit is older than the action: measure again, then grade"
        return out
    item = next((i for i in audit["items"] if i.get("id") == out["check"]), None)
    if item is None:
        out["note"] = f"{out['check']} is not in {audit['file'].name}: run {tool} with the same flags"
        return out
    now, unit, note = measure_now(item, out["target"])
    if now is None:
        out["note"] = note
        return out
    family, then_base = base(*measure)
    now_family, now_base = base(now, unit)
    if family != now_family:
        out["note"] = f"the row measures in {measure[1]} and the audit in {unit}, so they do not compare"
        return out
    out["now"] = show(now_base, measure[1])
    out["verdict"] = verdict_for(then_base, now_base, family)
    out["note"] = note
    return out


def due_rows(base_dir, today, only):
    rows = []
    folder = base_dir / "log" / THEME
    for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        for r in table_rows(f.read_text(encoding="utf-8"), "## Actions"):
            if only and r.get("id") not in only:
                continue
            if r.get("status") not in ("applied", "verify"):
                continue
            after = r.get("verify after", "")
            if only or (ISO_DATE.match(after) and dt.date.fromisoformat(after) <= today):
                r["_file"] = f
                rows.append(r)
    return rows


def insert_row(text, heading, cells):
    """Add one row at the end of the first table under `heading`, in that table's column order."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == heading), None)
    if start is None:
        sys.exit(f"no section {heading} in the log file")
    head = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("|")), None)
    if head is None:
        sys.exit(f"no table under {heading} in the log file")
    columns = [c.strip().lower() for c in split_cells(lines[head])]
    end = head
    while end + 1 < len(lines) and lines[end + 1].strip().startswith("|"):
        end += 1
    lines.insert(end + 1, "| " + " | ".join(escape(cells.get(c, "")) for c in columns) + " |")
    return "\n".join(lines) + "\n"


def is_separator(line):
    """The `|---|---|` line under a table header."""
    return line.strip().startswith("|") and set(line.strip()) <= set("|-: ")


def set_cells(text, row_id, values):
    """Rewrite named cells of the row with this id, leaving every other cell untouched.

    The columns are read from the header of the table the row sits in, because a log file holds
    two tables with different columns and the outcomes one comes first.
    """
    lines = text.splitlines()
    columns = []
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            columns = []
            continue
        if is_separator(line):
            continue
        cells = split_cells(line)
        if i + 1 < len(lines) and is_separator(lines[i + 1]):
            columns = [c.strip().lower() for c in cells]
            continue
        if not columns or len(cells) != len(columns) or cells[0] != row_id:
            continue
        for key, v in values.items():
            if key in columns:
                cells[columns.index(key)] = v
        # Every cell is escaped again: reading the row unescaped a pipe that must survive the write.
        lines[i] = "| " + " | ".join(escape(c) for c in cells) + " |"
    return "\n".join(lines) + "\n"


def write_back(graded):
    """One outcome row per verdict, and the action row's status set to it. Nothing else moves."""
    written = []
    for g in graded:
        if not g["verdict"]:
            continue
        path = g.pop("_file")
        text = path.read_text(encoding="utf-8")
        text = insert_row(text, "## Outcomes of earlier actions",
                          {"id": g["id"], "check": g["check"], "target": g["target"],
                           "applied": g["applied"], "then": g["then"], "now": g["now"],
                           "verdict": g["verdict"]})
        text = set_cells(text, g["id"], {"status": g["verdict"], "outcome": f"now {g['now']}"})
        path.write_text(text, encoding="utf-8")
        written.append(f"{g['id']} {g['verdict']} in {path.name}")
    return written


VERDICT_WORD = {"won": "the cost fell or reached zero",
                "no-change": "the cost stayed inside the tolerance",
                "returned": "the cost rose past the tolerance"}


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one row needs, two rows need."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 row(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def short(path):
    """A path with the home directory written as `~`, so a line stays readable in a terminal."""
    home = str(Path.home())
    text = str(path)
    if text == home:
        return "~"
    return "~" + text[len(home):] if text.startswith(home + "/") else text


def report(slug, graded, today):
    """The console report: one block per row due, the verdict first, the reason under it."""
    out = [paint(f"grade  {slug}  {today.isoformat()}", "head")]
    if not graded:
        return "\n".join(out + ["", "nothing due, no log row has reached its verify date"])
    settled = [g for g in graded if g["verdict"]]
    rest = len(graded) - len(settled)
    out.append(f"{len(settled)} of {plural(len(graded), 'row')} due can be settled, "
               f"{rest} {verb(rest, 'need')} a person")
    for g in graded:
        where = short(g["target"]) if g["target"] else "this repository"
        out += ["", f"{paint(g['id'], 'id')}  {g['check']} on {where}"]
        if g["verdict"]:
            verdict = paint(g["verdict"], VERDICT_PAINT.get(g["verdict"], "dim"))
            out.append(f"      then {g['then']}, now {g['now']}, verdict {verdict}: "
                       f"{VERDICT_WORD.get(g['verdict'], '')}")
        else:
            out.append(f"      then {g['then']}, {paint('no verdict yet', 'INFO')}")
        if g["note"]:
            out.append(paint(f"      {g['note']}", "dim"))
        if g["audit"]:
            out.append(paint(f"      measured again from {g['audit']}", "dim"))
    if settled:
        out += ["", paint("next", "head") + "  run the same command with --write to put these verdicts in the log"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--root", default="~/sec")
    ap.add_argument("--only", action="append", default=[], metavar="ID",
                    help="grade this row id whatever its verify date says")
    ap.add_argument("--write", action="store_true", help="write the verdicts into the log")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    ap.add_argument("--namespaces", action="store_true",
                    help="print the tool that owns every check id namespace")
    a = ap.parse_args(argv)
    if a.namespaces:
        for ns, tool in sorted(TOOL_OF.items()):
            print(f"{ns} {tool}")
        return 0
    root = Path(a.root).expanduser()
    for h in a.repos:         # a folder name, never a path: keep every write inside --root
        if "/" in h or h.startswith("."):
            sys.exit(f"not a repository folder name: {h!r}")
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    folder = root / "repos"
    if not folder.is_dir():
        print(f"no workspace at {root}: run `jorekai-security:setup` first")
        return 2
    names = a.repos or sorted(p.name for p in folder.iterdir() if p.is_dir() and (p / "config.md").exists())
    if not names:
        print(f"no repository folder under {folder}: run `jorekai-security:setup` first")
        return 2
    results, texts = {}, []
    for m in names:
        if not (folder / m).is_dir():
            print(f"no folder {folder / m}: run `jorekai-security:setup {m}` first")
            return 2
        found = audits(folder / m)
        graded = []
        for row in due_rows(folder / m, today, a.only):
            g = grade_row(row, found)
            g["_file"] = row["_file"]
            graded.append(g)
        written = write_back(graded) if a.write else []
        for g in graded:
            g.pop("_file", None)
        results[m] = {"graded": graded, "written": written}
        texts.append(report(m, graded, today))
        for line in written:
            texts.append(f"written: {line}")
    if a.json:
        print(json.dumps({"tool": "grade", "date": today.isoformat(), "repos": results},
                         indent=2, ensure_ascii=False))
    else:
        print("\n\n".join(texts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
