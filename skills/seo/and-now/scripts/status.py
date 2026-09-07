#!/usr/bin/env python3
"""Where a domain stands in the SEO loop, read from docs/seo/<domain>/ alone, and what comes next.

Usage:
  status.py [--root docs/seo] [DOMAIN ...] [--today YYYY-MM-DD]

No argument: every domain folder under --root. Reads config, connections, strategy, glossary,
the newest audits/*.json, the log tables, exports/, briefs/, drafts/. Never touches the network.
Stdlib only. Exit code 2 when the root or a named domain folder does not exist.
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


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^-\s*([A-Za-z_]+):\s*(.*)$")
EXPORT_MAX_AGE = 7          # days; the loop is weekly
TECH_VERIFY_DAYS = 14


def week_of(day):
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def value(text, key):
    """Value of `- key: ...`; blank when empty or still the template's parenthesised hint."""
    for line in text.splitlines():
        m = KEY_RE.match(line.strip())
        if m and m.group(1).lower() == key.lower():
            v = m.group(2).strip()
            return "" if not v or v.startswith("(") else v
    return ""


def filled(path, marker):
    """A workspace file counts as filled once it holds anything beyond the template's instruction text."""
    if not path.exists():
        return False
    body = path.read_text(encoding="utf-8")
    return marker not in body


