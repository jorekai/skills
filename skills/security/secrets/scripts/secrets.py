#!/usr/bin/env python3
"""Credentials in the files this repository tracks, and in the history behind them.

Usage:
  secrets.py [--root DIR] [--entropy-bits N] [--history-days N] [--no-history]
             [--rotated SPEC ...] [--accept SPEC ...] [--gitleaks-file FILE] [--no-tool]
             [--now YYYY-MM-DDTHH:MM:SS] [--json]
  secrets.py --measures              the unit every check id is measured in

Three checks: a credential in a tracked file, a credential still reachable through the history
where the file no longer carries it, and a credential this pass found that carries no rotation
date. Reads files only, and never sends a value anywhere: a finding names the path, the line, the
kind, and a fingerprint, so two passes can talk about the same value without printing it.

SPEC for --rotated is `<fingerprint> <provider> YYYY-MM-DD`, for --accept
`<check id> <target> <reason> <date>`; both come from the repository's config.md.
An installed scanner is used when it is there and its findings are merged with this pass's own;
without one the pass reads the same files itself and says which coverage is missing.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import os
import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
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
MEASURES = {"cred.tracked": "count", "cred.history": "count", "cred.unrotated": "count"}
# What the number in a row counts, per check id.
ROW_WORD = {"cred.tracked": ("credential", "credentials"),
            "cred.history": ("credential", "credentials"),
            "cred.unrotated": ("finding", "findings")}
# Prefixes a provider publishes, so a match is the provider's own format and not a guess. The
# table holds patterns, never values; the finding it produces holds a fingerprint, never a value.
PROVIDERS = (
    ("github token", r"gh[pousr]_[0-9A-Za-z]{30,}"),
    ("slack token", r"xox[abprs]-[0-9A-Za-z-]{10,}"),
    ("stripe key", r"[sr]k_(live|test)_[0-9A-Za-z]{20,}"),
    ("aws access key", r"A(?:KIA|SIA)[0-9A-Z]{16}"),
    ("google api key", r"AIza[0-9A-Za-z_-]{35}"),
    ("openai key", r"sk-(?:proj-)?[0-9A-Za-z_-]{20,}"),
    ("npm token", r"npm_[0-9A-Za-z]{36}"),
    ("private key block", r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    ("json web token", r"eyJ[0-9A-Za-z_-]{10,}\.eyJ[0-9A-Za-z_-]{10,}\.[0-9A-Za-z_-]{10,}"),
)
PROVIDER_RE = [(name, re.compile(pattern)) for name, pattern in PROVIDERS]
# A name that says credential, then a value long enough to be one. The value decides, not the
# name: a short one and a placeholder are dropped below.
# The name is matched but not captured: only the credential word inside it is. A name is
# repository text, it passes no filter, and a finding names the kind and a fingerprint, never
# what the file wrote (decisions/0026).
ASSIGNMENT = re.compile(
    r"(?i)\b[a-z0-9_.-]*(?P<word>secret|token|password|passwd|pwd|api[_-]?key|access[_-]?key"
    r"|private[_-]?key|credential|auth)[a-z0-9_.-]*\s*[:=]\s*[\"']?(?P<value>[^\s\"'`,;)]{8,})")
# The shortest value the named rule accepts. A real credential is longer than a word, and the
# named rule has to carry the whole burden of being right, because a name proves nothing.
MIN_LENGTH = 16
ESCAPE = re.compile(r"\\[nrt]")
# What a value looks like when it is a stand-in for one. Any of these and the candidate is dropped.
PLACEHOLDER = re.compile(
    r"(?i)(^[$%<{]|^\.\.\.|xxx|yyy|placeholder|changeme|change_me|example|sample|dummy"
    r"|redacted|removed|your[_-]|my[_-]|test[_-]value|todo|fixme|none|null|true|false"
    r"|process\.env|os\.environ|getenv|secrets\.|vault:|env\.|\*{4,}|^/|^\./|^~|^https?:)")
# Directories nothing in a repository is authored in, so reading them costs time and finds copies.
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "target", ".venv", "venv",
             "__pycache__", ".mypy_cache", ".pytest_cache", ".next", ".tox", "coverage"}
BINARY = b"\0"
MAX_BYTES = 1_000_000
HUNK_FILE = re.compile(r"^\+\+\+ b/(.+)$")
HUNK_AT = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
COMMIT = re.compile(r"^commit ([0-9a-f]{7,40})")


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one file grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def fingerprint(value):
    """A short, stable name for a value that is never written down. Ten hexadecimal characters."""
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:10]


def entropy(value):
    """Shannon bits per character. A random token sits near five, an English word near three."""
    if not value:
        return 0.0
    counts = {}
    for c in value:
        counts[c] = counts.get(c, 0) + 1
    n = len(value)
    return -sum((k / n) * math.log2(k / n) for k in counts.values())


def classes(value):
    """How many of lower case, upper case and digit the value mixes."""
    return sum((any(c.islower() for c in value), any(c.isupper() for c in value),
                any(c.isdigit() for c in value)))


def named_value(line, bits):
    """The value behind a name that says credential, when it looks like one. Otherwise None.

    The name proves nothing on its own, so the value carries the decision: long enough, mixing at
    least two kinds of character, random enough, and not one of the stand-ins people write. A
    literal escape ends the value, because a line of source that embeds a file holds the next
    setting after it, not more of this one.
    """
    m = ASSIGNMENT.search(line)
    if not m:
        return None
    value = ESCAPE.split(m.group("value"))[0]
    if len(value) < MIN_LENGTH or classes(value) < 2:
        return None
    if PLACEHOLDER.search(value) or entropy(value) < bits:
        return None
    return f"value named by {m.group('word').lower()}", value


def candidates(line, bits):
    """Every credential-shaped value in one line, as (kind, value). The value never leaves here."""
    out = []
    for name, rx in PROVIDER_RE:
        for m in rx.finditer(line):
            out.append((name, m.group(0)))
    if not out:
        named = named_value(line, bits)
        if named:
            out.append(named)
    return out


def run_command(argv, timeout=120):
    """One command, its stdout, or None when it is missing, fails, or takes too long."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def tracked_files(root):
    """The files this repository tracks, or the tree when git cannot answer for it."""
    out = run_command(["git", "-C", str(root), "ls-files"], timeout=30)
    if out is not None:
        return [root / p for p in out.splitlines() if p.strip()], True
    found = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found += [Path(base) / n for n in names]
    return sorted(found), False


