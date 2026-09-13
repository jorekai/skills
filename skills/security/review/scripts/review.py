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
import textwrap
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
# Gate 2 (decisions/0027): a fix that touches authentication, authorization, sessions, or
# cryptography needs a failing test that turns green in the same commit as the fix.
GATE2 = {"vuln.authz", "vuln.crypto"}
REQUIRED = ("id", "check", "path", "sink")
MAX_BYTES = 2_000_000
BINARY = b"\0"


class Report:
    def __init__(self):
        self.items = []
        self.incomplete = False

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per rule, so a log row about one rule grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and (measure is not None or by is not None) else None})

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
    """Where this rule is still open, and whether every matching file was read.

    Open means a file the glob matches carries the sink and does not carry the mitigation. The
    question is whether the sink is still written the way it was written when the rule was made,
    which is weaker than whether the code is safe, and it is the question a script answers twice.
    """
    hits, seen, unread = [], 0, False
    for p in sorted(Path(root).glob(rule["path"])):
        text = readable(p)
        if text is None:
            unread = True
            continue
        seen += 1
        m = rule["_sink"].search(text)
        if not m:
            continue
        if rule["_mitigation"] and rule["_mitigation"].search(text):
            continue
        line = text[:m.start()].count("\n") + 1
        hits.append(f"{rel(p, root)}:{line}")
    return hits, bool(seen) and not unread


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


def collect(rules, broken, rep, a):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    skip = owned(pairs(a.accept))
    unmeasured, open_rules, values = [], {}, {}
    for rule in rules:
        by = values.setdefault(rule["check"], {})
        if (rule["check"], rule["id"]) in skip:
            by[rule["id"]] = 0
            continue
        hits, complete = match(rule, a.root)
        if hits:
            by[rule["id"]] = 1
            open_rules.setdefault(rule["check"], []).append((rule, hits))
        elif complete:
            by[rule["id"]] = 0
        else:
            by[rule["id"]] = None
            unmeasured.append(rule)
    rep.incomplete = bool(unmeasured or broken)
    for cid in sorted(MEASURES):
        mine = [r for r in rules if r["check"] == cid]
        if not mine:
            continue
        rows, by = [], values[cid]
        # One unread rule makes the total unknown. Other rules keep their own measured values.
        total = None
        if not broken and None not in by.values():
            total = sum(by.values())
        for rule, hits in open_rules.get(cid, []):
            rows.append({"target": rule["id"], "value": f"{hits[0]}, {rule.get('why', '')}"[:90]})
        if rows:
            rep.add(LEVEL_OF[cid], cid,
                    f"{plural(len(rows), 'rule')} of this class {verb(len(rows), 'are', 'is')} "
                    f"still open: {CLASS_WORD[cid]}", data=rows, measure=total, by=by)
        elif total is None:
            rep.add("INFO", cid, "total unknown: some rules could not be checked", measure=None, by=by)
        else:
            rep.add("PASS", cid, f"every rule of this class is closed: {CLASS_WORD[cid]}", measure=0, by=by)
    if not rules:
        rep.add("INFO", "vuln.injection",
                "no rule has been written yet, so this pass measures nothing. A review that "
                "accepted a finding writes it as a rule, and this pass counts it from then on")
    if unmeasured:
        rep.add("INFO", "vuln.injection",
                f"{plural(len(unmeasured), 'rule')} could not be checked: "
                "no matching file, or a file could not be read. Check the paths listed below",
                data=[{"target": r["id"], "value": r["path"]} for r in unmeasured])
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
    """The cost of a finding as one number and one unit, the column the eye lands on."""
    m = item.get("measure") or {}
    value = m.get("value")
    if value is None:
        return ""
    return plural(value, "open rule", "open rules")


def block(rows, indent="      "):
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


def detail(item):
    return [(str(d.get("target", "")), str(d.get("value", "")) or "yes") for d in item["data"][:5]]


