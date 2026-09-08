#!/usr/bin/env python3
"""Where a host stands in the ops loop, read from the workspace alone.

Usage:
  status.py [--root ~/dx] [HOST ...] [--today YYYY-MM-DD]

No argument: every host folder under <root>/machines whose config says `role: server`. Reads the
workspace files, the newest audit per tool under audits/, the log tables under log/ops/, and
proposals/. Never touches a host and never the network.
Stdlib only. Exit code 2 when the workspace or a named host folder does not exist.
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


THEME = "ops"
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
    # 1. A way in survives, and no credential leaks.
    "access.single-path": 1, "secret.plaintext": 1, "secret.in-repo": 1, "secret.mode": 1,
    "key.orphan": 1, "key.duplicate": 1, "backup.missing": 1, "backup.stale": 1,
    # 2. The host is not standing open.
    "ssh.root-login": 2, "ssh.password-auth": 2, "port.world-open": 2, "panel.exposed": 2,
    "fw.disabled": 2, "tls.expired": 2,
    # 3. Someone is waiting on a service.
    "service.down": 3, "service.failed": 3, "timer.disabled": 3, "timer.missed": 3,
    "deploy.absent": 3, "deploy.no-key": 3,
    # 4. What is known-bad but not yet exploited.
    "pkg.security": 4, "boot.pending": 4, "tls.expiring": 4, "os.eol": 4, "intrusion.off": 4,
    "ssh.weak-crypto": 4, "key.weak": 4, "key.past-rotation": 4, "sudo.nopasswd": 4,
    # 5. What costs later.
    "service.restarts": 5, "code.behind": 5, "unit.unhardened": 5, "pkg.pending": 5,
    "pkg.unattended-off": 5, "ssh.no-limit": 5, "backup.untested": 5, "secret.missing": 5,
    "backup.offsite": 5,
    # 6. Tidiness.
    "port.unexpected": 6, "fw.rule-orphan": 6, "user.unlisted": 6, "log.no-retention": 6,
    "log.growth": 6, "plane.outdated": 6,
}
# Which skill produces and fixes an id, by namespace. Naming the skill is the difference between
# a report and a next step. A skill here that has not shipped is named under `## Planned` in the
# router, which is where scripts/check.sh reads the list: a next step points at something real.
SKILL_OF = {"ssh": "jorekai-ops:access", "key": "jorekai-ops:access", "sudo": "jorekai-ops:access",
            "user": "jorekai-ops:access", "access": "jorekai-ops:access",
            "port": "jorekai-ops:exposure", "fw": "jorekai-ops:exposure",
            "intrusion": "jorekai-ops:exposure", "tls": "jorekai-ops:exposure",
            "panel": "jorekai-ops:exposure", "pkg": "jorekai-ops:currency",
            "boot": "jorekai-ops:currency", "os": "jorekai-ops:currency",
            "plane": "jorekai-ops:currency", "backup": "jorekai-ops:recovery",
            "secret": "jorekai-ops:recovery", "log": "jorekai-ops:recovery",
            "service": "jorekai-ops:availability", "timer": "jorekai-ops:availability",
            "unit": "jorekai-ops:availability", "code": "jorekai-ops:availability",
            "deploy": "jorekai-ops:availability"}
# What a shipped tool measures today. An id this theme owns whose tool has not shipped yet is
# parked, not broken: a row carrying it waits for that release instead of being refused at its
# verify date with nobody able to say what its number meant.
MEASURED = {"ssh.root-login", "ssh.password-auth", "ssh.weak-crypto", "ssh.no-limit",
            "key.orphan", "key.past-rotation", "key.weak", "key.duplicate", "access.single-path",
            "sudo.nopasswd", "user.unlisted",
            "service.down", "service.failed", "service.restarts", "timer.disabled",
            "timer.missed", "unit.unhardened", "code.behind", "deploy.no-key", "deploy.absent",
            "backup.missing", "backup.stale", "backup.offsite", "backup.untested",
            "secret.missing", "secret.mode", "secret.in-repo", "secret.plaintext",
            "log.no-retention", "log.growth",
            "port.world-open", "port.unexpected", "panel.exposed", "fw.disabled",
            "fw.rule-orphan", "tls.expired", "tls.expiring", "intrusion.off"}


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


def read_host(root, host, today):
    """Everything the workspace says about one host. No decisions here."""
    base = root / "machines" / host
    s = {"host": host, "base": base}
    cfg = (base / "config.md").read_text(encoding="utf-8") if (base / "config.md").exists() else ""
    std = (root / "standards.md").read_text(encoding="utf-8") if (root / "standards.md").exists() else ""
    s["role"] = value(cfg, "role")
    s["access"] = value(cfg, "access")
    s["control_plane"] = value(cfg, "control_plane")
    s["services"] = value(cfg, "services")
    s["profile"] = value(std, "profile")
    s["paths"] = value(cfg, "access_paths")
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
    s["parked"] = [r for r in rows if r.get("check") in LADDER and r["check"] not in MEASURED]
    # A parked row never reaches a verdict, so it is not due for one and its date is not an event.
    # Naming it as gradeable would send the reader to a skill that can only refuse it, and the
    # parked line below already says what to do with it.
    parked = {r["check"] for r in s["parked"]}
    gradeable = [r for r in rows if r.get("status") in ("applied", "verify")
                 and r.get("check") not in parked
                 and ISO_DATE.match(r.get("verify after", ""))]
    s["due"] = [r for r in gradeable if dt.date.fromisoformat(r["verify after"]) <= today]
    future = [dt.date.fromisoformat(r["verify after"]) for r in gradeable
              if dt.date.fromisoformat(r["verify after"]) > today]
    s["next_verify"] = min(future) if future else None
    s["unknown"] = [r for r in rows if r.get("check") and r["check"] not in LADDER]
    s["proposals"] = sorted(p.stem for p in (base / "proposals").glob("*.md")) \
        if (base / "proposals").is_dir() else []
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
    if s["role"] != "server":
        return "setup", [f"`jorekai-ops:setup`: {s['host']} does not say `role: server`, "
                         "so this theme does not measure it"], then

    setup_open = []
    if not s["access"]:
        setup_open.append("`jorekai-ops:setup`: no `access` is recorded, so no pass can reach this host")
    if not s["control_plane"]:
        setup_open.append("`jorekai-ops:setup`: the control plane is not detected, so every fix "
                          "would guess which surface to write to")
    if not s["profile"]:
        setup_open.append("`jorekai-ops:setup`: no profile is chosen, so there is no bar to measure against")
    if not s["paths"]:
        setup_open.append("`jorekai-ops:setup`: no independent way in is recorded, so nothing may "
                          "change access on this host")
    started = bool(s["audits"] or s["rows"] or s["proposals"])
    if setup_open and not started:
        return "setup", setup_open, then

    stage = "loop"
    if s["due"]:
        ids = ", ".join(r.get("id", "?") for r in s["due"][:3])
        now.append(f"grade {plural(len(s['due']), 'row')} past the verify date ({ids}): "
                   "`jorekai-ops:grade` recomputes each measure and writes the verdict")
    if s["unknown"]:
        ids = sorted({r["check"] for r in s["unknown"]})
        where = ", ".join(sorted({r["_file"] for r in s["unknown"]})[:2])
        now.append(f"{plural(len(s['unknown']), 'log row')} {verb(len(s['unknown']), 'name')} a check id "
                   "this theme does not own "
                   f"({', '.join(ids[:3])} in {where}): correct the id or drop the row, because "
                   "nothing recomputes its measure at the verify date")
    if s["parked"]:
        ids = sorted({r["check"] for r in s["parked"]})
        now.append(f"{plural(len(s['parked']), 'log row')} {verb(len(s['parked']), 'wait')} for a tool that "
                   "has not shipped "
                   f"({', '.join(ids[:3])}, owned by {skill_for(ids[0])}): leave the status at "
                   "`todo` and the verify date empty until it ships")
    audits = s["audits"]
    if not audits:
        stage = "measure"
        now.append("nothing has measured this host yet: `jorekai-ops:access` first, because every "
                   "other fix here needs a second way in, then `jorekai-ops:availability`")
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
            now.append(f"{plural(len(stale), 'audit')} describe a host that has moved on: {names}. "
                       "Measure again before acting")
        if "access" not in audits:
            now.append("no `jorekai-ops:access` audit exists: nothing may change access until one does")
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
                    "`jorekai-ops:grade` settles the row it belongs to")
    return stage, now, then


def report(s, today):
    """The console report: what the workspace holds, then the stage and the next steps."""
    out = [paint(f"and-now  {s['host']}  {today.isoformat()}", "head"), "",
           "setup      access " + (s["access"] or "MISSING")
           + " · plane " + (s["control_plane"] or "UNDETECTED")
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
               + (f" · {len(s['parked'])} waiting for a tool" if s["parked"] else "")
               + (f" · {len(s['unknown'])} with an id this theme does not own" if s["unknown"] else "")
               + (f" · next verify {s['next_verify'].isoformat()}" if s["next_verify"] else ""))
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
    ap.add_argument("hosts", nargs="*")
    ap.add_argument("--root", default="~/dx")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    for h in a.hosts:         # a folder name, never a path: keep the report inside --root
        if "/" in h or h.startswith("."):
            sys.exit(f"not a host folder name: {h!r}")
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    base = root / "machines"
    if not base.is_dir():
        print(f"no workspace at {root}: run `jorekai-ops:setup` first")
        sys.exit(2)
    found = a.hosts or sorted(p.name for p in base.iterdir()
                              if p.is_dir() and (p / "config.md").exists())
    if not found:
        print(f"no host folder under {base}: run `jorekai-ops:setup` first")
        sys.exit(2)
    reports = []
    for h in found:
        if not (base / h).is_dir():
            print(f"no folder {base / h}: run `jorekai-ops:setup {h}` first")
            sys.exit(2)
        s = read_host(root, h, today)
        if not a.hosts and s["role"] != "server":
            continue          # a workstation belongs to the dx theme, not to this one
        reports.append(report(s, today))
    if not reports:
        print(f"no host under {base} says `role: server`: run `jorekai-ops:setup` first")
        sys.exit(2)
    print("\n\n".join(reports))


if __name__ == "__main__":
    main()
