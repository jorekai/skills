#!/usr/bin/env python3
"""Which installed dependency carries a published advisory, and which one is already exploited.

Usage:
  deps.py [--root DIR] [--epss-floor N] [--cache-dir DIR] [--offline]
          [--accept SPEC ...] [--osv-file FILE] [--kev-file FILE] [--epss-file FILE]
          [--now YYYY-MM-DDTHH:MM:SS] [--json]
  deps.py --measures              the unit every check id is measured in

Four checks: an installed version with an advisory that a catalogue of exploited flaws names, one
with an advisory and a published fix, one with an advisory and no fix, and a manifest with no lock
file beside it. Reads the lock files, then asks the advisory database about the versions it found.

This pass needs the network, and says so in its report. `--offline` reads the cache only, and a
question the cache cannot answer carries no measure rather than a zero. Every downloaded
catalogue is cached with the date it was fetched, so a later pass says how old its answer is.

A package counts in one check only: exploited, then fixable, then the rest.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import os
import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
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
MEASURES = {"dep.known-exploited": "count", "dep.fix-available": "count",
            "dep.vulnerable": "count", "dep.unresolved": "count"}
# What the number in a row counts, per check id.
ROW_WORD = {"dep.known-exploited": ("dependency", "dependencies"),
            "dep.fix-available": ("dependency", "dependencies"),
            "dep.vulnerable": ("dependency", "dependencies"),
            "dep.unresolved": ("manifest", "manifests")}
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss"
# The lock file of each ecosystem, and the name the advisory database knows that ecosystem by.
ECOSYSTEM = {"package-lock.json": "npm", "yarn.lock": "npm", "pnpm-lock.yaml": "npm",
             "requirements.txt": "PyPI", "poetry.lock": "PyPI", "uv.lock": "PyPI",
             "Cargo.lock": "crates.io", "go.sum": "Go", "composer.lock": "Packagist",
             "Gemfile.lock": "RubyGems"}
# The manifest each lock file answers for. A manifest with none of its locks is `dep.unresolved`.
MANIFEST = {"package.json": ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"),
            "pyproject.toml": ("poetry.lock", "uv.lock", "requirements.txt"),
            "Cargo.toml": ("Cargo.lock",), "go.mod": ("go.sum",),
            "composer.json": ("composer.lock",), "Gemfile": ("Gemfile.lock",)}
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "target", ".venv", "venv",
             "__pycache__", ".mypy_cache", ".pytest_cache", ".next", ".tox"}
CVE = re.compile(r"CVE-\d{4}-\d{4,}")
BATCH = 500
TIMEOUT = 30


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one package grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def npm_lock(text):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for key, entry in (data.get("packages") or {}).items():
        if not key or not isinstance(entry, dict) or not entry.get("version"):
            continue
        name = key.split("node_modules/")[-1]
        out.append((name, str(entry["version"])))
    for name, entry in (data.get("dependencies") or {}).items():
        if isinstance(entry, dict) and entry.get("version"):
            out.append((name, str(entry["version"])))
    return out


YARN_ENTRY = re.compile(r'^"?((?:@[^/\s"]+/)?[^@\s"]+)@', re.M)
YARN_VERSION = re.compile(r'^\s+"?version"?[:\s]+"?([^"\s]+)"?', re.M)


def yarn_lock(text):
    out, name = [], ""
    for line in text.splitlines():
        if line and not line[0].isspace() and not line.startswith("#"):
            m = YARN_ENTRY.match(line)
            name = m.group(1) if m else ""
            continue
        m = YARN_VERSION.match(line)
        if m and name:
            out.append((name, m.group(1)))
            name = ""
    return out


PNPM_ENTRY = re.compile(r"^\s{2}'?/?((?:@[^/]+/)?[^/@']+)[/@]([0-9][^:'\s(]*)")


def pnpm_lock(text):
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("packages:"):
            inside = True
            continue
        if inside and line and not line[0].isspace():
            inside = False
        if not inside:
            continue
        m = PNPM_ENTRY.match(line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


REQ = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*==\s*([^\s;#]+)")


def requirements(text):
    return [(m.group(1), m.group(2)) for m in (REQ.match(l) for l in text.splitlines()) if m]


TOML_NAME = re.compile(r'^\s*name\s*=\s*"([^"]+)"')
TOML_VERSION = re.compile(r'^\s*version\s*=\s*"([^"]+)"')


def toml_packages(text):
    """`[[package]]` blocks, the shape every lock file in this family writes."""
    out, name, version, inside = [], "", "", False
    for line in text.splitlines():
        if line.strip().startswith("[["):
            if inside and name and version:
                out.append((name, version))
            inside = line.strip() in ("[[package]]", "[[packages]]")
            name, version = "", ""
            continue
        if line.strip().startswith("[") and not line.strip().startswith("[["):
            if inside and name and version:
                out.append((name, version))
            inside, name, version = False, "", ""
            continue
        if not inside:
            continue
        m = TOML_NAME.match(line)
        if m and not name:
            name = m.group(1)
        m = TOML_VERSION.match(line)
        if m and not version:
            version = m.group(1)
    if inside and name and version:
        out.append((name, version))
    return out


GO_SUM = re.compile(r"^(\S+)\s+v(\S+?)(?:/go\.mod)?\s+h1:")


def go_sum(text):
    seen = set()
    for line in text.splitlines():
        m = GO_SUM.match(line)
        if m:
            seen.add((m.group(1), "v" + m.group(2)))
    return sorted(seen)


def composer_lock(text):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for key in ("packages", "packages-dev"):
        for entry in data.get(key) or []:
            if isinstance(entry, dict) and entry.get("name") and entry.get("version"):
                out.append((entry["name"], str(entry["version"]).lstrip("v")))
    return out


GEM = re.compile(r"^\s{4}([A-Za-z0-9._-]+) \(([^)=<>~ ]+)\)$")


def gemfile_lock(text):
    return [(m.group(1), m.group(2)) for m in (GEM.match(l) for l in text.splitlines()) if m]


READERS = {"package-lock.json": npm_lock, "yarn.lock": yarn_lock, "pnpm-lock.yaml": pnpm_lock,
           "requirements.txt": requirements, "poetry.lock": toml_packages,
           "uv.lock": toml_packages, "Cargo.lock": toml_packages, "go.sum": go_sum,
           "composer.lock": composer_lock, "Gemfile.lock": gemfile_lock}


def find_files(root):
    """Every lock file and every manifest in the repository, by name."""
    locks, manifests = [], []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if n in ECOSYSTEM:
                locks.append(Path(base) / n)
            if n in MANIFEST:
                manifests.append(Path(base) / n)
    return sorted(locks), sorted(manifests)


def packages(locks, root):
    """Every installed package, as ecosystem, name and version, with the lock that named it."""
    out = {}
    for p in locks:
        reader = READERS[p.name]
        eco = ECOSYSTEM[p.name]
        for name, version in reader(read(p)):
            if name and version:
                out.setdefault((eco, name, version), rel(p, root))
    return out


def fetch(url, payload=None, timeout=TIMEOUT):
    """One request, its parsed answer, or None when the network, the service or the shape fails."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "jorekai-security"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, ValueError, OSError):
        return None


