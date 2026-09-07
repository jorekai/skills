#!/usr/bin/env python3
"""Whether the services this host is supposed to run are running, current, and hardened.

Usage:
  availability.py --service SPEC [--service SPEC ...] [--root DIR] [--show-dir DIR]
                  [--ssh-config FILE] [--require-option NAME=VALUE ...] [--except UNIT:NAME ...]
                  [--restart-bar N] [--missed-grace-seconds N] [--now YYYY-MM-DDTHH:MM:SS] [--json]
  availability.py --measures              the unit every check id is measured in

SPEC is `name=unit[,timer=unit][,path=DIR][,repo=URL][,commit=SHA]`, one per service the
standards name. `scaffold.py --flags` in the setup skill prints them from the workspace.

Unit state is read from `systemctl show`, or from `--show-dir` holding one `<unit>.show` file per
unit, which is what makes the whole pass testable without systemd. Reads only: nothing is started,
stopped, or written, and only `code.behind` looks at a repository, locally and without fetching.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import os
import argparse
import datetime as dt
import json
import re
import subprocess
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


LEVEL_ORDER = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
# The unit of every check id this script measures. A measure counts what the finding costs, so
# lower is better and zero means the check no longer fires (decisions/0014). `--measures` prints
# this table and scripts/check.sh compares it to the unit named in the theme's fixes.md.
MEASURES = {"service.down": "count", "service.failed": "count", "service.restarts": "count",
            "timer.disabled": "count", "timer.missed": "count", "unit.unhardened": "count",
            "code.behind": "count", "deploy.no-key": "count", "deploy.absent": "count"}
# What the number in a row counts, per check id.
ROW_WORD = {"service.down": ("unit", "units"), "service.failed": ("unit", "units"),
            "service.restarts": ("restart over the bar", "restarts over the bar"),
            "timer.disabled": ("timer", "timers"), "timer.missed": ("timer", "timers"),
            "unit.unhardened": ("missing option", "missing options"),
            "code.behind": ("commit", "commits"), "deploy.no-key": ("repository", "repositories"),
            "deploy.absent": ("service", "services")}
# `systemctl show` prints a timestamp as "Mon 2026-09-08 06:45:00 CEST". The date and the clock
# are read; the weekday and the zone abbreviation are not, because a zone abbreviation is
# ambiguous. A grace window absorbs the offset, so this is a heuristic and says so.
TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})")
SSH_HOST = re.compile(r"^\s*Host\s+(.+)$", re.I)
SSH_KEY = re.compile(r"^\s*IdentityFile\s+(.+)$", re.I)
SPEC_KEYS = ("timer", "path", "repo", "commit")


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one service grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def parse_spec(text):
    """`name=unit,path=/opt/x` as a dict. A spec without a unit names nothing systemd knows."""
    head, _, rest = text.partition(",")
    name, _, unit = head.partition("=")
    if not name or not unit:
        sys.exit(f"not a service spec: {text!r}. Expected name=unit[,path=...][,repo=...]")
    spec = {"name": name.strip(), "unit": unit.strip()}
    for part in rest.split(",") if rest else []:
        key, _, value = part.partition("=")
        key = key.strip()
        if key and key not in SPEC_KEYS:
            sys.exit(f"unknown field {key!r} in {text!r}. One of {', '.join(SPEC_KEYS)}")
        if key:
            spec[key] = value.strip()
    return spec


def show(unit, show_dir, timeout=10):
    """`systemctl show <unit>` as {Key: Value}, from a captured file when one is given."""
    if show_dir:
        text = None
        p = Path(show_dir) / f"{unit}.show"
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
    else:
        try:
            r = subprocess.run(["systemctl", "show", unit], capture_output=True, text=True,
                               timeout=timeout)
            text = r.stdout if r.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            text = None
    if text is None:
        return None
    out = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out.setdefault(key.strip(), value.strip())
    return out


def timestamp(value):
    """A systemd timestamp as a naive datetime, or None. The zone abbreviation is not read."""
    m = TIMESTAMP.search(value or "")
    if not m:
        return None
    try:
        return dt.datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}")
    except ValueError:
        return None


def git(repo, *args, timeout=10):
    """One git command in repo. Returns stdout, or None when git fails or takes too long."""
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                           timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def ssh_hosts(path):
    """Host aliases in an ssh config that carry an identity file. A deploy needs both."""
    hosts, current = {}, []
    for line in (read(path) or "").splitlines():
        m = SSH_HOST.match(line.split("#", 1)[0])
        if m:
            current = m.group(1).split()
            for h in current:
                hosts.setdefault(h, False)
            continue
        if current and SSH_KEY.match(line.split("#", 1)[0]):
            for h in current:
                hosts[h] = True
    return hosts


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def repo_host(url):
    """The host part of a git remote, for both `git@host:org/x` and `ssh://host/org/x`."""
    if "://" in url:
        return url.split("://", 1)[1].split("/", 1)[0].split("@")[-1].split(":")[0]
    if ":" in url:
        return url.split(":", 1)[0].split("@")[-1]
    return ""


def read_services(specs, a, now):
    """What each service says about itself. One read pass, no decisions."""
    out = []
    for spec in specs:
        s = dict(spec)
        s["show"] = show(spec["unit"], a.show_dir)
        s["timer_show"] = show(spec["timer"], a.show_dir) if spec.get("timer") else None
        path = spec.get("path", "")
        s["path_exists"] = bool(path) and (Path(a.root) / path.lstrip("/")).is_dir()
        s["head"] = ""
        s["behind"] = None
        s["commit_known"] = None
        if s["path_exists"] and spec.get("commit"):
            full = Path(a.root) / path.lstrip("/")
            s["head"] = git(full, "rev-parse", "HEAD") or ""
            s["commit_known"] = git(full, "cat-file", "-e", spec["commit"] + "^{commit}") is not None
            if s["commit_known"]:
                count = git(full, "rev-list", "--count", f"HEAD..{spec['commit']}")
                s["behind"] = int(count) if (count or "").isdigit() else None
        out.append(s)
    return out


def collect(services, rep, a, now):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    missing_state = [s for s in services if s["show"] is None]
    if missing_state:
        rep.add("INFO", "service.down",
                f"{plural(len(missing_state), 'unit')} {verb(len(missing_state), 'report')} no state, so systemd was not "
                "readable for them",
                data=[{"target": s["name"], "value": s["unit"]} for s in missing_state])
    known = [s for s in services if s["show"] is not None]

    down = [s for s in known if s["show"].get("ActiveState") not in ("active", "activating")
            and s["show"].get("ActiveState") != "failed"]
    report_count(rep, "FAIL", "service.down", down,
                 "are not running, and the standards say they should be",
                 "every service the standards name is running",
                 one="is not running, and the standards say it should be")

    failed = [s for s in known if s["show"].get("ActiveState") == "failed"
              or s["show"].get("Result", "success") not in ("success", "")]
    report_count(rep, "FAIL", "service.failed", failed,
                 "ended in a failure, so their last run did not do what it was for",
                 "no service ended in a failure",
                 one="ended in a failure, so its last run did not do what it was for")

    over = []
    for s in known:
        n = int(s["show"].get("NRestarts", "0") or 0)
        if n > a.restart_bar:
            over.append((s, n - a.restart_bar))
    if over:
        rep.add("WARN", "service.restarts",
                f"{plural(len(over), 'service')} restarted more often than the bar of "
                f"{a.restart_bar}, so something makes them fall over",
                data=[{"target": s["name"], "value": f"{s['show'].get('NRestarts')} restarts"}
                      for s, _ in over],
                measure=sum(n for _, n in over), by={s["name"]: n for s, n in over})
    elif known:
        rep.add("PASS", "service.restarts", "no service restarted more often than the bar", measure=0)

    timers = [s for s in services if s.get("timer")]
    no_state = [s for s in timers if s["timer_show"] is None]
    if no_state:
        rep.add("INFO", "timer.disabled",
                f"{plural(len(no_state), 'timer')} {verb(len(no_state), 'report')} no state",
                data=[{"target": s["name"], "value": s["timer"]} for s in no_state])
    live = [s for s in timers if s["timer_show"] is not None]
    off = [s for s in live if s["timer_show"].get("UnitFileState") != "enabled"]
    report_count(rep, "FAIL", "timer.disabled", off,
                 "are not enabled, so nothing fires them after a reboot",
                 "every timer the standards name is enabled", value=lambda s:
                 s["timer_show"].get("UnitFileState") or "no state",
                 one="is not enabled, so nothing fires it after a reboot")

    missed = []
    for s in live:
        when = timestamp(s["timer_show"].get("NextElapseUSecRealtime", ""))
        if when and (now - when).total_seconds() > a.missed_grace_seconds:
            missed.append(s)
    report_count(rep, "WARN", "timer.missed", missed,
                 "should have fired and have not, past the grace window",
                 "no timer is past its next elapse", value=lambda s:
                 s["timer_show"].get("NextElapseUSecRealtime", ""),
                 one="should have fired and has not, past the grace window")

    required = dict(pair.split("=", 1) for pair in (a.require_option or []) if "=" in pair)
    exceptions = {}
    for pair in a.exempt or []:
        unit, _, name = pair.partition(":")
        exceptions.setdefault(unit.strip(), set()).add(name.strip())
    if required and known:
        rows, by = [], {}
        for s in known:
            allowed = exceptions.get(s["unit"], set()) | exceptions.get(s["name"], set())
            gaps = [f"{k}={v}" for k, v in sorted(required.items())
                    if k not in allowed and s["show"].get(k, "") != v]
            if gaps:
                rows.append({"target": s["name"], "value": ", ".join(gaps[:3])})
                by[s["name"]] = len(gaps)
        if rows:
            rep.add("WARN", "unit.unhardened",
                    f"{plural(sum(by.values()), 'required option')} {verb(sum(by.values()), 'are', 'is')} not set on "
                    f"{plural(len(rows), 'unit')}",
                    data=rows, measure=sum(by.values()), by=by)
        else:
            rep.add("PASS", "unit.unhardened", "every required option is set on every unit", measure=0)
    elif known:
        rep.add("INFO", "unit.unhardened", "no required options are recorded, so this check is off")

    absent = [s for s in services if not s.get("path") or not s["path_exists"]]
    report_count(rep, "FAIL", "deploy.absent", absent,
                 "have no deploy path on this host, so nothing here is the code they run",
                 "every service has a deploy path that exists",
                 value=lambda s: s.get("path") or "no path recorded",
                 one="has no deploy path on this host, so nothing here is the code it runs")

    hosts = ssh_hosts(Path(a.ssh_config) if a.ssh_config else Path(a.root) / "root/.ssh/config")
    no_key = [s for s in services if s.get("repo") and not hosts.get(repo_host(s["repo"]), False)]
    report_count(rep, "WARN", "deploy.no-key", no_key,
                 "name a repository whose host has no identity file in the ssh configuration",
                 "every repository host carries an identity file",
                 value=lambda s: repo_host(s["repo"]) or s["repo"],
                 one="names a repository whose host has no identity file in the ssh configuration")

    behind = [s for s in services if s["behind"]]
    unknown = [s for s in services if s.get("commit") and s["commit_known"] is False]
    if behind:
        rep.add("WARN", "code.behind",
                f"{plural(len(behind), 'service')} {verb(len(behind), 'run')} code behind the commit the standards name",
                data=[{"target": s["name"], "value": f"{s['behind']} behind {s['commit'][:8]}"}
                      for s in behind],
                measure=sum(s["behind"] for s in behind), by={s["name"]: s["behind"] for s in behind})
    elif any(s.get("commit") for s in services):
        rep.add("PASS", "code.behind", "every deploy path is at the commit the standards name",
                measure=0)
    if unknown:
        rep.add("INFO", "code.behind",
                f"{plural(len(unknown), 'service')} {verb(len(unknown), 'name')} a commit this clone does not hold, "
                "so the distance needs a fetch first",
                data=[{"target": s["name"], "value": s["commit"][:8]} for s in unknown])
    return rep


def report_count(rep, level, cid, rows, bad, good, value=None, one=None):
    """One finding per check that simply counts services, or the passing line with a zero.

    `bad` is the sentence for several services, `one` the sentence for exactly one. A verb
    agrees with the count in front of it, and the count is not known where the sentence is written.
    """
    if rows:
        rep.add(level, cid, f"{plural(len(rows), 'service')} "
                            f"{one if len(rows) == 1 and one else bad}",
                data=[{"target": s["name"], "value": value(s) if value else s["unit"]} for s in rows],
                measure=len(rows), by={s["name"]: 1 for s in rows})
    else:
        rep.add("PASS", cid, good, measure=0)


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one unit runs, two units run."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 unit(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def cost(item):
    m = item.get("measure") or {}
    value = m.get("value")
    if value is None:
        return ""
    return "costs " + plural(value, *ROW_WORD.get(item["id"], ("finding", "findings")))


def block(rows, indent="      "):
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


def detail(item):
    return [(str(d.get("target", "")), str(d.get("value", "")) or "yes") for d in item["data"][:5]]


def text_report(services, rep, target, standards):
    """The console report: what was measured, what needs a decision, what is only a note."""
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    findings = [i for i in ranked if i["level"] in ("FAIL", "WARN")]
    notes = [i for i in ranked if i["level"] == "INFO"]
    passed = [i for i in ranked if i["level"] == "PASS"]
    out = [paint(f"availability  {target}  {plural(len(services), 'service')}", "head"),
           f"measured against  {standards}", "",
           f"{plural(len(findings), 'finding')} to decide on, "
           f"{plural(len(notes), 'note')}, {plural(len(passed), 'check')} passed"]
    for i in findings + notes:
        tag = paint("note" if i["level"] == "INFO" else f"{i['level']:<4}", i["level"])
        price = f"  ({cost(i)})" if i["level"] != "INFO" and cost(i) else ""
        out += ["", f"{tag}  {paint(i['id'], 'id')}" + paint(price, "dim"),
                f"      {i['message']}"]
        out += block(detail(i))
        if len(i["data"]) > 5:
            out.append(f"      and {len(i['data']) - 5} more, the full list is in the JSON")
    if passed:
        out += ["", paint("passed  " + ", ".join(i["id"] for i in passed), "dim")]
    if findings:
        out += ["", paint("next", "head") + "  bring back what is down before anything that is only behind, then look "
                    "each id up in the fixes table of jorekai-ops:ops for the fix per control "
                    "plane and the risk class"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--service", action="append", metavar="SPEC",
                    help="name=unit[,timer=unit][,path=DIR][,repo=URL][,commit=SHA]")
    ap.add_argument("--root", default="/", help="filesystem root every path is read under")
    ap.add_argument("--show-dir", default="", metavar="DIR",
                    help="captured `systemctl show` output, one <unit>.show file per unit")
    ap.add_argument("--ssh-config", default="")
    ap.add_argument("--require-option", action="append", metavar="NAME=VALUE",
                    help="a unit option the profile requires; without any the check is off")
    ap.add_argument("--except", dest="exempt", action="append", metavar="UNIT:NAME",
                    help="one option a named unit is allowed to miss, with the reason in standards.md")
    ap.add_argument("--restart-bar", type=int, default=3)
    ap.add_argument("--missed-grace-seconds", type=int, default=3600,
                    help="how far past its next elapse a timer may be before it counts as missed")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", default=None, metavar="YYYY-MM-DDTHH:MM:SS", help="for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    if not a.service:
        ap.error("at least one --service is required: without it nothing says what should run")
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()
    specs = [parse_spec(s) for s in a.service]
    services = read_services(specs, a, now)
    rep = collect(services, Report(), a, now)
    target = a.root if a.root != "/" else "this host"
    if a.json:
        print(json.dumps({"tool": "availability", "target": target,
                          "generated": now.date().isoformat(), "counts": rep.counts(),
                          "services": [{k: v for k, v in s.items() if k not in ("show", "timer_show")}
                                       for s in services],
                          "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        standards = (f"restarts up to {a.restart_bar}"
                     + (f" · {plural(len(a.require_option), 'required option')}"
                        if a.require_option else "")
                     + f" · timers within {a.missed_grace_seconds} seconds")
        print(text_report(services, rep, target, standards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
