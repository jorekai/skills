#!/usr/bin/env python3
"""What an accepted review finding still costs, counted from the rules that review wrote.

Usage:
  review.py [--root DIR] [--rules-dir DIR] [--accept SPEC ...] [--now YYYY-MM-DDTHH:MM:SS] [--json]
  review.py --measures              the unit every check id is measured in

A finding a model made is not reproducible on its own, and a log row needs a measure the same
script recomputes weeks later. So every accepted finding is written as a rule: where it is, the
text of the sink, and the text that would mean it is handled. This pass reads those rules and
counts the ones that are still open, per class.

A rule file holds `id`, `check`, `path` (a glob), `sink` (a regular expression), and optionally
`mitigation` (another one), `why`, `written` and `commit`. A rule is open when a file the glob
matches carries the sink and does not carry the mitigation.

Reads files only, no network. Stdlib only. Exit code 0 always; findings are in the report.
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


LEVEL_ORDER = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
# The unit of every check id this script measures. A measure counts what the finding costs, so
# lower is better and zero means the check no longer fires (decisions/0014). `--measures` prints
# this table and scripts/check.sh compares it to the unit named in the theme's fixes.md.
MEASURES = {"vuln.injection": "count", "vuln.authz": "count", "vuln.deserialize": "count",
            "vuln.ssrf": "count", "vuln.crypto": "count", "vuln.exposure": "count"}
LEVEL_OF = {"vuln.injection": "FAIL", "vuln.authz": "FAIL", "vuln.deserialize": "FAIL",
            "vuln.ssrf": "FAIL", "vuln.crypto": "FAIL", "vuln.exposure": "WARN"}
CLASS_WORD = {"vuln.injection": "input that reaches an interpreter unbound",
              "vuln.authz": "a handler without the check its neighbours carry",
              "vuln.deserialize": "untrusted data reaching a deserializer",
              "vuln.ssrf": "an outgoing request the caller aims",
              "vuln.crypto": "cryptography that does not hold",
              "vuln.exposure": "a value that reaches a log line or a response"}
REQUIRED = ("id", "check", "path", "sink")
MAX_BYTES = 2_000_000
BINARY = b"\0"


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per rule, so a log row about one rule grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def load_rules(folder):
    """Every rule file, and the reason for each one that cannot be used."""
    rules, broken = [], []
    if not folder.is_dir():
        return rules, broken
    for p in sorted(folder.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            broken.append((p.name, f"the file does not parse: {e}"))
            continue
        missing = [k for k in REQUIRED if not str(data.get(k) or "").strip()]
        if missing:
            broken.append((p.name, f"no {', '.join(missing)}"))
            continue
        if data["check"] not in MEASURES:
            broken.append((p.name, f"{data['check']} is not a check this pass measures"))
            continue
        try:
            data["_sink"] = re.compile(data["sink"])
            data["_mitigation"] = re.compile(data["mitigation"]) if data.get("mitigation") else None
        except re.error as e:
            broken.append((p.name, f"the pattern does not compile: {e}"))
            continue
        data["_file"] = p.name
        rules.append(data)
    return rules, broken


def readable(p):
    """The text of a file worth searching, or None when it is binary, large, or unreadable."""
    try:
        if not p.is_file() or p.stat().st_size > MAX_BYTES:
            return None
        raw = p.read_bytes()
    except OSError:
        return None
    if BINARY in raw[:4096]:
        return None
    return raw.decode("utf-8", "replace")


def match(rule, root):
    """Where this rule is still open, and where the file it named has gone.

    Open means a file the glob matches carries the sink and does not carry the mitigation. The
    question is whether the sink is still written the way it was written when the rule was made,
    which is weaker than whether the code is safe, and it is the question a script answers twice.
    """
    hits, seen = [], 0
    for p in sorted(Path(root).glob(rule["path"])):
        text = readable(p)
        if text is None:
            continue
        seen += 1
        m = rule["_sink"].search(text)
        if not m:
            continue
        if rule["_mitigation"] and rule["_mitigation"].search(text):
            continue
        line = text[:m.start()].count("\n") + 1
        hits.append(f"{rel(p, root)}:{line}")
    return hits, seen


def pairs(specs, fields=2):
    """The first `fields` words of every spec. The reason and the date are for a person to read."""
    out = set()
    for spec in specs or []:
        parts = spec.split()
        if len(parts) >= fields:
            out.add(tuple(parts[:fields]))
    return out


def collect(rules, broken, rep, a):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    skip = pairs(a.accept)
    gone, open_rules = [], {}
    for rule in rules:
        if (rule["check"], rule["id"]) in skip:
            continue
        hits, seen = match(rule, a.root)
        if not seen:
            gone.append(rule)
            continue
        if hits:
            open_rules.setdefault(rule["check"], []).append((rule, hits))
    for cid in sorted(MEASURES):
        mine = [r for r in rules if r["check"] == cid]
        if not mine:
            continue
        rows, by = [], {}
        for rule, hits in open_rules.get(cid, []):
            rows.append({"target": rule["id"], "value": f"{hits[0]}, {rule.get('why', '')}"[:90]})
            by[rule["id"]] = 1
        if rows:
            rep.add(LEVEL_OF[cid], cid,
                    f"{plural(len(rows), 'rule')} of this class {verb(len(rows), 'are', 'is')} "
                    f"still open: {CLASS_WORD[cid]}", data=rows, measure=len(rows), by=by)
        else:
            rep.add("PASS", cid, f"every rule of this class is closed: {CLASS_WORD[cid]}", measure=0)
    if not rules:
        rep.add("INFO", "vuln.injection",
                "no rule has been written yet, so this pass measures nothing. A review that "
                "accepted a finding writes it as a rule, and this pass counts it from then on")
    if gone:
        rep.add("INFO", "vuln.injection",
                f"{plural(len(gone), 'rule')} {verb(len(gone), 'name')} a path that matches no "
                "file today, so a person decides whether the flaw was fixed or the file moved",
                data=[{"target": r["id"], "value": r["path"]} for r in gone])
    if broken:
        rep.add("INFO", "vuln.injection",
                f"{plural(len(broken), 'rule file')} cannot be used and {verb(len(broken), 'are', 'is')} "
                "left out of every count",
                data=[{"target": name, "value": why} for name, why in broken])
    if skip:
        rep.add("INFO", "vuln.injection",
                f"{plural(len(skip), 'rule')} {verb(len(skip), 'are', 'is')} recorded as accepted "
                "and left out of the counts",
                data=[{"target": t, "value": c} for c, t in sorted(skip)])
    return rep


def rel(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one rule is, two rules are."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 rule(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def cost(item):
    m = item.get("measure") or {}
    value = m.get("value")
    if value is None:
        return ""
    return "costs " + plural(value, "open rule", "open rules")


def block(rows, indent="      "):
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


def detail(item):
    return [(str(d.get("target", "")), str(d.get("value", "")) or "yes") for d in item["data"][:5]]


def text_report(rules, rep, target, standards):
    """The console report: what was measured, what needs a decision, what is only a note."""
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    findings = [i for i in ranked if i["level"] in ("FAIL", "WARN")]
    notes = [i for i in ranked if i["level"] == "INFO"]
    passed = [i for i in ranked if i["level"] == "PASS"]
    out = [paint(f"review  {target}  {plural(len(rules), 'rule')}", "head"),
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
        out += ["", paint("next", "head") + "  a rule closes when the sink is gone or the "
                "mitigation stands anywhere in the same file, and gate 2 asks for the test "
                "that proves it"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, review again when the code moves"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repository to read")
    ap.add_argument("--rules-dir", default="", metavar="DIR",
                    help="where the rules live; without it `rules` beside the repository")
    ap.add_argument("--accept", action="append", metavar="SPEC",
                    help="`<check id> <rule id> <reason> <date>` from config.md, left out of the counts")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", default=None, metavar="YYYY-MM-DDTHH:MM:SS", help="for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()
    folder = Path(a.rules_dir) if a.rules_dir else Path(a.root) / "rules"
    rules, broken = load_rules(folder)
    rep = collect(rules, broken, Report(), a)
    target = Path(a.root).resolve().name
    if a.json:
        print(json.dumps({"tool": "review", "target": target,
                          "generated": now.date().isoformat(), "counts": rep.counts(),
                          "rules": [{"id": r["id"], "check": r["check"], "path": r["path"],
                                     "written": r.get("written", "")} for r in rules],
                          "unusable": [{"file": n, "why": w} for n, w in broken],
                          "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        standards = f"{plural(len(rules), 'rule')} in {folder}"
        print(text_report(rules, rep, target, standards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