# The gates of this theme (references/risk-classes.md): gate 1 stands over every `cred.*` finding,
# gate 2 over a change to authentication, authorization, sessions, cryptography, or the rights a
# token carries. A gate is passed before the class applies, never after.
GATE_ONE = ("cred.",)
GATE_TWO = ("vuln.authz", "vuln.crypto", "build.token-broad")


def gate_of(cid):
    """The gate a fix for this id passes before its class applies, or an empty string."""
    return "gate 1" if cid.startswith(GATE_ONE) else ("gate 2" if cid in GATE_TWO else "")


# The report answers the questions a person asks, in the order they ask them (decisions/0031):
# what it is and how heavy it weighs stand in the list, the rest waits behind `--explain`. A report
# that prints the whole chain for every finding is a report nobody finishes.
FIXES_FILE = Path(__file__).resolve().parents[2] / "security" / "references" / "fixes.md"
FIX_ROW = re.compile(r"\|\s*`([a-z]+\.[a-z-]+)`\s*\|([^|]*)\|\s*`([a-z]+)`\s*\|\s*(\d+)\s*\|")


def load_fixes(path=None):
    """Check id to what it means, its risk class, and the rung of the ladder it sits on."""
    try:
        text = Path(path or FIXES_FILE).read_text(encoding="utf-8")
    except OSError:
        return {}
    rows = {}
    for line in text.splitlines():
        m = FIX_ROW.match(line)
        if m:
            rows[m.group(1)] = {"means": m.group(2).strip(), "class": m.group(3),
                                "rung": int(m.group(4))}
            continue
    return rows


def previous_measures(path):
    """Every measure of an earlier findings JSON, so a line can carry a direction."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {i["id"]: (i.get("measure") or {}).get("value") for i in data.get("items", [])}


def change_of(item, previous):
    """The direction since that pass: `=`, a signed number, or `new` for an id it never held."""
    now = (item.get("measure") or {}).get("value")
    if now is None:
        return "-"
    old = previous.get(item["id"])
    if old is None:
        return "new"
    return "=" if old == now else f"{now - old:+d}"


def where_of(item, width=20):
    """The first place the finding names, and how many more places the JSON holds.

    It reads the same rows the long form prints, so the column and `--explain` never disagree.
    """
    rows = detail(item)
    if not rows:
        return "-"
    more = len(item["data"]) - 1
    text = str(rows[0][0]) + (f" +{more}" if more > 0 else "")
    return text if len(text) <= width else text[:width - 2] + ".."

def ranked_findings(rep, fixes=None):
    """Findings and notes in ladder order: the rank is the address `--explain` takes.

    The rung comes from the fixes table, so one order runs through the report, the fixes table and
    `jorekai-ops:and-now`. Without that file the pass still ranks, by level and cost alone.
    """
    fixes = fixes or {}
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              fixes.get(x["id"], {}).get("rung", 9),
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    return ([i for i in ranked if i["level"] in ("FAIL", "WARN")],
            [i for i in ranked if i["level"] == "INFO"],
            [i for i in ranked if i["level"] == "PASS"])


def columns(head, rows, paints, under=None):
    """Fixed columns, padded on the plain text, painted after, so colour never moves a column."""
    under = under or {}
    widths = [max([len(h)] + [len(r[c]) for r in rows]) for c, h in enumerate(head)]
    out = [paint("  ".join(h.ljust(w) for h, w in zip(head, widths)).rstrip(), "dim")]
    indent = " " * (widths[0] + 2 + widths[1] + 2)
    for n, (row, keys) in enumerate(zip(rows, paints)):
        # The padding stays outside the escape, or a line with colour and a line without it would
        # end on a different number of spaces and the report would read differently in a pipe.
        line = "  ".join((paint(v, k) if k else v) + " " * (w - len(v))
                         for v, w, k in zip(row, widths, keys))
        out.append(line.rstrip())
        if under.get(n):
            out.append(paint(indent + under[n], "dim"))
    return out


def said(item, width=70):
    """The sentence a line with no cost carries, because a note's content is its sentence."""
    text = " ".join(item.get("message", "").split())
    return text if len(text) <= width else text[:width - 2] + ".."


