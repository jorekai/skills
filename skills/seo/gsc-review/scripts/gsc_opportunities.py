#!/usr/bin/env python3
"""Turn a Google Search Console performance export into ranked opportunity buckets.

Input: the folder or .zip that GSC produces via Performance -> Export -> Download CSV
(files like Queries.csv / Pages.csv, or localized names). Locale-safe number parsing.

Usage:
  gsc_opportunities.py EXPORT [--previous EXPORT] [--page-queries CSV] [--not-indexed CSV]
                       [--min-impressions 50] [--pos-min 8] [--pos-max 20] [--top 25] [--json]

Buckets:
  striking      queries/pages ranking pos-min..pos-max with enough impressions
  ctr-gap       impressions high, CTR far below what the position should earn
  decay         pages that lost clicks versus --previous (same length period)
  cannibal      one query served by several of your pages (needs --page-queries)
  not-indexed   URLs from --not-indexed, listed for action

With --previous the report also carries the site totals and the site baseline: the median change
of every page present in both exports. One page's change counts only against that line. It suggests
--expected-ctr-1 from the site's own non-brand queries at position 1 as well.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile

# Rough non-branded organic CTR by position. A heuristic, not a fact: published studies put
# position 1 anywhere from 11 % to 40 % depending on market, intent, and AI Overviews.
# Calibration points (study results, not rules): Sistrix, Germany, 100M keywords, 2026:
# position 1 about 27 % overall and 11 % when an AI Overview shows. Ahrefs, 300,000 keywords,
# desktop GSC data, Dec 2025: position 1 at 7.3 % without and 1.6 % with an AI Overview.
# Pass --expected-ctr-1 to scale the curve to the site's own top queries.
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


EXPECTED_CTR = {1: .28, 2: .15, 3: .11, 4: .08, 5: .07, 6: .05, 7: .04, 8: .03, 9: .03, 10: .025}

# A median over a handful of rows is noise, not a baseline. The same holds for the suggestion.
MIN_BASELINE_N = 10
MIN_BASELINE_CLICKS = 10        # a page with few clicks makes the click ratio jump between windows
MIN_CALIBRATION_N = 5

# --------------------------------------------------------------------------- parsing

def to_int(s):
    return int(re.sub(r"[^\d]", "", s or "0") or 0)


def to_float(s):
    s = (s or "0").strip().replace("%", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def read_rows(text):
    text = text.lstrip("﻿")
    dialect = csv.excel
    if text:
        try:
            dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t")
        except csv.Error:
            pass    # one column and no delimiter in sight: the not-indexed URL export
    rows = list(csv.reader(io.StringIO(text), dialect))
    return [r for r in rows if r and any(c.strip() for c in r)]


def load_export(path):
    """Return {name_lower: text} for every CSV in a folder or zip."""
    files = {}
    if os.path.isdir(path):
        for n in os.listdir(path):
            if n.lower().endswith(".csv"):
                with open(os.path.join(path, n), encoding="utf-8-sig", errors="replace") as f:
                    files[n.lower()] = f.read()
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    files[os.path.basename(n).lower()] = z.read(n).decode("utf-8-sig", errors="replace")
    elif path.lower().endswith(".csv"):
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            files[os.path.basename(path).lower()] = f.read()
    else:
        sys.exit(f"Cannot read {path}: expected a folder, .zip or .csv")
    return files


def metric_rows(text):
    """Rows of (key, clicks, impressions, ctr, position) from a 5-column GSC table."""
    rows = read_rows(text)
    if not rows or len(rows[0]) < 5:
        return []
    out = []
    for r in rows[1:]:
        if len(r) < 5:
            continue
        out.append({"key": r[0].strip(), "clicks": to_int(r[1]), "impressions": to_int(r[2]),
                    "ctr": to_float(r[3]) / 100.0, "position": to_float(r[4])})
    return out


def split_export(files):
    """Identify the queries table and the pages table by name, then by content."""
    queries = pages = None
    for name, text in files.items():
        if re.search(r"quer|suchanfr|requ[eê]te|consult|zoekopdr", name):
            queries = text
        elif re.search(r"^page|seiten|^pagina|^páginas", name):
            pages = text
    if pages is None:
        for name, text in files.items():
            rows = metric_rows(text)
            if rows and sum(r["key"].startswith("http") for r in rows) > len(rows) / 2:
                pages = text
                break
    if queries is None:
        best = None
        for name, text in files.items():
            rows = metric_rows(text)
            if not rows or text is pages:
                continue
            first = rows[0]["key"]
            if re.match(r"\d{4}-\d{2}-\d{2}", first) or first.upper() in ("MOBILE", "DESKTOP", "TABLET"):
                continue
            if best is None or len(rows) > len(best):
                best = rows
                queries = text
    return (metric_rows(queries) if queries else []), (metric_rows(pages) if pages else [])


def load_page_queries(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        rows = read_rows(f.read())
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]

    def col(*names):
        for i, h in enumerate(header):
            if any(n in h for n in names):
                return i
        return None
    ip, iq = col("page", "url", "seite", "landing"), col("query", "keyword", "suchanfr")
    ic, ii, ipos = col("click", "klick"), col("impr"), col("position")
    if None in (ip, iq, ii, ipos):
        sys.exit(f"--page-queries needs page, query, impressions, position columns; got {header}")
    out = []
    for r in rows[1:]:
        if len(r) <= max(ip, iq, ii, ipos):
            continue
        out.append({"page": r[ip].strip(), "query": r[iq].strip(), "clicks": to_int(r[ic]) if ic is not None else 0,
                    "impressions": to_int(r[ii]), "position": to_float(r[ipos])})
    return out

# --------------------------------------------------------------------------- buckets

CTR_SCALE = 1.0


def expected_ctr(pos):
    return CTR_SCALE * EXPECTED_CTR.get(int(round(pos)), .015 if pos <= 20 else .005)


def is_brand(key, a):
    return bool(a.brand_re and a.brand_re.search(key))


def striking(rows, a, is_query=True):
    """`is_query=False` for the pages table: the brand filter only applies to query text.
    A page key is a full URL, and the brand name usually sits in the host."""
    hits = [r for r in rows if a.pos_min <= r["position"] <= a.pos_max and r["impressions"] >= a.min_impressions
            and not (is_query and is_brand(r["key"], a))]
    return sorted(hits, key=lambda r: -r["impressions"])


def ctr_gap(rows, a, is_query=True):
    hits = []
    for r in rows:
        if r["impressions"] < max(a.min_impressions, 100) or r["position"] > 20 or (is_query and is_brand(r["key"], a)):
            continue
        exp = expected_ctr(r["position"])
        if r["ctr"] < exp * 0.5:
            hits.append({**r, "expected_ctr": exp, "missed_clicks": int((exp - r["ctr"]) * r["impressions"])})
    return sorted(hits, key=lambda r: -r["missed_clicks"])


def decay(now_pages, prev_pages, a):
    prev = {r["key"]: r for r in prev_pages}
    hits = []
    for r in now_pages:
        p = prev.get(r["key"])
        if not p or p["clicks"] < 20:
            continue
        if r["clicks"] <= p["clicks"] * 0.7:
            hits.append({**r, "prev_clicks": p["clicks"], "prev_position": p["position"],
                         "lost": p["clicks"] - r["clicks"]})
    for p in prev_pages:  # pages that vanished entirely
        if p["clicks"] >= 20 and p["key"] not in {r["key"] for r in now_pages}:
            hits.append({"key": p["key"], "clicks": 0, "impressions": 0, "ctr": 0, "position": 0,
                         "prev_clicks": p["clicks"], "prev_position": p["position"], "lost": p["clicks"]})
    return sorted(hits, key=lambda r: -r["lost"])


def totals(rows):
    """Clicks and impressions of the rows in the export. The UI export caps a table at 1,000 rows,
    so on a big site this is the top of the site, not the site."""
    clicks = sum(r["clicks"] for r in rows)
    impressions = sum(r["impressions"] for r in rows)
    return {"rows": len(rows), "clicks": clicks, "impressions": impressions,
            "ctr": clicks / impressions if impressions else 0.0}


def median(xs):
    s = sorted(xs)
    if not s:
        return None
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def baseline(now_pages, prev_pages, a):
    """Median change of every page in both exports: the yardstick for one page's change.

    Seasonality, a Google update and site-wide drift move all pages at once. A page that
    gained 5 % in a period when the site gained 12 % lost ground. Pages changed in the period
    are a small share of all pages, so no list of them is needed: the median ignores them.
    """
    prev = {r["key"]: r for r in prev_pages}
    pos, ctr, clicks = [], [], []
    for r in now_pages:
        p = prev.get(r["key"])
        if not p or p["impressions"] < a.min_impressions:
            continue
        pos.append(r["position"] - p["position"])
        ctr.append(r["ctr"] - p["ctr"])
        if p["clicks"] >= MIN_BASELINE_CLICKS:
            clicks.append((r["clicks"] - p["clicks"]) / p["clicks"])
    enough = len(pos) >= MIN_BASELINE_N
    return {"n": len(pos), "n_clicks": len(clicks),
            "position": median(pos) if enough else None,
            "ctr": median(ctr) if enough else None,
            "clicks": median(clicks) if len(clicks) >= MIN_BASELINE_N else None}


def ctr_calibration(rows, a):
    """The site's own CTR at position 1: the value for --expected-ctr-1 and for config.md."""
    top = [r for r in rows if r["position"] <= 1.5 and r["impressions"] >= a.min_impressions
           and not is_brand(r["key"], a)]
    return {"n": len(top),
            "ctr_1": median([r["ctr"] for r in top]) if len(top) >= MIN_CALIBRATION_N else None}


