#!/usr/bin/env python3
"""Where a repository stands in the stack loop, read from the workspace alone.

Usage:
  status.py [--root ~/stack] [REPO ...] [--today YYYY-MM-DD]

No argument: every repository folder under <root>/repos whose config says `role: stack`. Reads
the workspace files, the newest audit per tool under audits/, the log tables under log/stack/,
the snapshot of the declaration under repos/<slug>/stack.yaml, and proposals/. Never reads a
repository and never the network.
Stdlib only. Exit code 2 when the workspace or a named repository folder does not exist.
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


# Every check id this theme owns, with the rung of the ladder it sits on. The ladder is what turns
# a list of findings into an order of work, and naming every id here is also how a log row whose
# id nobody measures is told from one that belongs to another theme (decisions/0015).
# scripts/check_rungs.py compares this table to the Rung column of the router's fixes table.
LADDER = {
    # 1. The declaration is right.
    "decl.absent": 1, "decl.unmatched": 1,
    # 2. The lock cannot be walked around.
    "escape.unenforced": 2, "escape.unowned": 2, "escape.expired": 2,
    # 3. Nobody went through the back door.
    "escape.type": 3, "escape.lint": 3, "escape.test": 3,
    # 4. A declared guard runs.
    "guard.missing": 4, "guard.disabled": 4, "guard.unwired": 4, "guard.unbarred": 4,
    "guard.rulegap": 4,
    # 5. The install is reproducible.
    "lock.incomplete": 5, "lock.runtime": 5,
    # 6. The convention holds.
    "boundary.crossed": 6, "boundary.cycle": 6, "adapter.bypassed": 6, "decl.generated": 6,
    # 7. The bar is reached.
    "guard.coverage": 7, "guard.assertionless": 7, "guard.slow": 7, "dead.export": 7,
    "dead.file": 7, "dead.dep": 7, "boundary.deep-import": 7, "adapter.missing": 7,
    "adapter.untargeted": 7,
    # 8. What stayed open.
    "decl.undeclared": 8, "decl.undecided": 8,
}
# Which skill produces and fixes an id, by namespace. Naming the skill is the difference between
# a report and a next step. Every id this theme owns is measured by a skill that exists, so a row
# is either gradeable or names an id of another theme.
SKILL_OF = {"decl": "jorekai-stack:drift", "boundary": "jorekai-stack:drift",
            "adapter": "jorekai-stack:drift", "lock": "jorekai-stack:drift",
            "escape": "jorekai-stack:guards", "guard": "jorekai-stack:guards",
            "dead": "jorekai-stack:guards"}
THEME = "stack"
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^-\s*([A-Za-z_]+):\s*(.*)$")
HINT_RE = re.compile(r"\s*\([^()]*\)\s*$")
KIND_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")
AUDIT_MAX_AGE = 30          # days; overridden by audit_max_age_days in standards.md
# A step that opens with a skill name in backticks and a colon carries the skill as its own column, so the
# leading tag is not printed twice. One that only mentions the skill elsewhere keeps its full
# text and the tag becomes the column. One with neither falls back to a dash.
LEAD_SKILL_RE = re.compile(r"^`(jorekai-stack:[a-z-]+)`:\s*")
SKILL_ANY_RE = re.compile(r"`(jorekai-stack:[a-z-]+)`")
CHECK_ANY_RE = re.compile(r"`([a-z]+\.[a-z-]+)`")


# The declaration reader: the subset of the format the snapshot uses. Duplicated from the
# measuring scripts of this theme on purpose, so this skill stays standalone.
class Unsupported(Exception):
    """The reader met a construction it does not parse. The file counts as unread, not as clean."""


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one workflow grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


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
    """Lines that carry content, as (indent, body, raw).

    `raw` keeps what a comment marker would have removed, because a script inside a block scalar
    is not this format's comment: the runner substitutes an expression before a shell sees the
    line, so an expression behind a `#` is still substituted. Everything a reader cannot follow
    raises, and the file counts as unread.
    """
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



def value(text, key):
    """Value of `- key: ...`; blank when empty or still the template's hint."""
    for line in (text or "").splitlines():
        m = KEY_RE.match(line.strip())
        if m and m.group(1).lower() == key.lower():
            v = HINT_RE.sub("", m.group(2).strip()).strip()
            return "" if not v or v.startswith("(") else v
    return ""