def scan_tree(root, files, bits):
    """Every candidate in the working tree. A file that is binary or large is skipped, not read."""
    out = []
    for p in files:
        try:
            if not p.is_file() or p.stat().st_size > MAX_BYTES:
                continue
            raw = p.read_bytes()
        except OSError:
            continue
        if BINARY in raw[:4096]:
            continue
        text = raw.decode("utf-8", "replace")
        for n, line in enumerate(text.splitlines(), 1):
            for kind, value in candidates(line, bits):
                out.append({"path": rel(p, root), "line": n, "kind": kind,
                            "fingerprint": fingerprint(value), "where": "tree", "commit": ""})
    return out


def scan_history(root, bits, since):
    """Candidates on lines the history added. None when git cannot walk this repository."""
    argv = ["git", "-C", str(root), "log", "--no-color", "--unified=0", "-p", "--no-merges"]
    if since:
        argv.append(f"--since={since}")
    out = run_command(argv, timeout=300)
    if out is None:
        return None
    found, path, commit, number = [], "", "", 0
    for line in out.splitlines():
        m = COMMIT.match(line)
        if m:
            commit = m.group(1)[:8]
            continue
        m = HUNK_FILE.match(line)
        if m:
            path = m.group(1)
            continue
        m = HUNK_AT.match(line)
        if m:
            number = int(m.group(1))
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for kind, value in candidates(line[1:], bits):
            found.append({"path": path, "line": number, "kind": kind,
                          "fingerprint": fingerprint(value), "where": "history", "commit": commit})
        number += 1
    return found


