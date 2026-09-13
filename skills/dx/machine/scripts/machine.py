#!/usr/bin/env python3
"""Local resources of this machine: free space, what is eating it, memory, container storage.

Usage:
  machine.py [PATH ...] [--min-free-gb N] [--large-gb N] [--reclaim-gb N]
             [--runtime NAME] [--json]
  machine.py --measures                   the unit every check id is measured in

`scaffold.py --flags` in the setup skill prints these arguments from the workspace standards.

PATH is a directory to look through for large rebuildable trees; without one only the volume,
memory, caches and the container runtime are measured. Nothing is written and nothing is removed:
this reports, and the risk class of each finding decides what may follow.

Stdlib only, no network. Exit code 0 always; findings are in the report, not the exit status.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
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
GB = 1024 ** 3
# Available memory under this percentage is a finding, and the measure is the distance to it.
MEM_FLOOR = 15
# The unit of every check id this script measures. A measure counts what the finding costs, so
# lower is better and zero means the check no longer fires (decisions/0014). Two checks read
# naturally as a benefit and are inverted here: free space becomes bytes short of the floor,
# available memory becomes percentage points below it. `--measures` prints this table and
# scripts/check.sh compares it to the unit named in the theme's fixes.md.
MEASURES = {"disk.low": "bytes", "disk.cache": "bytes", "disk.large-dir": "bytes",
            "mem.pressure": "percent", "container.reclaimable": "bytes"}
# Trees a package manager or a build rebuilds from a manifest that is already in the repository.
REBUILDABLE = {"node_modules", ".venv", "venv", "target", "build", "dist", ".next", ".nuxt",
               ".turbo", ".gradle", "__pycache__", ".pytest_cache", ".mypy_cache"}
SKIP = {".git", "Library", ".Trash", ".local/share/Trash"}
# Default locations of caches that a tool refills on its next run. Only the ones that exist
# are reported, so a path that is wrong on this machine costs nothing.
CACHES = ["~/Library/Caches", "~/.cache", "~/.npm/_cacache", "~/.yarn/cache", "~/.pnpm-store",
          "~/Library/pnpm/store", "~/.cargo/registry", "~/go/pkg/mod", "~/.gradle/caches",
          "~/.m2/repository", "~/.cache/uv", "~/.cache/pip", "~/Library/Caches/pip",
          "~/Library/Developer/Xcode/DerivedData"]
RUNTIMES = ("docker", "podman")


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one path grades against that path."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 directory(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def number(n):
    """A threshold without a trailing zero: 100 GB, not 100.0 GB."""
    return f"{n:g}"


def human(n):
    """Bytes as a short string. Exact numbers stay in the JSON."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def dir_size(path, timeout=30):
    """Size of a directory tree. Falls back to walking when the fast path is unavailable."""
    out = run(["du", "-sk", str(path)], timeout=timeout)
    if out:
        first = out.split("\t", 1)[0].strip()
        if first.isdigit():
            return int(first) * 1024
    total = 0
    for root, dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def volume(path, rep, min_free_gb):
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        rep.add("INFO", "disk.low", f"free space on {path} is not readable")
        return None
    free_gb = usage.free / GB
    # The measure is the distance to the floor, not the free space: zero means the check passes.
    short = max(0, int(min_free_gb * GB) - usage.free)
    data = [{"path": str(path), "free": usage.free, "total": usage.total, "short_of_floor": short,
             "used_percent": round(100 * usage.used / usage.total, 1) if usage.total else None}]
    if free_gb < min_free_gb:
        rep.add("FAIL", "disk.low", f"{human(usage.free)} free on {path}, below the floor of {number(min_free_gb)} GB",
                data, measure=short, by={str(path): short})
    else:
        rep.add("PASS", "disk.low", f"{human(usage.free)} free on {path}", data,
                measure=0, by={str(path): 0})
    return usage