def split_cells(line):
    """Markdown table cells; `\\|` inside a cell is an escaped pipe, not a separator.
    Duplicated from setup/scripts/scaffold.py on purpose: each skill stays standalone."""
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table_rows(text, heading):
    if heading not in text:
        return []
    section = text.split(heading, 1)[1]
    lines = [l for l in section.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    head = [c.strip().lower() for c in split_cells(lines[0])]
    rows = []
    for line in lines[2:]:
        cells = split_cells(line)
        if len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    return rows


def plural(n, word):
    """"1 day", "2 days"."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def file_date(p):
    m = DATE_RE.search(p.name)
    return dt.date.fromisoformat(m.group(1)) if m else dt.date.fromtimestamp(p.stat().st_mtime)


def natural(name):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", name)]


def latest(paths):
    """Newest by the date in the name, then by name (tech-verify3 after tech-verify2 after tech)."""
    paths = list(paths)
    return max(paths, key=lambda p: (file_date(p), natural(p.stem))) if paths else None


def read_domain(base, today):
    s = {"domain": base.name}
    cfg = base / "config.md"
    s["config"] = cfg.exists() and _config_edited(cfg)
    conn = (base / "connections.md")
    ctext = conn.read_text(encoding="utf-8") if conn.exists() else ""
    s["connections"] = {k: value(ctext, k) for k in
                        ("GSC_PROPERTY", "SITEMAP_SUBMITTED_AT", "BING_IMPORTED_AT", "INDEXNOW_TESTED_AT")}
    s["strategy"] = filled(base / "strategy.md", "One paragraph: what the site sells")
    s["glossary"] = filled(base / "glossary.md", "**Term**:")

    audit = latest(p for p in (base / "audits").glob("*.json") if p.is_file()) if (base / "audits").is_dir() else None
    s["audit"] = None
    if audit:
        try:
            data = json.loads(audit.read_text(encoding="utf-8"))
            counts = data.get("counts", {})
            fails = sorted({i.get("id", "?") for i in data.get("items", []) if i.get("level") == "FAIL"})
            s["audit"] = {"file": audit.name, "fail": int(counts.get("FAIL", 0)),
                          "warn": int(counts.get("WARN", 0)), "fail_ids": fails}
        except (ValueError, AttributeError):
            s["audit"] = {"file": audit.name, "fail": None, "warn": None, "fail_ids": []}

    rows, sources = [], []
    for f in sorted((base / "log").glob("*.md")) if (base / "log").is_dir() else []:
        text = f.read_text(encoding="utf-8")
        sources += [l.split(":", 1)[1].strip() for l in text.splitlines() if l.startswith("Source:")]
        for r in table_rows(text, "## Actions"):
            r["_file"] = f.name
            rows.append(r)
    s["rows"] = rows
    s["todo"] = [r for r in rows if r.get("status") == "todo"]
    s["due"] = [r for r in rows if r.get("status") in ("applied", "verify") and ISO_DATE.match(r.get("verify after", ""))
                and dt.date.fromisoformat(r["verify after"]) <= today]
    future = [dt.date.fromisoformat(r["verify after"]) for r in rows if r.get("status") in ("applied", "verify")
              and ISO_DATE.match(r.get("verify after", "")) and dt.date.fromisoformat(r["verify after"]) > today]
    s["next_verify"] = min(future) if future else None
    s["log_sources"] = sources          # in file order, so the last one is the newest week's
    s["log_source"] = " ".join(sources)

    exports = [p for p in (base / "exports").iterdir() if p.is_file() and p.suffix in (".zip", ".csv")] \
        if (base / "exports").is_dir() else []
    s["export"] = latest(exports)
    # <slug>.review.md is the jorekai-seo:review report, not a brief waiting for a draft.
    s["briefs"] = sorted(p.stem for p in (base / "briefs").glob("*.md")
                         if not p.name.endswith(".review.md")) if (base / "briefs").is_dir() else []
    s["drafts"] = sorted(p.stem for p in (base / "drafts").glob("*.md")) if (base / "drafts").is_dir() else []
    s["reports"] = sorted(p.stem for p in (base / "reports").glob("*.md")) if (base / "reports").is_dir() else []
    return s


def _config_edited(cfg):
    """config.md differs from the template once at least one key beyond canonical_host has a value."""
    text = cfg.read_text(encoding="utf-8")
    keys = [m.group(1) for m in (KEY_RE.match(l.strip()) for l in text.splitlines()) if m]
    return any(value(text, k) for k in keys if k != "canonical_host")


def decide(s, today):
    """Stage and the ordered list of next steps. Every step names the skill and what it writes."""
    now, then = [], []
    c = s["connections"]
    if not s["config"]:
        return "setup", ["`jorekai-seo:setup`: fill config.md (canonical host, framework, sitemap, brand_regex, CTR calibration)"], then
    # Unfinished setup is an item, never a gate: a folder with an audit or log rows is in the loop,
    # and hiding its open work behind the wizard is how a workspace stalls unseen.
    setup_open = []
    if not c["GSC_PROPERTY"] or not c["SITEMAP_SUBMITTED_AT"]:
        setup_open.append("`jorekai-seo:connect`: Search Console property and sitemap submission are not recorded in connections.md")
    if not s["strategy"] or not s["glossary"]:
        setup_open.append("`jorekai-seo:grill`: strategy.md and glossary.md are still the template")
    a = s["audit"]
    started = bool(a or s["rows"] or s["briefs"] or s["drafts"])
    if setup_open and not started:
        return "setup", setup_open, then
    if a is None:
        return "audit", setup_open + ["`jorekai-seo:tech-audit --crawl`: no audits/*.json yet; run until zero FAIL, then the launch checklist"], then
    stage = "loop"
    # A verdict is what makes the log learn, so a due row outranks everything else.
    if s["due"]:
        now.append(f"`jorekai-seo:gsc-review`: {len(s['due'])} row(s) past their verify date need a verdict "
                   "(`won` / `no-change` / `too-small`) from a fresh export: " + ", ".join(r.get("id", "?") for r in s["due"]))
    if a["fail"]:
        stage = "audit"
        now.append(f"`jorekai-seo:tech-audit`: {a['file']} still has {a['fail']} FAIL ({', '.join(a['fail_ids'])}); "
                   "fix per check id, rerun, log a `tech` row")
    tech_todo = [r for r in s["todo"] if r.get("bucket") == "tech"]
    other_todo = [r for r in s["todo"] if r.get("bucket") != "tech"]
    if tech_todo:
        now.append("apply the open `tech` rows, then set Status `applied`, the date, and `verify after` "
                   f"(+{TECH_VERIFY_DAYS} days): " + ", ".join(r.get("id", "?") for r in tech_todo))
    last_month = (today.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
    if s["rows"] and last_month not in s["reports"]:
        now.append(f"`jorekai-seo:report` for {last_month}: reports/{last_month}.md does not exist yet")
    now += setup_open
    exp = s["export"]
    if exp is None:
        step = ("export Search Console (Performance > Export, 28 days, plus the previous 28 days) into exports/, "
                "then `jorekai-seo:gsc-review`")
        # exports/ is git-ignored, so a second checkout has the log rows but not the file they name.
        if s["log_sources"]:
            step += (f" (the newest log names {s['log_sources'][-1]}, and exports/ holds no file here: "
                     "the folder is git-ignored, so export again instead of hunting for it)")
        now.append(step)
        if stage == "loop" and not s["rows"] and not s["briefs"] and not s["drafts"]:
            stage = "loop, not started"
    else:
        age = (today - file_date(exp)).days
        if exp.name not in s["log_source"]:
            now.append(f"`jorekai-seo:gsc-review` on exports/{exp.name}: not named in any log's Source line yet")
        elif age > EXPORT_MAX_AGE:
            now.append(f"export Search Console again (exports/{exp.name} is {plural(age, 'day')} old), then `jorekai-seo:gsc-review`")
    for r in other_todo:
        skill = {"content": "jorekai-seo:content", "links": "jorekai-seo:links", "distribution": "jorekai-seo:distribution",
                 "diagnose": "jorekai-seo:diagnose"}.get(r.get("bucket"), "apply per jorekai-seo:gsc-review actions.md")
        now.append(f"{skill}: {r.get('id', '?')} ({r.get('bucket')}, {r.get('url')}), then set Status `applied` and `verify after`")
    for slug in s["briefs"]:
        if slug not in s["drafts"]:
            now.append(f"`jorekai-seo:content`: briefs/{slug}.md has no draft yet")
    for slug in s["drafts"]:
        shipped = any(slug in r.get("url", "") and r.get("bucket") == "content" and r.get("status") != "todo"
                      for r in s["rows"])
        if not shipped:
            now.append(f"`jorekai-seo:review` on drafts/{slug}.md, then ship it, request indexing, and log a `content` row")
    for r in s["rows"]:
        if r.get("bucket") != "content" or r.get("status") not in ("applied", "verify", "won", "no-change", "too-small"):
            continue
        url = r.get("url", "")
        for bucket, skill in (("links", "jorekai-seo:links"), ("distribution", "jorekai-seo:distribution")):
            if not any(x.get("bucket") == bucket and x.get("url") == url for x in s["rows"]):
                now.append(f"`{skill}` for {url} (shipped as {r.get('id', '?')}, no `{bucket}` row yet)")
    if not now:
        now.append("nothing open this week; next export and `jorekai-seo:gsc-review` next week")
    if s["next_verify"]:
        then.append(f"{s['next_verify'].isoformat()}: first verify date reached; `jorekai-seo:gsc-review` grades those rows")
    return stage, now, then


def report(s, today):
    c = s["connections"]
    out = [paint(f"# {s['domain']}, {today.isoformat()} ({week_of(today)})", "head"), ""]
    out.append("setup        config " + ("filled" if s["config"] else "TEMPLATE")
               + " | connections: " + ", ".join(f"{k.split('_')[0].lower()} {v.split()[0] if v else 'MISSING'}" for k, v in c.items())
               + " | strategy " + ("filled" if s["strategy"] else "TEMPLATE")
               + " | glossary " + ("filled" if s["glossary"] else "TEMPLATE"))
    a = s["audit"]
    out.append("audit        " + (f"{a['file']}: {paint('FAIL', 'FAIL')} {a['fail']}, "
                                  f"{paint('WARN', 'WARN')} {a['warn']}" if a else "none"))
    by = {}
    for r in s["rows"]:
        by[r.get("status", "?")] = by.get(r.get("status", "?"), 0) + 1
    out.append(f"log          {len(s['rows'])} rows: " + (", ".join(f"{k} {v}" for k, v in sorted(by.items())) or "empty")
               + f" | due for verdict {len(s['due'])}"
               + (f" | next verify {s['next_verify'].isoformat()}" if s["next_verify"] else ""))
    exp = s["export"]
    out.append("exports      " + (f"{exp.name} ({plural((today - file_date(exp)).days, 'day')} old)" if exp else "none"))
    out.append(f"briefs       {', '.join(s['briefs']) or 'none'}")
    out.append(f"drafts       {', '.join(s['drafts']) or 'none'}")
    out.append(f"reports      {', '.join(s['reports']) or 'none'}")
    stage, now, then = decide(s, today)
    out += ["", f"{paint('stage', 'head')}: {stage}", paint("now:", "head")]
    out += [f"  {i}. {step}" for i, step in enumerate(now, 1)]
    if then:
        out += ["then:"] + [f"  - {t}" for t in then]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("domains", nargs="*")
    ap.add_argument("--root", default="docs/seo")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    a = ap.parse_args()
    root = Path(a.root)
    for d in a.domains:      # a folder name, never a path: keep the report inside --root
        if "/" in d or d.startswith("."):
            sys.exit(f"not a domain folder name: {d!r}")
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    if not root.is_dir():
        print(f"no workspace at {root}: run `jorekai-seo:setup` first")
        sys.exit(2)
    domains = a.domains or sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "config.md").exists())
    if not domains:
        print(f"no domain folder under {root}: run `jorekai-seo:setup <domain>` first")
        sys.exit(2)
    reports = []
    for d in domains:
        base = root / d
        if not base.is_dir():
            print(f"no folder {base}: run `jorekai-seo:setup {d}` first")
            sys.exit(2)
        reports.append(report(read_domain(base, today), today))
    print("\n\n".join(reports))


if __name__ == "__main__":
    main()