def listing(findings, notes, fixes, previous):
    """One line per finding: rank, level, check, measure, change, where, class."""
    head = ["  #", "level", "check", "measure"] + (["change"] if previous is not None else []) \
        + ["where", "class"]
    rows, paints, notes_under = [], [], {}
    for n, i in enumerate(findings + notes, 1):
        level = "note" if i["level"] == "INFO" else i["level"]
        row = [f"{n:>3}", level, i["id"], cost(i) or "-"]
        keys = [None, i["level"], "id", "dim"]
        if previous is not None:
            direction = change_of(i, previous)
            row.append(direction)
            keys.append({"=": "dim", "-": "dim", "new": "WARN"}.get(direction)
                        or ("WARN" if direction.startswith("+") else "PASS"))
        row += [where_of(i), fixes.get(i["id"], {}).get("class", "-")]
        keys += ["dim", "INFO"]
        rows.append(row)
        paints.append(keys)
        # A finding without a cost has nothing in the column the eye reads, so its sentence goes
        # under it, dimmed. Every other line stays one line.
        notes_under[len(rows) - 1] = None if cost(i) else said(i)
    return columns(head, rows, paints, notes_under)


def field(label, lines, width=6, wrap=80):
    """One field of the chain: the label once, dimmed, its lines wrapped under it."""
    if not lines:
        return []
    pad = " " * (width + 2)
    flowed = []
    for line in lines:
        flowed += textwrap.wrap(line, width=wrap - len(pad), break_long_words=False,
                                break_on_hyphens=False) or [""]
    return [f"{paint(label.ljust(width), 'dim')}  {flowed[0]}"] + [pad + l for l in flowed[1:]]


def undo_line(cid, klass):
    """The way back, read from the gate and the class the id runs under (references/risk-classes.md)."""
    if cid.startswith(GATE_ONE):
        return ("a rotated value has no way back, so the record of the rotation is what closes "
                "this, never a revert of the line")
    if klass == "confirm":
        return "the dry run names every path it writes, and the copy it writes first is the way back"
    if klass == "safe":
        return "the class is safe, so the change reports what it did and setting the old value again is the way back"
    if klass == "ask":
        return "the class is ask, so nothing runs from here: the change and the test that proves it are one commit"
    return ""


def pick(ranked, which):
    """A finding by its rank in this pass or by its check id, whichever the argument holds."""
    if which.isdigit() and 1 <= int(which) <= len(ranked):
        return ranked[int(which) - 1]
    return next((i for i in ranked if i["id"] == which), None)


def explain_report(rep, target, fixes, which, previous):
    """The chain for one finding: what, weight, means, cause, fix, undo, verify."""
    findings, notes, _ = ranked_findings(rep, fixes)
    ranked = findings + notes
    item = pick(ranked, which)
    if item is None:
        return (f"no finding called {which} in this pass. The list prints a rank per finding, "
                "and --explain takes that rank or the check id.")
    n, row = ranked.index(item) + 1, fixes.get(item["id"], {})
    klass = row.get("class", "")
    out = [f"{paint(item['id'], 'head')}  {paint(f'rank {n} of {len(ranked)}', 'dim')}  "
           f"{paint('note' if item['level'] == 'INFO' else item['level'], item['level'])}  "
           f"{paint(target, 'dim')}", ""]
    out += field("what", [item["message"]])
    out += block(detail(item), indent=" " * 8)

    weight = [cost(item) or "nothing measurable", item["level"].lower()]
    if previous is not None:
        weight.append(f"change {change_of(item, previous)}")
    if gate_of(item["id"]):
        weight.append(gate_of(item["id"]))
    out += field("weight", [" · ".join(weight)])
    out += field("means", [row.get("means") or
                           "no row in the fixes table of jorekai-security:security, so nothing explains this id yet"])
    # A cause is printed only where the pass proved one. A finding that carries no signal carries
    # no line here, because a guessed cause costs more trust than it saves time.
    if item.get("cause"):
        out += field("cause", [item["cause"]])

    fix = [" · ".join(filter(None, [klass or "no class",
                                    gate_of(item["id"]),
                                    "fixes table of jorekai-security:security"]))]
    out += field("fix", fix)
    out += field("undo", [undo_line(item["id"], klass)] if undo_line(item["id"], klass) else [])
    unit = MEASURES.get(item["id"], "count")
    out += field("verify", [f"{item['id']}  0 {unit}  recomputed by this pass",
                            "the verify date goes in the log row that carries the change"])
    return "\n".join(out)