def caches(rep, min_gb):
    found = []
    for c in CACHES:
        p = Path(c).expanduser()
        if p.is_dir():
            found.append({"path": str(p), "size": dir_size(p)})
    total = sum(f["size"] for f in found)
    found.sort(key=lambda f: -f["size"])
    by = {f["path"]: f["size"] for f in found}
    if not found:
        rep.add("PASS", "disk.cache", "no known cache directory exists here", measure=0)
    elif total >= min_gb * GB:
        rep.add("WARN", "disk.cache", f"{human(total)} in {plural(len(found), 'cache directory', 'cache directories')}, all refilled on next use",
                found, measure=total, by=by)
    else:
        rep.add("INFO", "disk.cache", f"{human(total)} in {plural(len(found), 'cache directory', 'cache directories')}, under the threshold", found,
                measure=total, by=by)


def large_dirs(paths, rep, large_gb):
    """Rebuildable trees under the given paths that are over the threshold, biggest first."""
    hits = []
    for p in paths:
        base = Path(p).expanduser()
        if not base.is_dir():
            continue
        for root, dirs, _ in os.walk(base, onerror=lambda e: None):
            keep = []
            for d in dirs:
                if d in SKIP:
                    continue
                full = Path(root) / d
                if d in REBUILDABLE:
                    size = dir_size(full)
                    if size >= large_gb * GB:
                        hits.append({"path": str(full), "size": size, "kind": d})
                    continue          # its contents are the tree we just measured
                keep.append(d)
            dirs[:] = keep
    hits.sort(key=lambda h: -h["size"])
    if not paths:
        return
    if hits:
        rep.add("WARN", "disk.large-dir",
                f"{human(sum(h['size'] for h in hits))} in {plural(len(hits), 'rebuildable tree')} over {number(large_gb)} GB",
                hits, measure=sum(h["size"] for h in hits), by={h["path"]: h["size"] for h in hits})
    else:
        rep.add("PASS", "disk.large-dir", f"no rebuildable tree over {number(large_gb)} GB", measure=0)


def memory(rep):
    system = platform.system()
    if system == "Linux":
        try:
            info = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, _, v = line.partition(":")
                info[k.strip()] = int(v.strip().split()[0]) * 1024
            total, avail = info.get("MemTotal"), info.get("MemAvailable")
        except (OSError, ValueError, IndexError):
            total = avail = None
    elif system == "Darwin":
        total_out = run(["sysctl", "-n", "hw.memsize"], timeout=5)
        stat = run(["vm_stat"], timeout=5)
        total = int(total_out.strip()) if total_out and total_out.strip().isdigit() else None
        avail = None
        if stat:
            page = 4096
            m = re.search(r"page size of (\d+) bytes", stat)
            if m:
                page = int(m.group(1))
            counts = {k.strip(): int(v.strip().rstrip(".")) for k, _, v in
                      (l.partition(":") for l in stat.splitlines() if ":" in l) if v.strip().rstrip(".").isdigit()}
            free = counts.get("Pages free", 0) + counts.get("Pages inactive", 0) + counts.get("Pages speculative", 0)
            avail = free * page
    else:
        total = avail = None
    if not total or avail is None:
        rep.add("INFO", "mem.pressure", "memory is not measurable on this system")
        return
    percent = round(100 * avail / total, 1)
    # As with free space, the measure is the distance to the floor, so zero means the check passes.
    short = round(max(0.0, MEM_FLOOR - percent), 1)
    data = [{"total": total, "available": avail, "available_percent": percent, "short_of_floor": short}]
    if percent < MEM_FLOOR:
        rep.add("WARN", "mem.pressure", f"{percent}% of memory is available ({human(avail)} of {human(total)})",
                data, measure=short)
    else:
        rep.add("PASS", "mem.pressure", f"{percent}% of memory is available", data, measure=0)


