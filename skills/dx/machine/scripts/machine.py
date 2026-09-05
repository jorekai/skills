#!/usr/bin/env python3
"""Local resources of this machine: free space, what is eating it, memory, container storage.

Usage:
  machine.py [PATH ...] [--min-free-gb N] [--large-gb N] [--reclaim-gb N] [--json]

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

LEVEL_ORDER = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
GB = 1024 ** 3
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

    def add(self, level, cid, message, data=None):
        self.items.append({"id": cid, "level": level, "message": message, "data": data or []})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


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
    data = [{"path": str(path), "free": usage.free, "total": usage.total,
             "used_percent": round(100 * usage.used / usage.total, 1) if usage.total else None}]
    if free_gb < min_free_gb:
        rep.add("FAIL", "disk.low", f"{human(usage.free)} free on {path}, below the floor of {min_free_gb} GB", data)
    else:
        rep.add("PASS", "disk.low", f"{human(usage.free)} free on {path}", data)
    return usage


def caches(rep, min_gb):
    found = []
    for c in CACHES:
        p = Path(c).expanduser()
        if p.is_dir():
            found.append({"path": str(p), "size": dir_size(p)})
    total = sum(f["size"] for f in found)
    found.sort(key=lambda f: -f["size"])
    if not found:
        rep.add("PASS", "disk.cache", "no known cache directory exists here")
    elif total >= min_gb * GB:
        rep.add("WARN", "disk.cache", f"{human(total)} in {len(found)} cache directory(s), all refilled on next use", found)
    else:
        rep.add("INFO", "disk.cache", f"{human(total)} in {len(found)} cache directory(s)", found)


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
                f"{human(sum(h['size'] for h in hits))} in {len(hits)} rebuildable tree(s) over {large_gb} GB", hits)
    else:
        rep.add("PASS", "disk.large-dir", f"no rebuildable tree over {large_gb} GB")


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
    data = [{"total": total, "available": avail, "available_percent": percent}]
    if percent < 15:
        rep.add("WARN", "mem.pressure", f"{percent}% of memory is available ({human(avail)} of {human(total)})", data)
    else:
        rep.add("PASS", "mem.pressure", f"{percent}% of memory is available", data)


def containers(rep, reclaim_gb):
    runtime = next((r for r in RUNTIMES if shutil.which(r)), None)
    if not runtime:
        rep.add("INFO", "container.reclaimable", "no container runtime is installed here")
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
    rep.add("WARN" if big else "INFO", "container.reclaimable",
            f"{runtime} reports reclaimable storage: {got or 'none'}", data)


def _gb(text):
    """Leading number of a size string like "12.3GB (40%)"; 0 when it says nothing."""
    if not text:
        return 0.0
    m = re.match(r"\s*([\d.]+)\s*([KMGT]?)B", str(text))
    if not m:
        return 0.0
    n = float(m.group(1))
    return n * {"": 1 / GB, "K": 1 / (1024 ** 2), "M": 1 / 1024, "G": 1.0, "T": 1024.0}[m.group(2)]


def text_report(rep):
    c = rep.counts()
    out = [f"# machine: {platform.system()}",
           f"FAIL {c.get('FAIL', 0)} · WARN {c.get('WARN', 0)} · INFO {c.get('INFO', 0)} · PASS {c.get('PASS', 0)}", ""]
    for i in sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]], x["id"])):
        if i["level"] == "PASS":
            continue
        out.append(f"- **{i['level']}** `{i['id']}`: {i['message']}")
        for d in i["data"][:5]:
            if "size" in d and "path" in d:
                out.append(f"    - {d['path']}: {human(d['size'])}")
        if len(i["data"]) > 5:
            out.append(f"    - and {len(i['data']) - 5} more, full list in the JSON")
    if not any(i["level"] != "PASS" for i in rep.items):
        out.append("- nothing open")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--min-free-gb", type=float, default=20)
    ap.add_argument("--large-gb", type=float, default=1)
    ap.add_argument("--reclaim-gb", type=float, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = Report()
    volume(Path(a.paths[0]).expanduser() if a.paths else Path.home(), rep, a.min_free_gb)
    memory(rep)
    caches(rep, a.large_gb)
    large_dirs(a.paths, rep, a.large_gb)
    containers(rep, a.reclaim_gb)
    if a.json:
        print(json.dumps({"tool": "machine", "target": platform.node(), "counts": rep.counts(),
                          "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        print(text_report(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
