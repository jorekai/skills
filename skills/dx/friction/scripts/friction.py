#!/usr/bin/env python3
"""What the shell history says costs time: repeated sequences, failures, retries, slow commands.

Usage:
  friction.py [--history FILE ...] [--db FILE ...] [--sessions DIR ...]
              [--days N] [--min-count N] [--slow-seconds N] [--examples N] [--json]
  friction.py --measures                  the unit every check id is measured in

Every command line is redacted before it is counted and again before it is printed, so a token,
a credential flag, an address, or a home path never reaches the output. Commands are grouped by
shape (the program and its subcommand), because the shape is what repeats, not the argument.

Reads only. No network, nothing is written, no history file is modified.
Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import argparse
import collections
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

LEVEL_ORDER = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
HOME = str(Path.home())
# The unit of every check id this script measures. A measure counts what the finding costs, so
# lower is better and zero means the check no longer fires (decisions/0014). The cost of a shape
# is its runs, its failures, or the seconds it spends, never the number of shapes reported.
# `--measures` prints this table and scripts/check.sh compares it to the theme's fixes.md.
MEASURES = {"friction.repeat-command": "count", "friction.failed-command": "count",
            "friction.slow-command": "seconds", "friction.repeat-sequence": "count",
            "friction.retry-prompt": "count", "friction.agent-sessions": "count"}

# Applied in this order to every command line before it is counted or printed. The list is
# deliberately wide: a false redaction costs a less readable example, a missed one costs a secret.
REDACTIONS = [
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1<redacted>"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"), "<redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), "<redacted>"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<redacted>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "<redacted>"),
    (re.compile(r"(?i)(--?(?:password|token|secret|api[-_]?key|auth|bearer)[= ])\S+"), r"\1<redacted>"),
    (re.compile(r"(?i)\b([A-Za-z_]*(?:TOKEN|SECRET|PASSWORD|APIKEY|API_KEY)[A-Za-z_]*)=\S+"), r"\1=<redacted>"),
    (re.compile(r"(https?://)[^\s/@]+:[^\s/@]+@"), r"\1<redacted>@"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "<address>"),
    (re.compile(r"\b[0-9a-f]{32,}\b"), "<redacted>"),
    (re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"), "<redacted>"),
]
# Wrappers that say nothing about what was run.
WRAPPERS = {"sudo", "time", "command", "nohup", "env", "doas"}
# Shapes that carry no work, so counting them buries the ones that do.
TRIVIAL = {"clear", "ls", "ll", "la", "cd", "pwd", "exit", "cat", "echo", "which", "history"}
# A token stops the shape when it names a thing rather than a subcommand: a flag,
# a path, a file, a number, an assignment.
ARGUMENT = re.compile(r"^[-~$.\d]|[/=@.]")
# A history file stores a multi-line command as several lines, and the tail of one is not a
# command name. Only a plausible program name starts a shape.
PROGRAM = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]*$")


def redact(text):
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text.replace(HOME, "~")


def shape(command):
    """The program and its subcommand, which is what repeats. Arguments are dropped, not masked."""
    parts = command.strip().split()
    while parts and (parts[0] in WRAPPERS or "=" in parts[0].split("/")[-1] and parts[0].isupper()):
        parts = parts[1:]
    if not parts:
        return ""
    program = os.path.basename(parts[0])
    if not PROGRAM.match(program):
        return ""
    out = [program]
    for token in parts[1:3]:
        if ARGUMENT.search(token):
            break
        out.append(token)
    return " ".join(out)


def failed(entry):
    """A positive exit code is a failure. A negative one means the source recorded no result,
    which happens for a command that was still running when the history was written."""
    return entry.exit is not None and entry.exit > 0


class Entry:
    __slots__ = ("when", "duration", "exit", "command", "cwd", "session")

    def __init__(self, when, command, duration=None, exit_code=None, cwd="", session=""):
        self.when, self.command = when, command
        self.duration, self.exit = duration, exit_code
        self.cwd, self.session = cwd, session


def _divisor(timestamp):
    """How much a source's timestamps must be divided by to become epoch seconds.

    A history database stores milliseconds, microseconds, or nanoseconds depending on which one
    wrote it. The timestamp is the only value with a known range, so it decides the unit, and the
    duration beside it is divided by the same amount. Guessing per value turns a five minute
    command into a number with eleven digits.
    """
    if not timestamp:
        return 1
    divisor = 1
    while timestamp // divisor > 10 ** 11:
        divisor *= 1000
    return divisor


def read_db(path):
    """Any history database with a `history` table of command, timestamp, duration, exit, cwd."""
    entries = []
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = list(con.execute("select timestamp, duration, exit, command, cwd, session from history"))
        con.close()
    except sqlite3.Error:
        return entries
    divisor = _divisor(next((r[0] for r in rows if r[0]), 0))
    for when, duration, code, command, cwd, session in rows:
        entries.append(Entry(int(when) // divisor if when else None, command or "",
                             int(duration) // divisor if duration else None,
                             code, cwd or "", session or ""))
    return entries


ZSH = re.compile(r"^:\s*(\d+):(\d+);(.*)$")


def read_history_file(path):
    """A plain history file, or the extended format that prefixes a timestamp and a duration."""
    entries = []
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entries
    for line in text.splitlines():
        line = line.rstrip("\\")
        if not line.strip():
            continue
        m = ZSH.match(line)
        if m:
            entries.append(Entry(int(m.group(1)), m.group(3), int(m.group(2))))
        elif line.startswith("- cmd: "):
            entries.append(Entry(None, line[len("- cmd: "):]))
        elif not line.startswith(("#", "  when:", "  paths:", "  - ")):
            entries.append(Entry(None, line))
    return entries


def read_sessions(dirs):
    """Agent sessions as volume only: how many, where, how recent. Never their contents."""
    per_project = collections.Counter()
    newest = {}
    for d in dirs:
        base = Path(d).expanduser()
        if not base.is_dir():
            continue
        for f in base.rglob("*.jsonl"):
            project = f.parent.name
            per_project[project] += 1
            try:
                stamp = f.stat().st_mtime
            except OSError:
                continue
            newest[project] = max(newest.get(project, 0), stamp)
    return per_project, newest


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per shape, so a log row about one shape grades against that shape."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def analyse(entries, rep, min_count, slow_seconds, examples):
    shapes = collections.Counter()
    failures = collections.Counter()
    seconds = collections.Counter()
    samples = collections.defaultdict(list)
    codes = collections.defaultdict(collections.Counter)
    for e in entries:
        s = shape(e.command)
        if not s or s.split()[0] in TRIVIAL:
            continue
        shapes[s] += 1
        if e.exit is not None:
            codes[s][e.exit] += 1
        if failed(e):
            failures[s] += 1
        if e.duration:
            seconds[s] += e.duration
        if examples and len(samples[s]) < examples:
            line = redact(e.command).strip()
            if line not in samples[s]:
                samples[s].append(line)

    repeated = [{"shape": s, "count": n, "examples": samples.get(s, [])}
                for s, n in shapes.most_common(15) if n >= min_count]
    if repeated:
        rep.add("INFO", "friction.repeat-command",
                f"{len(repeated)} command shape(s) run at least {min_count} times", repeated,
                measure=sum(r["count"] for r in repeated), by={r["shape"]: r["count"] for r in repeated})
    else:
        rep.add("PASS", "friction.repeat-command", f"no command shape reaches {min_count} runs", measure=0)

    failing = [{"shape": s, "failures": n, "runs": shapes[s],
                "rate": round(100 * n / shapes[s]),
                "exit_codes": dict(codes[s].most_common(3)), "examples": samples.get(s, [])}
               for s, n in failures.most_common(10) if n >= min_count]
    if failing:
        rep.add("WARN", "friction.failed-command",
                f"{len(failing)} command shape(s) fail at least {min_count} times", failing,
                measure=sum(f["failures"] for f in failing), by={f["shape"]: f["failures"] for f in failing})
    else:
        rep.add("PASS", "friction.failed-command", "no command shape fails often enough to measure", measure=0)

    slow = [{"shape": s, "total_seconds": n, "runs": shapes[s],
             "average_seconds": round(n / shapes[s], 1)}
            for s, n in seconds.most_common(10) if n >= slow_seconds]
    if slow:
        rep.add("INFO", "friction.slow-command",
                f"{len(slow)} command shape(s) cost more than {slow_seconds} seconds in total", slow,
                measure=round(sum(x["total_seconds"] for x in slow), 1),
                by={x["shape"]: round(x["total_seconds"], 1) for x in slow})
    else:
        rep.add("PASS", "friction.slow-command", "no command shape passes the time threshold", measure=0)

    sequences(entries, rep, min_count)
    retries(entries, rep, min_count)


def sequences(entries, rep, min_count):
    """Pairs of shapes run one after the other in the same session: a script waiting to be written."""
    pairs = collections.Counter()
    by_session = collections.defaultdict(list)
    for e in entries:
        by_session[e.session].append(e)
    for group in by_session.values():
        group.sort(key=lambda e: (e.when or 0))
        previous = None
        for e in group:
            s = shape(e.command)
            if not s or s.split()[0] in TRIVIAL:
                continue
            if previous and previous != s:
                pairs[(previous, s)] += 1
            previous = s
    data = [{"first": a, "then": b, "count": n} for (a, b), n in pairs.most_common(10) if n >= min_count]
    if data:
        rep.add("INFO", "friction.repeat-sequence",
                f"{len(data)} pair(s) of commands run one after the other at least {min_count} times", data,
                measure=sum(d["count"] for d in data),
                by={f"{d['first']} then {d['then']}": d["count"] for d in data})
    else:
        rep.add("PASS", "friction.repeat-sequence", f"no command pair repeats {min_count} times", measure=0)


def retries(entries, rep, min_count, window=180):
    """The same shape run again within minutes of failing: the loop that eats an afternoon."""
    counted = collections.Counter()
    ordered = sorted((e for e in entries if e.when), key=lambda e: e.when)
    last_failure = {}
    for e in ordered:
        s = shape(e.command)
        if not s or s.split()[0] in TRIVIAL:
            continue
        previous = last_failure.get(s)
        if previous is not None and e.when - previous <= window:
            counted[s] += 1
        last_failure[s] = e.when if failed(e) else None
    data = [{"shape": s, "count": n} for s, n in counted.most_common(10) if n >= min_count]
    if data:
        rep.add("WARN", "friction.retry-prompt",
                f"{len(data)} command shape(s) get run again within minutes of failing", data,
                measure=sum(d["count"] for d in data), by={d["shape"]: d["count"] for d in data})
    else:
        rep.add("PASS", "friction.retry-prompt", "no command shape shows a retry loop", measure=0)


def text_report(rep, total, sources):
    c = rep.counts()
    out = [f"# friction: {total} command(s) from {len(sources)} source(s)",
           f"FAIL {c.get('FAIL', 0)} · WARN {c.get('WARN', 0)} · INFO {c.get('INFO', 0)} · PASS {c.get('PASS', 0)}", ""]
    for i in sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]], x["id"])):
        if i["level"] == "PASS":
            continue
        out.append(f"- **{i['level']}** `{i['id']}`: {i['message']}")
        for d in i["data"][:5]:
            if "first" in d:
                out.append(f"    - {d['count']}x: {d['first']}, then {d['then']}")
            elif "failures" in d:
                seen = ", ".join(f"exit {k} {v}x" for k, v in d.get("exit_codes", {}).items())
                out.append(f"    - {d['shape']}: {d['failures']} of {d['runs']} runs failed "
                           f"({d['rate']}%)" + (f", {seen}" if seen else ""))
            elif "total_seconds" in d:
                out.append(f"    - {d['shape']}: {d['total_seconds']}s over {d['runs']} runs "
                           f"({d['average_seconds']}s each)")
            elif "count" in d:
                out.append(f"    - {d['shape']}: {d['count']}x")
    if not any(i["level"] != "PASS" for i in rep.items):
        out.append("- nothing above the thresholds")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history", action="append", default=[], metavar="FILE")
    ap.add_argument("--db", action="append", default=[], metavar="FILE")
    ap.add_argument("--sessions", action="append", default=[], metavar="DIR")
    ap.add_argument("--days", type=int, default=90, help="only commands from the last N days")
    ap.add_argument("--min-count", type=int, default=5)
    ap.add_argument("--slow-seconds", type=int, default=60)
    ap.add_argument("--examples", type=int, default=2, help="redacted example lines per finding, 0 for none")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", type=int, default=None, help="unix seconds, for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    now = a.now if a.now is not None else int(time.time())
    cutoff = now - a.days * 86400

    entries, sources = [], []
    for f in a.db:
        got = read_db(Path(f).expanduser())
        entries += got
        sources.append({"source": str(f), "entries": len(got)})
    for f in a.history:
        got = read_history_file(Path(f).expanduser())
        entries += got
        sources.append({"source": str(f), "entries": len(got)})
    entries = [e for e in entries if e.when is None or e.when >= cutoff]

    rep = Report()
    if not entries:
        rep.add("INFO", "friction.repeat-command", "no history was readable, so nothing is measurable")
    else:
        analyse(entries, rep, a.min_count, a.slow_seconds, a.examples)

    if a.sessions:
        per_project, newest = read_sessions(a.sessions)
        data = [{"project": p, "sessions": n} for p, n in per_project.most_common(10)]
        rep.add("INFO", "friction.agent-sessions",
                f"{sum(per_project.values())} agent session(s) across {len(per_project)} project(s)", data,
                measure=sum(per_project.values()), by={d["project"]: d["sessions"] for d in data})

    if a.json:
        print(json.dumps({"tool": "friction", "target": sources, "window_days": a.days,
                          "counts": rep.counts(), "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        print(text_report(rep, len(entries), sources))
    return 0


if __name__ == "__main__":
    sys.exit(main())