def containers(rep, reclaim_gb, named=""):
    candidates = (named,) if named else RUNTIMES
    runtime = next((r for r in candidates if shutil.which(r)), None)
    if not runtime:
        rep.add("INFO", "container.reclaimable",
                f"{named} is not installed here" if named else "no container runtime is installed here")
        return
    out = run([runtime, "system", "df", "--format", "{{json .}}"], timeout=30)
    if not out:
        rep.add("INFO", "container.reclaimable", f"{runtime} is installed but its daemon did not answer")
        return
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    # A single JSON object holding lists is the other shape the same flag produces.
    flat = []
    for r in rows:
        if isinstance(r, dict) and any(isinstance(v, list) for v in r.values()):
            for v in r.values():
                if isinstance(v, list):
                    flat += [x for x in v if isinstance(x, dict)]
        else:
            flat.append(r)
    data = [{"type": r.get("Type"), "total": r.get("TotalCount"), "active": r.get("Active"),
             "size": r.get("Size"), "reclaimable": r.get("Reclaimable")} for r in flat if r.get("Type")]
    if not data:
        rep.add("INFO", "container.reclaimable", f"{runtime} reported no storage summary")
        return
    got = " · ".join(f"{d['type']} {d['reclaimable']}" for d in data if d.get("reclaimable"))
    big = any(_gb(d.get("reclaimable")) >= reclaim_gb for d in data)
    by = {str(d["type"]): _bytes(d.get("reclaimable")) for d in data}
    rep.add("WARN" if big else "INFO", "container.reclaimable",
            f"{runtime} reports reclaimable storage: {got or 'none'}", data,
            measure=sum(by.values()), by=by)


def _bytes(text):
    """A size string as whole bytes. The runtime prints "12.3GB (40%)", the log needs a number."""
    return int(_gb(text) * GB)


def _gb(text):
    """Leading number of a size string like "12.3GB (40%)"; 0 when it says nothing."""
    if not text:
        return 0.0
    m = re.match(r"\s*([\d.]+)\s*([KMGT]?)B", str(text))
    if not m:
        return 0.0
    n = float(m.group(1))
    return n * {"": 1 / GB, "K": 1 / (1024 ** 2), "M": 1 / 1024, "G": 1.0, "T": 1024.0}[m.group(2)]


def short(path):
    """A path with the home directory written as `~`, so a line stays readable in a terminal."""
    home = str(Path.home())
    text = str(path)
    if text == home:
        return "~"
    return "~" + text[len(home):] if text.startswith(home + os.sep) else text


def cost(item):
    """The cost of a finding as one number and one unit, the column the eye lands on.
    Empty when the check carries no measure."""
    m = item.get("measure") or {}
    value, unit = m.get("value"), m.get("unit")
    if value is None:
        return ""
    if unit == "bytes":
        return human(value)
    if unit == "percent":
        return f"{value} points below the floor"
    return f"{value}"


def detail(item):
    """The rows under one finding as (name, value) pairs, at most five."""
    rows = []
    for d in item["data"][:5]:
        if "used_percent" in d:
            rows.append((short(d["path"]), f"{human(d['free'])} free of {human(d['total'])}, "
                                           f"{d['used_percent']}% used"))
        elif "available_percent" in d:
            rows.append(("this machine", f"{human(d['available'])} available of {human(d['total'])}, "
                                         f"{d['available_percent']}% of it"))
        elif "size" in d and "path" in d:
            rows.append((short(d["path"]), human(d["size"]) + (f", rebuilt by {d['kind']}" if d.get("kind") else "")))
        elif d.get("type"):
            rows.append((str(d["type"]), f"{d.get('reclaimable') or '0B'} reclaimable of "
                                         f"{d.get('size') or '0B'}, {d.get('active')} in use"))
    return rows


def block(rows, indent="      "):
    """Name and value in two aligned columns, so sizes can be compared by eye."""
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


# Unsaved work is the gate above every class here (references/risk-classes.md): while one of these
# ids reads above zero, nothing destructive runs against that repository, whatever its own class says.
UNSAVED = ("git.dirty", "git.unpushed")


# The report answers the questions a person asks, in the order they ask them (decisions/0031):
# what it is and how heavy it weighs stand in the list, the rest waits behind `--explain`. A report
# that prints the whole chain for every finding is a report nobody finishes.
FIXES_FILE = Path(__file__).resolve().parents[2] / "dx" / "references" / "fixes.md"
FIX_ROW = re.compile(r"\|\s*`([a-z]+\.[a-z-]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|\s*(\d+)\s*\|")


