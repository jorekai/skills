#!/usr/bin/env python3
"""What the forge runs with this repository's own rights, and what those rights allow.

Usage:
  pipeline.py [--root DIR] [--workflow-dir DIR] [--trusted-owner OWNER ...] [--accept SPEC ...]
              [--now YYYY-MM-DDTHH:MM:SS] [--json]
  pipeline.py --measures              the unit every check id is measured in

Five checks over the workflow files a repository commits: a privileged trigger that checks out
code from a fork, a shell step that puts a context value straight into the command line, a
workflow that names no rights for its token or grants a broad one, a third-party action bound to
a tag rather than to a commit, and a self-hosted runner a trigger from outside can reach. Reads
files only: nothing is run, nothing is fetched, no workflow is triggered.

SPEC for --accept is `<check id> <target> <reason> <date>`; only the first two fields are read.
The reader parses the subset of the format these checks need. A file it cannot read is reported
as unread, never as clean.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
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
MEASURES = {"build.untrusted-checkout": "count", "build.script-injection": "count",
            "build.token-broad": "count", "build.action-unpinned": "count",
            "build.runner-exposed": "count"}
# What the number in a row counts, per check id.
ROW_WORD = {"build.untrusted-checkout": ("workflow", "workflows"),
            "build.script-injection": ("step", "steps"),
            "build.token-broad": ("workflow", "workflows"),
            "build.action-unpinned": ("action reference", "action references"),
            "build.runner-exposed": ("workflow", "workflows")}
# A trigger that runs in the repository's own context, with its secrets and its token, while the
# event that started it was raised by somebody who needs no write access.
PRIVILEGED = ("pull_request_target", "workflow_run")
# A commit sha is forty hexadecimal characters. Everything else a `uses` can carry moves.
SHA = re.compile(r"^[0-9a-f]{40}$")
EXPRESSION = re.compile(r"\$\{\{(.+?)\}\}", re.S)
# Context values an outsider writes. An input to a manual run is not here: starting one already
# needs write access, so it is trusted the way an environment variable is.
UNTRUSTED = (
    r"github\.event\.issue\.(title|body)",
    r"github\.event\.pull_request\.(title|body)",
    r"github\.event\.pull_request\.head\.(ref|label)",
    r"github\.event\.pull_request\.head\.repo\.[a-z_.]+",
    r"github\.event\.(comment|review|review_comment)\.body",
    r"github\.event\.discussion\.(title|body)",
    r"github\.event\.discussion_comment\.body",
    r"github\.event\.head_commit\.(message|author\.(name|email))",
    r"github\.event\.commits\[[^]]*\]\.(message|author\.(name|email))",
    r"github\.head_ref",
    r"github\.event\.workflow_run\.head_branch",
)
UNTRUSTED_RE = re.compile("|".join(UNTRUSTED))
# What a checkout has to be given before it holds the fork's code rather than the base branch.
FORK_REF = re.compile(
    r"github\.event\.pull_request\.head\.(sha|ref)|github\.head_ref"
    r"|github\.event\.pull_request\.merge_commit_sha"
    r"|github\.event\.workflow_run\.head_(sha|branch)|refs/pull/")
CHECKOUT = re.compile(r"^actions/checkout@")
# A trigger somebody outside this repository can raise: opening or updating a pull request, a
# comment, a review, a discussion, or a run this one watches. `push` and a manual run are not
# here, because both already need write access, the same bar a self-hosted runner needs cleared
# (GitHub docs, security-hardening-for-github-actions, `references/sources.md`).
EXTERNAL = ("pull_request", "pull_request_target", "pull_request_review",
            "pull_request_review_comment", "issue_comment", "issues", "discussion",
            "discussion_comment", "workflow_run")
# A permissions value that grants every scope at once rather than naming the ones a job needs.
BROAD_PERMISSIONS = ("write-all", "write")


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


def triggers(workflow):
    """The events that start this workflow, whatever shape `on` was written in."""
    on = workflow.get("on")
    if isinstance(on, str):
        return [on]
    if isinstance(on, list):
        return [str(x) for x in on]
    if isinstance(on, dict):
        return list(on)
    return []


def steps_of(workflow):
    """Every step of every job, as (job id, index, step). A job without steps yields nothing."""
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for i, step in enumerate(job.get("steps") or []):
            if isinstance(step, dict):
                yield job_id, i, step


def read_workflows(folder):
    """Every workflow file, parsed. A file that does not parse carries its reason instead."""
    out = []
    if not folder.is_dir():
        return out
    for p in sorted(folder.iterdir()):
        if p.suffix not in (".yml", ".yaml") or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            out.append({"path": p, "data": None, "why": str(e)})
            continue
        try:
            data = parse_yaml(text)
        except Unsupported as e:
            out.append({"path": p, "data": None, "why": str(e)})
            continue
        out.append({"path": p, "data": data if isinstance(data, dict) else {}, "why": ""})
    return out


def accepted_pairs(specs):
    """`check id` and `target` of every accepted entry. The reason and the date are for a person."""
    out = set()
    for spec in specs or []:
        parts = spec.split()
        if len(parts) >= 2:
            out.add((parts[0], parts[1]))
    return out


def owned(accepted):
    """The accepted entries this pass owns. One list reaches every pass, and a check id belongs to
    exactly one of them, so an entry another pass owns is not this one's to count or to name."""
    return {p for p in accepted if p[0] in MEASURES}