def split_cells(line):
    """Markdown table cells; `\\|` inside a cell is an escaped pipe, not a separator."""
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table_rows(text, heading):
    """Rows of the first markdown table after `heading`, as dicts keyed by header, each carrying
    its 1-based source line in `_line`. A row whose cell count differs from the header cannot
    become one; it is returned separately as `bad`, with its line and cell counts, so
    decisions/0030 holds: it is reported, never silently dropped."""
    if heading not in text:
        return [], []
    lines_all = text.splitlines()
    start = next(i for i, l in enumerate(lines_all) if heading in l)
    table = [(i, l) for i, l in enumerate(lines_all) if i > start and l.strip().startswith("|")]
    if len(table) < 2:
        return [], []
    head = [c.strip().lower() for c in split_cells(table[0][1])]
    rows, bad = [], []
    for i, line in table[2:]:
        cells = split_cells(line)
        if len(cells) == len(head):
            row = dict(zip(head, cells))
            row["_line"] = i + 1
            rows.append(row)
        else:
            bad.append({"line": i + 1, "cells": len(cells), "head": len(head), "text": line.strip()})
    return rows, bad


def read_json_counts(path):
    """FAIL ids and level counts of one audit, without importing json for the whole file twice."""
    import json
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    items = data.get("items", [])
    return {"fail_ids": sorted({i["id"] for i in items if i.get("level") == "FAIL"}),
            "fail": sum(1 for i in items if i.get("level") == "FAIL"),
            "warn": sum(1 for i in items if i.get("level") == "WARN")}


def read_snapshot(path, today):
    """What the snapshot of the declaration says is still open: undone human steps, decisions past
    their date. A missing or unread snapshot is reported as such, never as empty."""
    out = {"present": path.is_file(), "unread": "", "human_open": [], "undecided": []}
    if not out["present"]:
        return out
    try:
        data = parse_yaml(path.read_text(encoding="utf-8", errors="replace"))
    except Unsupported as e:
        out["unread"] = str(e)
        return out
    if not isinstance(data, dict):
        out["unread"] = "the file holds no mapping"
        return out
    for step in data.get("human_steps") or []:
        if isinstance(step, dict) and not str(step.get("done") or "").strip():
            out["human_open"].append(str(step.get("what") or "an unnamed step"))
    for decision in data.get("open_decisions") or []:
        if not isinstance(decision, dict):
            continue
        until = str(decision.get("until") or "")
        if ISO_DATE.match(until) and dt.date.fromisoformat(until) < today:
            out["undecided"].append(f"{decision.get('what') or 'an unnamed decision'} ({until})")
    return out


def read_repo(root, slug, today):
    """Everything the workspace says about one repository. No decisions here."""
    base = root / "repos" / slug
    s = {"slug": slug, "base": base}
    cfg = (base / "config.md").read_text(encoding="utf-8") if (base / "config.md").exists() else ""
    std = (root / "standards.md").read_text(encoding="utf-8") if (root / "standards.md").exists() else ""
    s["role"] = value(cfg, "role")
    s["path"] = value(cfg, "path")
    s["state"] = value(cfg, "state")
    s["profile"] = value(std, "profile")
    max_age = value(std, "audit_max_age_days")
    s["max_age"] = int(max_age) if max_age.isdigit() else AUDIT_MAX_AGE

    by_kind = {}
    for p in sorted((base / "audits").glob("*.json")) if (base / "audits").is_dir() else []:
        m = KIND_RE.match(p.stem)
        date = DATE_RE.match(p.stem)
        if not m or not date:
            continue
        counts = read_json_counts(p)
        if counts is None:
            continue
        entry = dict(counts, kind=m.group(1), file=p.name,
                     age=(today - dt.date.fromisoformat(date.group(1))).days)
        if m.group(1) not in by_kind or by_kind[m.group(1)]["age"] > entry["age"]:
            by_kind[m.group(1)] = entry
    s["audits"] = dict(sorted(by_kind.items()))

    rows, unreadable = [], []
    logdir = base / "log" / THEME
    for f in sorted(logdir.glob("*.md")) if logdir.is_dir() else []:
        found, bad = table_rows(f.read_text(encoding="utf-8"), "## Actions")
        for r in found:
            r["_file"] = f.name
            rows.append(r)
        unreadable += [{"file": f.name, "line": b["line"], "id": "?", "check": "?",
                        "why": f"the row has {b['cells']} cells against a header of {b['head']}, "
                               "likely an unescaped |"} for b in bad]
    s["rows"] = rows
    s["todo"] = [r for r in rows if r.get("status") == "todo"]
    gradeable = [r for r in rows if r.get("status") in ("applied", "verify")
                 and ISO_DATE.match(r.get("verify after", ""))]
    s["due"] = [r for r in gradeable if dt.date.fromisoformat(r["verify after"]) <= today]
    future = [dt.date.fromisoformat(r["verify after"]) for r in gradeable
              if dt.date.fromisoformat(r["verify after"]) > today]
    s["next_verify"] = min(future) if future else None
    s["unknown"] = [r for r in rows if r.get("check") and r["check"] not in LADDER]
    unreadable += [{"file": r["_file"], "line": r.get("_line", 0), "id": r.get("id") or "?",
                    "check": r.get("check") or "?",
                    "why": f"verify after {(r.get('verify after') or '(empty)')!r} is not a "
                           "YYYY-MM-DD date"}
                   for r in rows if r.get("status") in ("applied", "verify")
                   and not ISO_DATE.match(r.get("verify after", ""))]
    s["unreadable"] = sorted(unreadable, key=lambda u: (u["file"], u["line"]))
    s["proposals"] = sorted(p.stem for p in (base / "proposals").glob("*.md")) \
        if (base / "proposals").is_dir() else []
    s["snapshot"] = read_snapshot(base / "stack.yaml", today)
    return s


