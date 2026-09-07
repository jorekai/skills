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
    """What the finding costs now, in words. Empty when the check carries no measure."""
    m = item.get("measure") or {}
    value, unit = m.get("value"), m.get("unit")
    if value is None:
        return ""
    if unit == "bytes":
        return f"costs {human(value)}"
    if unit == "percent":
        return f"costs {value} points below the floor"
    return f"costs {value}"


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


def text_report(rep, target, floors):
    """The console report: what was measured, what needs a decision, what is only a note."""
    c = rep.counts()
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              -((x.get("measure") or {}).get("value") or 0)
                                              if (x.get("measure") or {}).get("unit") == "bytes" else 0,
                                              x["id"]))
    findings = [i for i in ranked if i["level"] in ("FAIL", "WARN")]
    notes = [i for i in ranked if i["level"] == "INFO"]
    passed = [i for i in ranked if i["level"] == "PASS"]
    out = [paint(f"machine  {target}", "head"), f"measured against  {floors}", "",
           f"{plural(len(findings), 'finding')} to decide on, "
           f"{plural(len(notes), 'note')}, {plural(len(passed), 'check')} passed"]
    for i in findings:
        tag = paint(f"{i['level']:<4}", i["level"])
        price = paint(f"  ({cost(i)})" if cost(i) else "", "dim")
        out += ["", f"{tag}  {paint(i['id'], 'id')}{price}", f"      {i['message']}"]
        out += block(detail(i))
        if len(i["data"]) > 5:
            out.append(f"      and {len(i['data']) - 5} more, the full list is in the JSON")
    for i in notes:
        out += ["", f"{paint('note', 'INFO')}  {paint(i['id'], 'id')}", f"      {i['message']}"]
        out += block(detail(i))
    if passed:
        out += ["", paint("passed  " + ", ".join(i["id"] for i in passed), "dim")]
    if findings:
        out += ["", paint("next", "head") + "  take the largest cost first, then look its id up in the fixes table "
                    "of jorekai-dx:dx for the fix and the risk class"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    if c.get("FAIL"):
        out += ["      a FAIL outranks every WARN, whatever the totals say"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--min-free-gb", type=float, default=20)
    ap.add_argument("--large-gb", type=float, default=1)
    ap.add_argument("--reclaim-gb", type=float, default=5)
    ap.add_argument("--runtime", default="", metavar="NAME",
                    help="the container runtime on this machine; without it the known ones are tried")
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
    else:
        floors = (f"free space floor {number(a.min_free_gb)} GB \u00b7 memory floor {MEM_FLOOR}% \u00b7 "
                  f"trees over {number(a.large_gb)} GB \u00b7 container storage over {number(a.reclaim_gb)} GB")
        print(text_report(rep, platform.node(), floors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