def action_refs(workflow):
    """Every `uses` in the file, from a step and from a job that calls another workflow."""
    jobs = workflow.get("jobs")
    if isinstance(jobs, dict):
        for job_id, job in jobs.items():
            if isinstance(job, dict) and isinstance(job.get("uses"), str):
                yield job_id, job["uses"]
    for job_id, i, step in steps_of(workflow):
        if isinstance(step.get("uses"), str):
            yield f"{job_id}#{i + 1}", step["uses"]


def unpinned(ref, trusted):
    """Whether this reference can change under the repository without anybody deciding."""
    if ref.startswith(("./", "../", ".\\")):
        return False                      # an action in this repository is this repository
    if ref.startswith("docker://"):
        return False                      # a different question with a different fix
    owner, _, rest = ref.partition("/")
    if owner in trusted:
        return False
    name, sep, version = rest.partition("@")
    if not sep:
        return True                       # no version at all moves with every push
    return not SHA.fullmatch(version.strip())


def broad_permissions(value):
    """Whether this `permissions` value grants every scope rather than naming them."""
    return isinstance(value, str) and value.strip().lower() in BROAD_PERMISSIONS


def settled_permissions(data):
    """Whether this workflow names narrow rights for its token everywhere it names any.

    A job's `permissions` overrides the top-level block for that job, so a narrow top level with
    one broad job is not settled, and a missing top level needs every job to carry a narrow one.
    """
    jobs = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
    top = data.get("permissions")
    if top is not None:
        return not broad_permissions(top) and not any(
            isinstance(j, dict) and broad_permissions(j.get("permissions")) for j in jobs.values())
    if not jobs:
        return False
    return all(isinstance(j, dict) and j.get("permissions") is not None
              and not broad_permissions(j.get("permissions")) for j in jobs.values())


def broad_grant(data):
    """Whether this workflow's token gets a broad grant somewhere, top level or in a job."""
    jobs = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
    return broad_permissions(data.get("permissions")) or any(
        isinstance(j, dict) and broad_permissions(j.get("permissions")) for j in jobs.values())


def self_hosted(runs_on):
    """Whether this `runs-on` value names a self-hosted runner rather than one GitHub hosts."""
    if isinstance(runs_on, str):
        values = [runs_on]
    elif isinstance(runs_on, list):
        values = [str(v) for v in runs_on]
    elif isinstance(runs_on, dict):
        values = [str(v) for v in (runs_on.get("labels") or [])]
    else:
        return False
    return any(v.strip().lower() == "self-hosted" for v in values)