def rung(cid):
    return LADDER.get(cid, 9)


def skill_for(cid):
    return SKILL_OF.get(cid.split(".", 1)[0], "")


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one row waits, two rows wait."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def decide(s, today):
    """Stage and the ordered list of next steps. Every step names what to run or what to write."""
    now, then = [], []
    if s["role"] != "stack":
        return "setup", [f"`jorekai-stack:setup`: {s['slug']} does not say `role: stack`, "
                         "so this theme does not measure it"], then

    setup_open = []
    if not s["path"]:
        setup_open.append("`jorekai-stack:setup`: no `path` is recorded, so no pass knows which "
                          "checkout to read")
    if not s["profile"]:
        setup_open.append("`jorekai-stack:setup`: no profile is chosen, so `jorekai-stack:choose` "
                          "has no bars to start from")
    if not s["state"]:
        setup_open.append("`jorekai-stack:setup`: `state` is blank, so nothing says whether the "
                          "tree is to be generated or adopted")
    started = bool(s["audits"] or s["rows"] or s["proposals"])
    if setup_open and not started:
        return "setup", setup_open, then

    stage = "loop"
    if s["due"]:
        ids = ", ".join(r.get("id", "?") for r in s["due"][:3])
        now.append(f"grade {plural(len(s['due']), 'row')} past the verify date ({ids}): "
                   "`jorekai-stack:grade` recomputes each measure and writes the verdict")
    if s["unreadable"]:
        first = s["unreadable"][0]
        now.append(f"{plural(len(s['unreadable']), 'log row')} "
                   f"{verb(len(s['unreadable']), 'are', one='is')} unreadable, starting with "
                   f"{first['file']}:{first['line']} ({first['why']}): repair it, because "
                   "nothing here can grade or count a row it cannot parse")
    if s["unknown"]:
        ids = sorted({r["check"] for r in s["unknown"]})
        where = ", ".join(sorted({r["_file"] for r in s["unknown"]})[:2])
        now.append(f"{plural(len(s['unknown']), 'log row')} {verb(len(s['unknown']), 'name')} a check id "
                   "this theme does not own "
                   f"({', '.join(ids[:3])} in {where}): correct the id or drop the row, because "
                   "nothing recomputes its measure at the verify date")
    audits = s["audits"]
    if not audits:
        stage = "measure"
        now.append("nothing has measured this repository yet: `jorekai-stack:guards` first, "
                   "because a suppression nobody named is the one finding that hides every "
                   "other one, then `jorekai-stack:drift`")
    else:
        failing = [(rung(cid), cid, e) for e in audits.values() for cid in e["fail_ids"]]
        for _, cid, e in sorted(failing, key=lambda x: (x[0], x[1]))[:4]:
            stage = "measure"
            owner = skill_for(cid)
            now.append(f"`{cid}` still fails in {e['file']}"
                       + (f": `{owner}` names the fix" if owner else "") + ", then one log row for it")
        stale = [e for e in audits.values() if e["age"] > s["max_age"]]
        if stale:
            names = ", ".join(f"{e['kind']} ({plural(e['age'], 'day')})"
                              for e in sorted(stale, key=lambda x: -x["age"])[:3])
            now.append(f"{plural(len(stale), 'audit')} describe a repository that has moved on: "
                       f"{names}. Measure again before acting")
        if "guards" not in audits:
            now.append("no `jorekai-stack:guards` audit exists: nothing here knows whether a "
                       "suppression stands in the tree without a waiver")
    snap = s["snapshot"]
    if not snap["present"]:
        now.append("`jorekai-stack:setup`: no snapshot of the declaration is in the workspace, "
                   "so run `scaffold.py --snapshot` and the open human steps become items")
    elif snap["unread"]:
        now.append(f"`jorekai-stack:choose`: the snapshot of the declaration could not be read "
                   f"({snap['unread']}), so its open steps are unknown")
    for what in snap["human_open"]:
        now.append(f"`jorekai-stack:new`: {what} is still open")
    for what in snap["undecided"]:
        now.append(f"`jorekai-stack:choose`: the decision about {what} is past its date, take it "
                   "or move the date with a reason")
    for r in s["todo"]:
        now.append(f"open row {r.get('id', '?')} ({r.get('check', '?')} on {r.get('target', '?')}): "
                   f"{r.get('action', '?')}, then set Status, Applied, and Verify after")
    for slug in s["proposals"]:
        now.append(f"proposals/{slug}.md waits for a decision: give it a measure and it becomes a "
                   "log row, or drop it")
    now += setup_open
    if not now:
        now.append("nothing open: measure again when the newest audit ages out")
    if s["next_verify"]:
        then.append(f"{s['next_verify'].isoformat()}: first verify date reached, "
                    "`jorekai-stack:grade` settles the row it belongs to")
    return stage, now, then