def cached(cache, name, max_age_days, now, build):
    """A catalogue from the cache, refreshed when it is older than the window. None when neither."""
    if not cache:
        return build(), ""
    path = Path(cache) / name
    age = None
    if path.is_file():
        age = (now - dt.datetime.fromtimestamp(path.stat().st_mtime)).days
        if age <= max_age_days:
            try:
                return json.loads(path.read_text(encoding="utf-8")), f"cached {age} days ago"
            except ValueError:
                pass
    fresh = build()
    if fresh is None:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8")), f"cached {age} days ago"
            except ValueError:
                return None, ""
        return None, ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fresh), encoding="utf-8")
    return fresh, "fetched today"


def osv_lookup(keys, offline):
    """Which package versions carry an advisory, and the advisory itself, keyed by package."""
    if offline:
        return None
    hits, ids = {}, set()
    ordered = list(keys)
    for start in range(0, len(ordered), BATCH):
        chunk = ordered[start:start + BATCH]
        payload = {"queries": [{"package": {"name": n, "ecosystem": e}, "version": v}
                               for e, n, v in chunk]}
        answer = fetch(OSV_BATCH, payload)
        if answer is None:
            return None
        for key, result in zip(chunk, answer.get("results") or []):
            found = [v.get("id") for v in (result.get("vulns") or []) if v.get("id")]
            if found:
                hits[key] = found
                ids.update(found)
    details = {}
    for vid in sorted(ids):
        one = fetch(OSV_VULN + vid)
        if one is not None:
            details[vid] = one
    return {"hits": {"/".join(k[:2]) + "@" + k[2]: v for k, v in hits.items()}, "vulns": details}