def collect(files, rep, a):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    skip = owned(accepted_pairs(a.accept))
    trusted = set(a.trusted_owner or [])
    unread = [f for f in files if f["data"] is None]
    if unread:
        rep.add("INFO", "build.token-broad",
                f"{plural(len(unread), 'workflow file')} could not be read, so nothing here "
                "counts them as clean",
                data=[{"target": rel(f["path"], a.root), "value": f["why"]} for f in unread])
    read = [f for f in files if f["data"] is not None]
    if not read:
        rep.add("INFO", "build.token-broad",
                "no workflow file was read, so this pass measures nothing about the pipeline")
        return rep

    rows, by = [], {}
    for f in read:
        name = rel(f["path"], a.root)
        if ("build.untrusted-checkout", name) in skip:
            continue
        events = [t for t in triggers(f["data"]) if t in PRIVILEGED]
        if not events:
            continue
        for job_id, i, step in steps_of(f["data"]):
            uses = step.get("uses") or ""
            with_ = step.get("with") if isinstance(step.get("with"), dict) else {}
            ref = " ".join(str(v) for v in with_.values())
            if CHECKOUT.match(str(uses)) and FORK_REF.search(ref):
                rows.append({"target": name, "value": f"{events[0]} then {job_id} checks out the fork"})
                by[name] = by.get(name, 0) + 1
                break
    report_rows(rep, "FAIL", "build.untrusted-checkout", rows, by,
                "run with this repository's rights and check out code from a fork",
                "no privileged workflow checks out code from a fork",
                one="runs with this repository's rights and checks out code from a fork")

    rows, by = [], {}
    for f in read:
        name = rel(f["path"], a.root)
        if ("build.script-injection", name) in skip:
            continue
        for job_id, i, step in steps_of(f["data"]):
            run = step.get("run")
            if not isinstance(run, str):
                continue
            hits = [m.group(1).strip() for m in EXPRESSION.finditer(run)
                    if UNTRUSTED_RE.search(m.group(1))]
            if hits:
                rows.append({"target": f"{name}#{job_id}", "value": hits[0][:60]})
                by[f"{name}#{job_id}"] = by.get(f"{name}#{job_id}", 0) + 1
    report_rows(rep, "FAIL", "build.script-injection", rows, by,
                "put a value somebody outside writes straight into the command line",
                "no shell step interpolates a value from outside",
                one="puts a value somebody outside writes straight into the command line")

    rows, by, broad_seen = [], {}, False
    for f in read:
        name = rel(f["path"], a.root)
        if ("build.token-broad", name) in skip:
            continue
        if settled_permissions(f["data"]):
            continue
        broad = broad_grant(f["data"])
        rows.append({"target": name,
                    "value": "grants a broad permission" if broad else "no permissions block"})
        by[name] = 1
        broad_seen = broad_seen or broad
    report_rows(rep, "FAIL" if broad_seen else "WARN", "build.token-broad", rows, by,
                "carry no explicit rights or grant a broad one, so their token can write more than it needs",
                "every workflow names narrow rights for its token",
                one="carries no explicit rights or grants a broad one, so its token can write more than it needs")

    rows, by = [], {}
    for f in read:
        name = rel(f["path"], a.root)
        if ("build.runner-exposed", name) in skip:
            continue
        events = [t for t in triggers(f["data"]) if t in EXTERNAL]
        if not events:
            continue
        jobs = f["data"].get("jobs") if isinstance(f["data"].get("jobs"), dict) else {}
        hit = next((job_id for job_id, job in jobs.items()
                   if isinstance(job, dict) and self_hosted(job.get("runs-on"))), "")
        if hit:
            rows.append({"target": name,
                        "value": f"{events[0]} then {hit} runs on a self-hosted runner"})
            by[name] = by.get(name, 0) + 1
    report_rows(rep, "FAIL", "build.runner-exposed", rows, by,
                "run on a self-hosted runner although a trigger reachable from outside can start them",
                "no workflow reachable from outside runs on a self-hosted runner",
                one="runs on a self-hosted runner although a trigger reachable from outside can start it")

    rows, by = [], {}
    for f in read:
        name = rel(f["path"], a.root)
        if ("build.action-unpinned", name) in skip:
            continue
        for where, ref in action_refs(f["data"]):
            if unpinned(ref, trusted):
                rows.append({"target": name, "value": f"{ref} in {where}"})
                by[name] = by.get(name, 0) + 1
    report_rows(rep, "WARN", "build.action-unpinned", rows, by,
                "name a version that can change without anybody deciding",
                "every third-party action is bound to a commit",
                one="names a version that can change without anybody deciding")
    if skip:
        rep.add("INFO", "build.token-broad",
                f"{plural(len(skip), 'finding')} {verb(len(skip), 'are', 'is')} recorded as accepted "
                "and left out of the counts",
                data=[{"target": t, "value": c} for c, t in sorted(skip)])
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
    """The verb that agrees with a count. English inverts the s: one file is, two files are."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 workflow(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def cost(item):
    """The cost of a finding as one number and one unit, the column the eye lands on."""
    m = item.get("measure") or {}
    value = m.get("value")
    if value is None:
        return ""
    return plural(value, *ROW_WORD.get(item["id"], ("finding", "findings")))


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


def text_report(files, rep, target, standards, fixes=None, previous=None):
    """The console report: what was measured, what needs a decision, what is only a note."""
    fixes = {} if fixes is None else fixes
    findings, notes, passed = ranked_findings(rep, fixes)
    fails = sum(1 for i in findings if i["level"] == "FAIL")
    out = [paint(f"pipeline  {target}  {plural(len(files), 'workflow file')}", "head"),
           f"measured against  {standards}", "",
           bar(fails, len(findings) - fails, len(notes), len(passed))]
    if findings or notes:
        out += [""] + listing(findings, notes, fixes, previous)
    if passed:
        out += [""] + wrapped("passed", [i["id"] for i in passed])
    if findings:
        out += ["", paint("next", "head") + "  close what lets somebody else run code here before "
                "what only widens a token, then look each id up in the fixes table of "
                "jorekai-security:security for the fix and the risk class"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    if findings or notes:
        out.append(paint("      --explain RANK prints what one line means, where it comes from, "
                         "the fix and the way back", "dim"))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repository to read")
    ap.add_argument("--workflow-dir", default="", metavar="DIR",
                    help="where the workflow files are; without it the forge's usual folder")
    ap.add_argument("--trusted-owner", action="append", metavar="OWNER",
                    help="an owner as trusted as this repository, so its actions need no commit pin")
    ap.add_argument("--accept", action="append", metavar="SPEC",
                    help="`<check id> <target> <reason> <date>` from config.md, left out of the counts")
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
    folder = Path(a.workflow_dir) if a.workflow_dir else Path(a.root) / ".github" / "workflows"
    files = read_workflows(folder)
    rep = collect(files, Report(), a)
    target = rel(Path(a.root), Path(a.root).parent) if a.root != "." else Path.cwd().name
    if a.json:
        print(json.dumps({"tool": "pipeline", "target": target,
                          "generated": now.date().isoformat(), "counts": rep.counts(),
                          "workflows": [{"path": rel(f["path"], a.root),
                                         "read": f["data"] is not None, "why": f["why"]}
                                        for f in files],
                          "items": rep.items}, indent=2, ensure_ascii=False))
    elif a.explain:
        print(explain_report(rep, target, load_fixes(a.fixes or None), a.explain,
                             previous_measures(a.previous) if a.previous else None))
    else:
        trusted = ", ".join(a.trusted_owner or []) or "no owner"
        kept = owned(accepted_pairs(a.accept))
        standards = f"{trusted} trusted without a pin · {plural(len(kept), 'accepted finding')}"
        print(text_report(files, rep, target, standards, load_fixes(a.fixes or None),
                          previous_measures(a.previous) if a.previous else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