def report(s, today):
    """The console report: what the workspace holds, then the stage and the next steps."""
    out = [paint(f"and-now  {s['slug']}  {today.isoformat()}", "head"), "",
           "setup      path " + (s["path"] or "MISSING")
           + " · profile " + (s["profile"] or "UNCHOSEN")
           + " · state " + (s["state"] or "BLANK")]
    if s["audits"]:
        label = "audits    "
        for kind, a in s["audits"].items():
            out.append(f"{label} {kind.ljust(12)} {a['file']}, {plural(a['age'], 'day')} old, "
                       f"{a['fail']} FAIL, {a['warn']} WARN")
            label = "          "
    else:
        out.append("audits     none, so nothing here is measured yet")
    by = {}
    for r in s["rows"]:
        by[r.get("status", "?")] = by.get(r.get("status", "?"), 0) + 1
    out.append(f"log        {plural(len(s['rows']), 'row')}: "
               + (", ".join(f"{v} {k}" for k, v in sorted(by.items())) or "empty")
               + f" · {len(s['due'])} due for a verdict"
               + (f" · {len(s['unreadable'])} unreadable" if s["unreadable"] else "")
               + (f" · {len(s['unknown'])} with an id this theme does not own" if s["unknown"] else "")
               + (f" · next verify {s['next_verify'].isoformat()}" if s["next_verify"] else ""))
    snap = s["snapshot"]
    out.append("snapshot   " + ("none" if not snap["present"] else
                                f"unread ({snap['unread']})" if snap["unread"] else
                                f"{plural(len(snap['human_open']), 'human step')} open, "
                                f"{plural(len(snap['undecided']), 'decision')} past the date"))
    out.append(f"proposals  {', '.join(s['proposals']) or 'none'}")
    stage, now, then = decide(s, today)
    out += ["", f"{paint('stage', 'head')}  {stage}", "", paint("now", "head")]
    columns = [step_columns(step) for step in now]
    width = max((len(skill) for skill, _ in columns), default=0)
    out += [f"  {i}. {skill.ljust(width)}  {short_paths(text)}"
            for i, (skill, text) in enumerate(columns, 1)]
    if then:
        out += ["", paint("then", "head") + "  " + "; ".join(short_paths(t) for t in then)]
    return "\n".join(out)


def short_paths(text):
    """The home directory inside a sentence written as `~`, so a step fits one line."""
    return text.replace(str(Path.home()), "~")


def step_columns(text):
    """The skill this step belongs to, and the text beside it, as two columns of one line."""
    m = LEAD_SKILL_RE.match(text)
    if m:
        return m.group(1), text[m.end():]
    m = SKILL_ANY_RE.search(text)
    if m:
        return m.group(1), text
    m = CHECK_ANY_RE.search(text)
    if m:
        skill = skill_for(m.group(1))
        if skill:
            return skill, text
    return "-", text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--root", default="~/stack")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    for h in a.repos:         # a folder name, never a path: keep the report inside --root
        if "/" in h or h.startswith("."):
            sys.exit(f"not a repository folder name: {h!r}")
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    base = root / "repos"
    if not base.is_dir():
        print(f"no workspace at {root}: run `jorekai-stack:setup` first")
        sys.exit(2)
    found = a.repos or sorted(p.name for p in base.iterdir()
                              if p.is_dir() and (p / "config.md").exists())
    if not found:
        print(f"no repository folder under {base}: run `jorekai-stack:setup` first")
        sys.exit(2)
    reports = []
    for h in found:
        if not (base / h).is_dir():
            print(f"no folder {base / h}: run `jorekai-stack:setup {h}` first")
            sys.exit(2)
        s = read_repo(root, h, today)
        if not a.repos and s["role"] != "stack":
            continue          # a folder that does not say `role: stack` is not measured here
        reports.append(report(s, today))
    if not reports:
        print(f"no folder under {base} says `role: stack`: run `jorekai-stack:setup` first")
        sys.exit(2)
    print("\n\n".join(reports))


if __name__ == "__main__":
    main()