def kev_set(data):
    """The identifiers of the exploited-flaw catalogue, whatever shape the file was given in."""
    if isinstance(data, dict):
        return {str(v.get("cveID")) for v in data.get("vulnerabilities") or [] if v.get("cveID")}
    if isinstance(data, list):
        return {str(v) for v in data}
    return set()


def epss_scores(data):
    """The probability per identifier, from the service's answer or from a captured file."""
    out = {}
    rows = data.get("data") if isinstance(data, dict) else data
    for row in rows or []:
        if isinstance(row, dict) and row.get("cve"):
            try:
                out[str(row["cve"])] = float(row.get("epss") or 0)
            except (TypeError, ValueError):
                continue
    return out


def fixed_versions(vuln):
    """The versions an advisory names as fixed. Empty means nothing published closes it yet."""
    out = []
    for affected in vuln.get("affected") or []:
        for rng in affected.get("ranges") or []:
            for event in rng.get("events") or []:
                if event.get("fixed"):
                    out.append(str(event["fixed"]))
    return sorted(set(out))


def aliases(vuln):
    ids = [str(vuln.get("id") or "")] + [str(a) for a in vuln.get("aliases") or []]
    return {i for i in ids if CVE.fullmatch(i)}


def pairs(specs, fields=2):
    """The first `fields` words of every spec. The reason and the date are for a person to read."""
    out = set()
    for spec in specs or []:
        parts = spec.split()
        if len(parts) >= fields:
            out.add(tuple(parts[:fields]))
    return out


def classify(found, kev, epss, floor):
    """One class per package: exploited, then fixable, then the rest. Nothing is counted twice."""
    exploited, fixable, rest = {}, {}, {}
    for key, vulns in found.items():
        ids = set()
        for v in vulns:
            ids |= aliases(v)
        hot = bool(ids & kev) or any(epss.get(i, 0) >= floor for i in ids)
        fixes = [f for v in vulns for f in fixed_versions(v)]
        target = key.split("@")[0]
        if hot:
            exploited.setdefault(target, []).append(key)
        elif fixes:
            fixable.setdefault(target, []).append(key)
        else:
            rest.setdefault(target, []).append(key)
    return exploited, fixable, rest


