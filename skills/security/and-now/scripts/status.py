#!/usr/bin/env python3
"""Where a repository stands in the security loop, read from the workspace alone.

Usage:
  status.py [--root ~/sec] [REPO ...] [--today YYYY-MM-DD]

No argument: every repository folder under <root>/repos whose config says `role: code`. Reads the
workspace files, the newest audit per tool under audits/, the log tables under log/security/, the
rules under rules/, and proposals/. Never reads a repository and never the network.
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


THEME = "security"
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^-\s*([A-Za-z_]+):\s*(.*)$")
HINT_RE = re.compile(r"\s*\([^()]*\)\s*$")
KIND_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")
AUDIT_MAX_AGE = 30          # days; overridden by audit_max_age_days in standards.md

# Every check id this theme owns, with the rung of the ladder it sits on. The ladder is what turns
# a list of findings into an order of work, and naming every id here is also how a log row whose
# id nobody measures is told from one that belongs to another theme (decisions/0015).
LADDER = {
    # 1. What is out is out.
    "cred.history": 1, "cred.tracked": 1, "cred.unrotated": 1,
    # 2. The build can be taken over.
    "build.untrusted-checkout": 2, "build.script-injection": 2, "build.token-broad": 2,
    "build.action-unpinned": 2,
    # 3. A known-exploited hole is installed here.
    "dep.known-exploited": 3, "dep.fix-available": 3,
    # 4. Input reaches a dangerous sink.
    "vuln.injection": 4, "vuln.authz": 4, "vuln.deserialize": 4, "vuln.ssrf": 4, "vuln.crypto": 4,
    # 5. Known-bad, not yet reachable.
    "dep.vulnerable": 5, "vuln.exposure": 5,
    # 6. Tidiness.
    "dep.unresolved": 6,
}
# Which skill produces and fixes an id, by namespace. Naming the skill is the difference between
# a report and a next step. Every id this theme owns is measured by a skill that exists, so a row
# is either gradeable or names an id of another theme.
SKILL_OF = {"cred": "jorekai-security:secrets", "build": "jorekai-security:pipeline",
            "dep": "jorekai-security:deps", "vuln": "jorekai-security:review"}


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


def read_repo(root, slug, today):
    """Everything the workspace says about one repository. No decisions here."""
    base = root / "repos" / slug
    s = {"slug": slug, "base": base}
    cfg = (base / "config.md").read_text(encoding="utf-8") if (base / "config.md").exists() else ""
    std = (root / "standards.md").read_text(encoding="utf-8") if (root / "standards.md").exists() else ""
    s["role"] = value(cfg, "role")
    s["path"] = value(cfg, "path")
    s["entrypoints"] = value(cfg, "entrypoints")
    s["store"] = value(cfg, "secret_store")
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

    rows = []
    logdir = base / "log" / THEME
    for f in sorted(logdir.glob("*.md")) if logdir.is_dir() else []:
        for r in table_rows(f.read_text(encoding="utf-8"), "## Actions"):
            r["_file"] = f.name
            rows.append(r)
    s["rows"] = rows
    s["todo"] = [r for r in rows if r.get("status") == "todo"]
    gradeable = [r for r in rows if r.get("status") in ("applied", "verify")
                 and ISO_DATE.match(r.get("verify after", ""))]
    s["due"] = [r for r in gradeable if dt.date.fromisoformat(r["verify after"]) <= today]
    future = [dt.date.fromisoformat(r["verify after"]) for r in gradeable
              if dt.date.fromisoformat(r["verify after"]) > today]
    s["next_verify"] = min(future) if future else None
    s["unknown"] = [r for r in rows if r.get("check") and r["check"] not in LADDER]
    s["proposals"] = sorted(p.stem for p in (base / "proposals").glob("*.md")) \
        if (base / "proposals").is_dir() else []
    s["rules"] = sorted(p.stem for p in (base / "rules").glob("*.json")) \
        if (base / "rules").is_dir() else []
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
    if s["role"] != "code":
        return "setup", [f"`jorekai-security:setup`: {s['slug']} does not say `role: code`, "
                         "so this theme does not measure it"], then

    setup_open = []
    if not s["path"]:
        setup_open.append("`jorekai-security:setup`: no `path` is recorded, so no pass knows which "
                          "checkout to read")
    if not s["entrypoints"]:
        setup_open.append("`jorekai-security:setup`: no entry point is recorded, so every pattern "
                          "reads as attacker-controlled and the review reports noise")
    if not s["profile"]:
        setup_open.append("`jorekai-security:setup`: no profile is chosen, so there is no bar to "
                          "measure against")
    if not s["store"]:
        setup_open.append("`jorekai-security:setup`: no secret store is recorded, so a credential "
                          "that is found has nowhere to go")
    started = bool(s["audits"] or s["rows"] or s["proposals"])
    if setup_open and not started:
        return "setup", setup_open, then

    stage = "loop"
    if s["due"]:
        ids = ", ".join(r.get("id", "?") for r in s["due"][:3])
        now.append(f"grade {plural(len(s['due']), 'row')} past the verify date ({ids}): "
                   "`jorekai-security:grade` recomputes each measure and writes the verdict")
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
        now.append("nothing has measured this repository yet: `jorekai-security:secrets` first, "
                   "because a credential that is out is the one finding an edit cannot undo, "
                   "then `jorekai-security:pipeline`")
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
        if "secrets" not in audits:
            now.append("no `jorekai-security:secrets` audit exists: nothing here knows whether a "
                       "credential is already out")
        if "review" in audits and not s["rules"]:
            now.append("a review audit exists and no rule stands in rules/: a finding that earns "
                       "no rule earns no log row, so it belongs in proposals/")
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
                    "`jorekai-security:grade` settles the row it belongs to")
    return stage, now, then


def report(s, today):
    """The console report: what the workspace holds, then the stage and the next steps."""
    out = [paint(f"and-now  {s['slug']}  {today.isoformat()}", "head"), "",
           "setup      path " + (s["path"] or "MISSING")
           + " · entry points " + (s["entrypoints"] or "NONE RECORDED")
           + " · profile " + (s["profile"] or "UNCHOSEN")]
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
               + (f" · {len(s['unknown'])} with an id this theme does not own" if s["unknown"] else "")
               + (f" · next verify {s['next_verify'].isoformat()}" if s["next_verify"] else ""))
    out.append(f"rules      {plural(len(s['rules']), 'rule')} written by review")
    out.append(f"proposals  {', '.join(s['proposals']) or 'none'}")
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
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--root", default="~/sec")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    for h in a.repos:         # a folder name, never a path: keep the report inside --root
        if "/" in h or h.startswith("."):
            sys.exit(f"not a repository folder name: {h!r}")
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    base = root / "repos"
    if not base.is_dir():
        print(f"no workspace at {root}: run `jorekai-security:setup` first")
        sys.exit(2)
    found = a.repos or sorted(p.name for p in base.iterdir()
                              if p.is_dir() and (p / "config.md").exists())
    if not found:
        print(f"no repository folder under {base}: run `jorekai-security:setup` first")
        sys.exit(2)
    reports = []
    for h in found:
        if not (base / h).is_dir():
            print(f"no folder {base / h}: run `jorekai-security:setup {h}` first")
            sys.exit(2)
        s = read_repo(root, h, today)
        if not a.repos and s["role"] != "code":
            continue          # a folder that does not say `role: code` is not measured here
        reports.append(report(s, today))
    if not reports:
        print(f"no folder under {base} says `role: code`: run `jorekai-security:setup` first")
        sys.exit(2)
    print("\n\n".join(reports))


if __name__ == "__main__":
    main()