def cannibal(pq, a):
    by_q = {}
    for r in pq:
        if r["impressions"] >= max(10, a.min_impressions // 5) and r["position"] <= 30:
            by_q.setdefault(r["query"].lower(), []).append(r)
    hits = []
    for q, rows in by_q.items():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda r: (-r["clicks"], r["position"]))
        hits.append({"query": q, "impressions": sum(r["impressions"] for r in rows),
                     "keep": rows[0]["page"], "merge": [r["page"] for r in rows[1:]],
                     "positions": [round(r["position"], 1) for r in rows]})
    return sorted(hits, key=lambda r: -r["impressions"])


def load_url_list(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        rows = read_rows(f.read())
    urls = [r[0].strip() for r in rows if r and r[0].strip().startswith("http")]
    return urls

# --------------------------------------------------------------------------- render

def fmt_pct(x):
    return f"{x * 100:.1f}%"


def fixed_table(headers, aligns, widths, rows):
    """A column header line, dimmed, then rows of fixed widths: text left, numbers right."""
    cell = lambda v, a, w: str(v).ljust(w) if a == "l" else str(v).rjust(w)
    out = [paint("  ".join(cell(h, a, w) for h, a, w in zip(headers, aligns, widths)), "dim")]
    for r in rows:
        out.append("  ".join(cell(v, a, w) for v, a, w in zip(r, aligns, widths)))
    return out


def bucket(out, label, params, headers, aligns, widths, rows, empty):
    """A bucket head (bold label, its parameters), then its rows, or a dimmed empty line."""
    out.append(paint(label, "head") + "  " + "  ".join(params))
    if rows:
        out += fixed_table(headers, aligns, widths, rows)
    else:
        out.append(paint(f"  {empty}", "dim"))
    out.append("")


def render(res, a):
    """The console report: totals and baseline, then the six buckets, `next` last
    (decisions/0028: a bucket head names its parameters, rows are fixed-width columns)."""
    o = [paint(f"gsc-review  {res['n_queries']} queries  {res['n_pages']} pages", "head"),
         f"measured against  impressions >= {a.min_impressions}, striking pos {a.pos_min} to {a.pos_max}", ""]
    if res.get("brand"):
        b = res["brand"]
        share = fmt_pct(b["clicks"] / b["total_clicks"]) if b["total_clicks"] else "0%"
        o.append(f"brand      {b['queries']} queries · {b['clicks']} of {b['total_clicks']} clicks ({share}), "
                 "excluded from buckets 1 and 3")
    cal = res["calibration"]
    if cal["ctr_1"] is not None:
        o.append(f"calibration  suggested --expected-ctr-1 {cal['ctr_1']:.2f} "
                 f"(median CTR of {cal['n']} non-brand queries at position 1.0 to 1.5, scale {CTR_SCALE:.2f})")
    else:
        o.append(f"calibration  no suggestion yet: {cal['n']} of {MIN_CALIBRATION_N} non-brand queries "
                 "at position 1.0 to 1.5")
    o.append("")

    t = res["totals"]
    n, prev = t["now"], t["previous"]
    if prev is None:
        bucket(o, "totals", [f"{t['source']} in this export", "capped at 1,000 rows"],
               ["metric", "this export"], ["l", "r"], [12, 14],
               [("clicks", n["clicks"]), ("impressions", n["impressions"]),
                ("ctr", fmt_pct(n["ctr"])), (t["source"], n["rows"])], "no rows")
    else:
        def change(x, y):
            return f"{(x - y) / y * 100:+.1f}%" if y else "n/a"
        bucket(o, "totals", [f"{t['source']} in this export", "capped at 1,000 rows"],
               ["metric", "this export", "previous", "change"], ["l", "r", "r", "r"], [12, 14, 14, 10],
               [("clicks", n["clicks"], prev["clicks"], change(n["clicks"], prev["clicks"])),
                ("impressions", n["impressions"], prev["impressions"], change(n["impressions"], prev["impressions"])),
                ("ctr", fmt_pct(n["ctr"]), fmt_pct(prev["ctr"]), f"{(n['ctr'] - prev['ctr']) * 100:+.2f}pp"),
                (t["source"], n["rows"], prev["rows"], f"{n['rows'] - prev['rows']:+d}")], "no rows")

    b = res["baseline"]
    if b is None:
        bucket(o, "baseline", ["subtract before a page counts as won"], [], [], [], [],
               "pass --previous with the export for the preceding period of equal length")
    elif b["position"] is None:
        bucket(o, "baseline", ["subtract before a page counts as won"], [], [], [], [],
               f"{b['n']} pages in both exports reach the impression threshold, {MIN_BASELINE_N} needed")
    else:
        bucket(o, "baseline", ["subtract before a page counts as won"],
               ["metric", "median change", "pages"], ["l", "r", "r"], [10, 30, 6],
               [("position", f"{b['position']:+.1f} (higher is worse)", b["n"]),
                ("ctr", f"{b['ctr'] * 100:+.2f}pp", b["n"]),
                ("clicks", f"{b['clicks'] * 100:+.1f}%" if b["clicks"] is not None
                 else f"under {MIN_BASELINE_N} pages had {MIN_BASELINE_CLICKS}+ clicks before", b["n_clicks"])],
               "no rows")

    bucket(o, "striking-q", [f"{len(res['striking_queries'])} queries", f"pos {a.pos_min} to {a.pos_max}",
                            f"min {a.min_impressions} impressions"],
           ["query", "impr.", "clicks", "ctr", "pos."], ["l", "r", "r", "r", "r"], [40, 8, 8, 7, 6],
           [(r["key"], r["impressions"], r["clicks"], fmt_pct(r["ctr"]), f"{r['position']:.1f}")
            for r in res["striking_queries"][:a.top]], "none")
    bucket(o, "striking-p", [f"{len(res['striking_pages'])} pages", f"pos {a.pos_min} to {a.pos_max}"],
           ["page", "impr.", "clicks", "pos."], ["l", "r", "r", "r"], [46, 8, 8, 6],
           [(r["key"], r["impressions"], r["clicks"], f"{r['position']:.1f}")
            for r in res["striking_pages"][:a.top]], "none")
    bucket(o, "ctr-gap-q", [f"{len(res['ctr_gap_queries'])} queries", "expected CTR is a heuristic curve"],
           ["query", "impr.", "ctr", "expected", "pos.", "missed"], ["l", "r", "r", "r", "r", "r"],
           [34, 8, 7, 8, 6, 7],
           [(r["key"], r["impressions"], fmt_pct(r["ctr"]), fmt_pct(r["expected_ctr"]),
             f"{r['position']:.1f}", r["missed_clicks"]) for r in res["ctr_gap_queries"][:a.top]], "none")
    bucket(o, "ctr-gap-p", [f"{len(res['ctr_gap_pages'])} pages"],
           ["page", "impr.", "ctr", "expected", "pos.", "missed"], ["l", "r", "r", "r", "r", "r"],
           [40, 8, 7, 8, 6, 7],
           [(r["key"], r["impressions"], fmt_pct(r["ctr"]), fmt_pct(r["expected_ctr"]),
             f"{r['position']:.1f}", r["missed_clicks"]) for r in res["ctr_gap_pages"][:a.top]], "none")
    if res["decay"] is None:
        bucket(o, "decay", ["refresh content, do not write anything new"], [], [], [], [],
               "pass --previous with the export for the preceding period of equal length")
    else:
        bucket(o, "decay", [f"{len(res['decay'])} pages", "check Compare year over year first"],
               ["page", "now", "before", "pos now", "pos before", "lost"],
               ["l", "r", "r", "r", "r", "r"], [40, 6, 8, 8, 10, 6],
               [(r["key"], r["clicks"], r["prev_clicks"], f"{r['position']:.1f}", f"{r['prev_position']:.1f}", r["lost"])
                for r in res["decay"][:a.top]], "none")
    if res["cannibal"] is None:
        bucket(o, "cannibal", ["two URLs for one query, not a penalty per Google"], [], [], [], [],
               "pass --page-queries with a page x query table")
    else:
        bucket(o, "cannibal", [f"{len(res['cannibal'])} queries", "merge only pages that duplicate each other"],
               ["query", "impr.", "keep", "merge/301"], ["l", "r", "l", "l"], [24, 7, 26, 26],
               [(r["query"], r["impressions"], r["keep"], "; ".join(r["merge"]))
                for r in res["cannibal"][:a.top]], "none")
    if res["not_indexed"] is None:
        bucket(o, "not-indexed", ["link internally, then request indexing"], [], [], [], [],
               "pass --not-indexed with the URL export of a not-indexed reason")
    else:
        bucket(o, "not-indexed", [f"{len(res['not_indexed'])} URLs", "unindexed after 4 weeks: merge or remove"],
               ["url"], ["l"], [70],
               [(u,) for u in res["not_indexed"][:a.top]], "none")

    if res["not_indexed"] or res["decay"] or res["ctr_gap_queries"] or res["ctr_gap_pages"] \
            or res["striking_queries"] or res["striking_pages"]:
        o.append(paint("next", "head") + "  decide one action per row per bucket "
                 "(references/actions.md), costliest first")
    else:
        o.append(paint("next", "head") + "  nothing to act on, export again next week")
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export")
    ap.add_argument("--previous", help="export for the preceding period (for decay)")
    ap.add_argument("--page-queries", help="CSV with page, query, clicks, impressions, position columns")
    ap.add_argument("--not-indexed", help="CSV of URLs exported from the Pages (indexing) report")
    ap.add_argument("--min-impressions", type=int, default=50)
    ap.add_argument("--pos-min", type=float, default=8)
    ap.add_argument("--pos-max", type=float, default=20)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--brand", help="regex (case-insensitive) for brand queries; excluded from striking distance and CTR gap, reported as a share")
    ap.add_argument("--expected-ctr-1", type=float, help="the site's own CTR at position 1 (e.g. 0.11); scales the expected-CTR curve")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    a.brand_re = re.compile(a.brand, re.I) if a.brand else None
    global CTR_SCALE
    if a.expected_ctr_1:
        CTR_SCALE = a.expected_ctr_1 / EXPECTED_CTR[1]

    queries, pages = split_export(load_export(a.export))
    if not queries and not pages:
        sys.exit("No queries/pages table found in the export")
    brand = None
    if a.brand_re:
        bq = [r for r in queries if is_brand(r["key"], a)]
        brand = {"queries": len(bq), "clicks": sum(r["clicks"] for r in bq), "total_clicks": sum(r["clicks"] for r in queries)}
    res = {"n_queries": len(queries), "n_pages": len(pages), "brand": brand,
           "striking_queries": striking(queries, a), "striking_pages": striking(pages, a, is_query=False),
           "ctr_gap_queries": ctr_gap(queries, a), "ctr_gap_pages": ctr_gap(pages, a, is_query=False),
           "decay": None, "cannibal": None, "not_indexed": None, "baseline": None,
           "calibration": ctr_calibration(queries, a),
           "totals": {"source": "pages" if pages else "queries", "previous": None,
                      "now": totals(pages or queries)}}
    if a.previous:
        prev_queries, prev_pages = split_export(load_export(a.previous))
        res["decay"] = decay(pages, prev_pages, a)
        res["baseline"] = baseline(pages, prev_pages, a)
        res["totals"]["previous"] = totals(prev_pages if pages else prev_queries)
    if a.page_queries:
        res["cannibal"] = cannibal(load_page_queries(a.page_queries), a)
    if a.not_indexed:
        res["not_indexed"] = load_url_list(a.not_indexed)
    print(json.dumps(res, indent=2, ensure_ascii=False) if a.json else render(res, a))


if __name__ == "__main__":
    main()