def load_fixes(path=None):
    """Check id to what it means, what closes it, its risk class, and the rung it sits on."""
    try:
        text = Path(path or FIXES_FILE).read_text(encoding="utf-8")
    except OSError:
        return {}
    rows = {}
    for line in text.splitlines():
        m = FIX_ROW.match(line)
        if m:
            klass = m.group(4).strip().strip("`")
            rows[m.group(1)] = {"means": m.group(2).strip(), "fix": m.group(3).strip(),
                                # A class cell that is a sentence names no single class: the table
                                # says the class differs per case, so the column stays empty.
                                "class": klass if klass.isalpha() else "",
                                "rung": int(m.group(5))}
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
    """The way back, read from the class the id runs under (references/risk-classes.md)."""
    if cid in UNSAVED:
        return "saving the work is the fix, and saved work needs no way back"
    if klass == "confirm":
        return "the dry run names every path it writes, and the copy it writes first is the way back"
    if klass == "safe":
        return "the class is safe because a tool rebuilds what it removes, so the way back is the next run"
    if klass == "ask":
        return "the class is ask, so nothing runs from here: look before you remove anything"
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
    if item["id"] in UNSAVED:
        weight.append("the gate above every class")
    out += field("weight", [" · ".join(weight)])
    out += field("means", [row.get("means") or
                           "no row in the fixes table of jorekai-dx:dx, so nothing explains this id yet"])
    # A cause is printed only where the pass proved one. A finding that carries no signal carries
    # no line here, because a guessed cause costs more trust than it saves time.
    if item.get("cause"):
        out += field("cause", [item["cause"]])

    fix = [" · ".join(filter(None, [klass or "no class",
                                    "",
                                    "fixes table of jorekai-dx:dx"]))]
    if row.get("fix"):
        fix.append(row["fix"])
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


def text_report(rep, target, floors, fixes=None, previous=None):
    """The console report: what was measured, what needs a decision, what is only a note."""
    c = rep.counts()
    fixes = {} if fixes is None else fixes
    findings, notes, passed = ranked_findings(rep, fixes)
    fails = sum(1 for i in findings if i["level"] == "FAIL")
    out = [paint(f"machine  {target}", "head"), f"measured against  {floors}", "",
           bar(fails, len(findings) - fails, len(notes), len(passed))]
    if findings or notes:
        out += [""] + listing(findings, notes, fixes, previous)
    if passed:
        out += [""] + wrapped("passed", [i["id"] for i in passed])
    if findings:
        out += ["", paint("next", "head") + "  take the largest cost first",
                paint("      gate: the fixes table of jorekai-dx:dx", "dim")]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    if c.get("FAIL"):
        out += [paint("      a FAIL outranks every WARN, whatever the totals say", "dim")]
    if findings or notes:
        out.append(paint("      --explain RANK prints what one line means, where it comes from, "
                         "the fix and the way back", "dim"))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--min-free-gb", type=float, default=20)
    ap.add_argument("--large-gb", type=float, default=1)
    ap.add_argument("--reclaim-gb", type=float, default=5)
    ap.add_argument("--runtime", default="", metavar="NAME",
                    help="the container runtime on this machine; without it the known ones are tried")
    ap.add_argument("--explain", default="", metavar="RANK|ID",
                    help="the chain behind one finding: what, weight, means, fix, undo, verify")
    ap.add_argument("--previous", default="", metavar="FILE",
                    help="an earlier findings JSON, which adds the change column")
    ap.add_argument("--fixes", default="", metavar="FILE",
                    help="the fixes table to read the class and the meaning from")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    rep = Report()
    volume(Path(a.paths[0]).expanduser() if a.paths else Path.home(), rep, a.min_free_gb)
    memory(rep)
    caches(rep, a.large_gb)
    large_dirs(a.paths, rep, a.large_gb)
    containers(rep, a.reclaim_gb, a.runtime)
    if a.json:
        print(json.dumps({"tool": "machine", "target": platform.node(), "counts": rep.counts(),
                          "items": rep.items}, indent=2, ensure_ascii=False))
    elif a.explain:
        print(explain_report(rep, platform.node(), load_fixes(a.fixes or None), a.explain,
                             previous_measures(a.previous) if a.previous else None))
    else:
        floors = (f"free space floor {number(a.min_free_gb)} GB \u00b7 memory floor {MEM_FLOOR}% \u00b7 "
                  f"trees over {number(a.large_gb)} GB \u00b7 container storage over {number(a.reclaim_gb)} GB")
        print(text_report(rep, platform.node(), floors, load_fixes(a.fixes or None),
                          previous_measures(a.previous) if a.previous else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