def collect(found, manifests_open, rep, a, reached, catalogues, unasked=""):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    skip = pairs(a.accept)
    if not reached:
        rep.add("INFO", "dep.vulnerable", unasked or
                "the advisory database was not reached, so nothing here says whether an installed "
                "version carries one")
    else:
        kev, epss = catalogues
        exploited, fixable, rest = classify(found, kev, epss, a.epss_floor)
        for cid, group, bad, one in (
                ("dep.known-exploited", exploited,
                 "carry an advisory that is already being used against somebody",
                 "carries an advisory that is already being used against somebody"),
                ("dep.fix-available", fixable,
                 "carry an advisory that a published version closes",
                 "carries an advisory that a published version closes"),
                ("dep.vulnerable", rest,
                 "carry an advisory that nothing published closes yet",
                 "carries an advisory that nothing published closes yet")):
            rows, by = [], {}
            for target, keys in sorted(group.items()):
                if (cid, target) in skip:
                    continue
                rows.append({"target": target, "value": ", ".join(sorted(keys))})
                by[target] = len(keys)
            report_rows(rep, "FAIL" if cid != "dep.vulnerable" else "WARN", cid, rows, by, bad,
                        {"dep.known-exploited": "no installed version carries an advisory that is "
                                                "already being used against somebody",
                         "dep.fix-available": "no installed version has a fix waiting for it",
                         "dep.vulnerable": "no installed version carries an advisory without a fix"
                         }[cid], one=one)
        if not kev:
            rep.add("INFO", "dep.known-exploited",
                    "the catalogue of exploited flaws was not read, so this check saw only the "
                    "probability floor")

    rows, by = [], {}
    for path in manifests_open:
        if ("dep.unresolved", path) in skip:
            continue
        rows.append({"target": path, "value": "no lock file beside it"})
        by[path] = 1
    report_rows(rep, "WARN", "dep.unresolved", rows, by,
                "have no lock file beside them, so nothing says which versions are installed",
                "every manifest has a lock file beside it",
                one="has no lock file beside it, so nothing says which versions are installed")
    if skip:
        rep.add("INFO", "dep.unresolved",
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
    """The verb that agrees with a count. English inverts the s: one package is, two packages are."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 dependency(s)"."""
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
    out = [paint(f"deps  {target}  {plural(count, 'installed package')}", "head"),
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
        out += ["", paint("next", "head") + "  raise what is already being used against somebody "
                "first, then look each id up in the fixes table of jorekai-security:security"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="the repository to read")
    ap.add_argument("--epss-floor", type=float, default=0.5,
                    help="probability at or above which an advisory counts as exploited")
    ap.add_argument("--cache-dir", default="", metavar="DIR",
                    help="where the downloaded catalogues are kept, with the date they were fetched")
    ap.add_argument("--cache-days", type=int, default=7,
                    help="how old a cached catalogue may be before it is fetched again")
    ap.add_argument("--offline", action="store_true", help="read the cache only, never the network")
    ap.add_argument("--accept", action="append", metavar="SPEC",
                    help="`<check id> <target> <reason> <date>` from config.md, left out of the counts")
    ap.add_argument("--osv-file", default="", metavar="FILE",
                    help="a captured answer: `{\"<ecosystem>/<name>@<version>\": [advisory, ...]}`")
    ap.add_argument("--kev-file", default="", metavar="FILE", help="a captured exploited-flaw catalogue")
    ap.add_argument("--epss-file", default="", metavar="FILE", help="a captured probability table")
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
    locks, manifests = find_files(root)
    installed = packages(locks, root)
    # A manifest is answered by a lock file beside it, in its own directory. A lock somewhere
    # else in the tree belongs to another package of the same repository.
    beside = {}
    for p in locks:
        beside.setdefault(p.parent, set()).add(p.name)
    open_manifests = sorted(rel(m, root) for m in manifests
                            if not set(MANIFEST[m.name]) & beside.get(m.parent, set()))

    reached, found, note = False, {}, ""
    if a.osv_file:
        try:
            raw = json.loads(Path(a.osv_file).read_text(encoding="utf-8"))
            found = {k: v for k, v in raw.items()
                     if k in {"/".join(key[:2]) + "@" + key[2] for key in installed}}
            reached, note = True, "a captured answer"
        except (OSError, ValueError):
            reached = False
    elif installed:
        answer = osv_lookup(installed, a.offline)
        if answer is not None:
            found = {k: [answer["vulns"][i] for i in ids if i in answer["vulns"]]
                     for k, ids in answer["hits"].items()}
            reached, note = True, "the advisory database"
    else:
        reached, note = True, "nothing installed to ask about"
    # A manifest with nothing resolved behind it: no lock file beside it, or one in a shape these
    # readers do not cover. Nothing was asked, so the three advisory checks carry no number. A zero
    # here would settle a log row with a figure nobody took (decisions/0014); what this repository
    # costs is reported as dep.unresolved instead. A repository with no manifest at all passes.
    if manifests and not installed:
        reached, note = False, "no version was resolved, so nothing was asked"

    kev, kev_note = set(), ""
    epss, epss_note = {}, ""
    if reached:
        if a.kev_file:
            kev, kev_note = kev_set(json.loads(read(a.kev_file) or "{}")), "a captured catalogue"
        elif not a.offline or a.cache_dir:
            data, kev_note = cached(a.cache_dir, "kev.json", a.cache_days, now,
                                    lambda: None if a.offline else fetch(KEV_URL))
            kev = kev_set(data or {})
        if a.epss_file:
            epss = epss_scores(json.loads(read(a.epss_file) or "{}"))
        elif found and not a.offline:
            ids = sorted({i for vs in found.values() for v in vs for i in aliases(v)})
            if ids:
                answer = fetch(f"{EPSS_URL}?cve={','.join(ids[:100])}")
                epss = epss_scores(answer or {})
    rep = collect(found, open_manifests, Report(), a, reached, (kev, epss),
                  unasked="no version was resolved, so nothing here says whether an installed "
                          "version carries an advisory" if manifests and not installed else "")
    target = Path(root).resolve().name
    if a.json:
        print(json.dumps({"tool": "deps", "target": target,
                          "generated": now.date().isoformat(), "counts": rep.counts(),
                          "packages": len(installed), "locks": [rel(p, root) for p in locks],
                          "source": note, "catalogue": kev_note, "items": rep.items},
                         indent=2, ensure_ascii=False))
    else:
        standards = (f"{note or 'nothing asked'} · exploited from {a.epss_floor:g} probability"
                     + (f" · {kev_note}" if kev_note else ""))
        print(text_report(len(installed), rep, target, standards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