def dedupe(found):
    """One finding per line: two readers that saw the same line saw one credential, not two.

    Two scanners match different spans of the same value, so their fingerprints differ. The place
    is what they agree on, and the place is what a log row names.
    """
    seen, out = set(), []
    for f in found:
        key = (f["where"], f["path"], f["commit"], f["line"]) if f["line"] \
            else (f["where"], f["path"], f["commit"], f["fingerprint"])
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def from_gitleaks(data, root):
    """An installed scanner's report in this pass's shape. Only the fields every version carries."""
    out = []
    for f in data if isinstance(data, list) else []:
        # The scanner is given an absolute root and answers with absolute paths; this pass's own
        # reader answers relative to the root. The place is what deduplicates two readers, so both
        # have to write it the same way or one credential is counted twice.
        path = rel(f.get("File") or "", root)
        commit = str(f.get("Commit") or "")[:8]
        secret = str(f.get("Secret") or f.get("Match") or f.get("Fingerprint") or path)
        out.append({"path": path, "line": int(f.get("StartLine") or 0),
                    "kind": str(f.get("RuleID") or "scanner rule"),
                    "fingerprint": fingerprint(secret),
                    "where": "history" if commit else "tree", "commit": commit})
    return out


def gitleaks(root, history):
    """What an installed scanner finds, or None when it is not there or does not answer."""
    if not shutil.which("gitleaks"):
        return None
    modes = [["dir", str(root)]] + ([["git", str(root)]] if history else [])
    found = []
    with tempfile.TemporaryDirectory() as d:
        for mode in modes:
            out = Path(d) / f"{mode[0]}.json"
            run_command(["gitleaks", *mode, "--no-banner", "--redact", "--exit-code", "0",
                         "--report-format", "json", "--report-path", str(out)])
            if out.is_file():
                try:
                    found += from_gitleaks(json.loads(out.read_text(encoding="utf-8") or "[]"), root)
                except ValueError:
                    continue
    return found


def pairs(specs, fields=2):
    """The first `fields` words of every spec. The reason and the date are for a person to read."""
    out = set()
    for spec in specs or []:
        parts = spec.split()
        if len(parts) >= fields:
            out.add(tuple(parts[:fields]))
    return out


def owned(accepted):
    """The accepted entries this pass owns. One list reaches every pass, and a check id belongs to
    exactly one of them, so an entry another pass owns is not this one's to count or to name."""
    return {p for p in accepted if p[0] in MEASURES}


def collect(found, rep, a, tool_used, history_read):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    skip = owned(pairs(a.accept))
    rotated = {f for f, _ in pairs(a.rotated)}
    # Which check a value lands in is settled before anybody accepts anything. Deriving this from
    # the filtered list instead would hand an accepted tree value to `cred.history` as a finding.
    in_tree = {f["fingerprint"] for f in found if f["where"] == "tree"}
    tree = [f for f in found if f["where"] == "tree"
            and ("cred.tracked", f["path"]) not in skip]
    # A value that is in the tree is already counted there. The history check is what is left:
    # a value the tree no longer carries and every clone still holds.
    history = [f for f in found if f["where"] == "history" and f["fingerprint"] not in in_tree
               and ("cred.history", f["path"]) not in skip]

    rows, by = [], {}
    for f in tree:
        rows.append({"target": f"{f['path']}:{f['line']}", "value": f"{f['kind']}, {f['fingerprint']}"})
        by[f["path"]] = by.get(f["path"], 0) + 1
    report_rows(rep, "FAIL", "cred.tracked", rows, by,
                "stand in files this repository tracks, so every clone has them",
                "no credential stands in a tracked file",
                one="stands in a file this repository tracks, so every clone has it")

    if not history_read:
        rep.add("INFO", "cred.history",
                "the history was not read, so nothing here says whether a value is still in it")
    else:
        rows, by = [], {}
        for f in history:
            where = f"{f['path']}@{f['commit']}" if f["commit"] else f["path"]
            rows.append({"target": where, "value": f"{f['kind']}, {f['fingerprint']}"})
            by[where] = by.get(where, 0) + 1
        report_rows(rep, "FAIL", "cred.history", rows, by,
                    "are reachable through the history although the files no longer carry them",
                    "no credential is reachable through the history alone",
                    one="is reachable through the history although the file no longer carries it")

    seen, rows, by = set(), [], {}
    for f in tree + history:
        fp = f["fingerprint"]
        if fp in seen or fp in rotated:
            continue
        seen.add(fp)
        rows.append({"target": fp, "value": f"{f['kind']} in {f['path']}"})
        by[fp] = 1
    report_rows(rep, "FAIL", "cred.unrotated", rows, by,
                "carry no rotation date, so nothing says the values were replaced",
                "every credential this pass found carries a rotation date",
                one="carries no rotation date, so nothing says the value was replaced")

    if not tool_used:
        rep.add("INFO", "cred.tracked",
                "no scanner is installed, so this pass read the files with its own patterns and "
                "an entropy floor; a provider format nobody wrote down here is not covered")
    if skip:
        rep.add("INFO", "cred.tracked",
                f"{plural(len(skip), 'finding')} {verb(len(skip), 'are', 'is')} recorded as accepted "
                "and left out of the counts",
                data=[{"target": t, "value": c} for c, t in sorted(skip)])
    if rotated:
        rep.add("INFO", "cred.unrotated",
                f"{plural(len(rotated), 'value')} {verb(len(rotated), 'carry', 'carries')} a "
                "rotation date and no longer count",
                data=[{"target": f, "value": "rotated"} for f in sorted(rotated)])
    return rep