def bar(fails, warns, notes, passed):
    """Four counts in one line, a zero dimmed, a count above zero in the colour of its word."""
    cells = [(fails, "FAIL", "FAIL"), (warns, "WARN", "WARN"),
             (notes, plural(notes, "note").split()[1], "INFO"),
             (passed, "passed", "PASS")]
    return " · ".join(paint(f"{n} {word}", key if n else "dim") for n, word, key in cells)


def wrapped(label, words, width=80):
    """A dimmed list that wraps at the terminal's width, the label once."""
    lines = textwrap.wrap(", ".join(words), width=width - len(label) - 2, break_on_hyphens=False)
    indent = " " * (len(label) + 2)
    return [paint(f"{label}  {lines[0]}", "dim")] + [paint(indent + l, "dim") for l in lines[1:]]


def text_report(rules, rep, target, standards, fixes=None, previous=None):
    """The console report: what was measured, what needs a decision, what is only a note."""
    fixes = {} if fixes is None else fixes
    findings, notes, passed = ranked_findings(rep, fixes)
    fails = sum(1 for i in findings if i["level"] == "FAIL")
    out = [paint(f"review  {target}  {plural(len(rules), 'rule')}", "head"),
           f"measured against  {standards}", "",
           bar(fails, len(findings) - fails, len(notes), len(passed))]
    if findings or notes:
        out += [""] + listing(findings, notes, fixes, previous)
    if passed:
        out += [""] + wrapped("passed", [i["id"] for i in passed])
    # An open finding keeps its action and its gate even when another rule could not be checked:
    # the unread path is one more line, never a replacement for the fix the report just proved.
    if findings:
        out += ["", paint("next", "head") + "  close the sink or add the mitigation, then look "
                "each id up in the fixes table of jorekai-security:security"]
        if any(i["id"] in GATE2 for i in findings):
            out.append(paint("      gate: a failing test that turns green in the same commit "
                              "as the fix", "dim"))
        if rep.incomplete:
            out.append(paint("      check the listed rule files and paths, then rerun review "
                              "before closing any affected action", "dim"))
    elif rep.incomplete:
        out += ["", paint("next", "head") + "  check the listed rule files and paths, "
                "then rerun review before closing any affected action"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, review again when the code moves"]
    if findings or notes:
        out.append(paint("      --explain RANK prints what one line means, where it comes from, "
                         "the fix and the way back", "dim"))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repository to read")
    ap.add_argument("--rules-dir", default="", metavar="DIR",
                    help="where the rules live; without it `rules` beside the repository")
    ap.add_argument("--accept", action="append", metavar="SPEC",
                    help="`<check id> <rule id> <reason> <date>` from config.md, left out of the counts")
    ap.add_argument("--explain", default="", metavar="RANK|ID",
                    help="the chain behind one finding: what, weight, means, fix, undo, verify")
    ap.add_argument("--previous", default="", metavar="FILE",
                    help="an earlier findings JSON, which adds the change column")
    ap.add_argument("--fixes", default="", metavar="FILE",
                    help="the fixes table to read the class and the meaning from")
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
    elif a.explain:
        print(explain_report(rep, target, load_fixes(a.fixes or None), a.explain,
                             previous_measures(a.previous) if a.previous else None))
    else:
        standards = f"{plural(len(rules), 'rule')} in {folder}"
        print(text_report(rules, rep, target, standards, load_fixes(a.fixes or None),
                          previous_measures(a.previous) if a.previous else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