def report_rows(rep, level, cid, rows, by, bad, good, one=None):
    """One finding per check, or the passing line with a zero that settles a row."""
    if rows:
        total = sum(by.values())
        word = ROW_WORD.get(cid, ("finding", "findings"))
        rep.add(level, cid, f"{plural(total, *word)} " + (one if total == 1 and one else bad),
                data=rows, measure=total, by=by)
    else:
        rep.add("PASS", cid, good, measure=0)


def rel(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one value is, two values are."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 credential(s)"."""
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


def text_report(count, rep, target, standards):
    """The console report: what was measured, what needs a decision, what is only a note."""
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    findings = [i for i in ranked if i["level"] in ("FAIL", "WARN")]
    notes = [i for i in ranked if i["level"] == "INFO"]
    passed = [i for i in ranked if i["level"] == "PASS"]
    out = [paint(f"secrets  {target}  {plural(count, 'file')}", "head"),
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
        out += ["", paint("next", "head") + "  rotate before anything else is edited, then look "
                "each id up in the fixes table of jorekai-security:security for the fix and the gate"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repository to read")
    ap.add_argument("--entropy-bits", type=float, default=3.5,
                    help="bits per character above which a named value counts as a candidate")
    ap.add_argument("--history-days", type=int, default=0,
                    help="how far back the history is read; without it all of it")
    ap.add_argument("--no-history", action="store_true", help="read the working tree only")
    ap.add_argument("--rotated", action="append", metavar="SPEC",
                    help="`<fingerprint> <provider> YYYY-MM-DD` from config.md")
    ap.add_argument("--accept", action="append", metavar="SPEC",
                    help="`<check id> <target> <reason> <date>` from config.md, left out of the counts")
    ap.add_argument("--gitleaks-file", default="", metavar="FILE",
                    help="a captured scanner report to read instead of running one")
    ap.add_argument("--no-tool", action="store_true", help="use this pass's own patterns only")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", default=None, metavar="YYYY-MM-DDTHH:MM:SS", help="for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()
    root = Path(a.root)
    files, is_git = tracked_files(root)
    found = scan_tree(root, files, a.entropy_bits)
    history_read = False
    if not a.no_history and is_git:
        since = ""
        if a.history_days:
            since = (now - dt.timedelta(days=a.history_days)).date().isoformat()
        walked = scan_history(root, a.entropy_bits, since)
        if walked is not None:
            found += walked
            history_read = True
    tool_used = False
    if a.gitleaks_file:
        try:
            found += from_gitleaks(json.loads(Path(a.gitleaks_file).read_text(encoding="utf-8")), root)
            tool_used = True
        except (OSError, ValueError):
            tool_used = False
    elif not a.no_tool:
        reported = gitleaks(root, history_read)
        if reported is not None:
            found += reported
            tool_used = True
    rep = collect(dedupe(found), Report(), a, tool_used, history_read)
    target = Path(root).resolve().name
    if a.json:
        print(json.dumps({"tool": "secrets", "target": target,
                          "generated": now.date().isoformat(), "counts": rep.counts(),
                          "files": len(files), "history_read": history_read,
                          "scanner": tool_used, "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        standards = (f"entropy from {a.entropy_bits:g} bits"
                     + (f" · history of {a.history_days} days" if a.history_days else
                        " · the whole history" if history_read else " · no history")
                     + (" · a scanner was used" if tool_used else " · no scanner"))
        print(text_report(len(files), rep, target, standards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
