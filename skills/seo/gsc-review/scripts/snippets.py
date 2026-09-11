#!/usr/bin/env python3
"""What Google sees in the snippet fields of a page, before deciding a title or meta rewrite.

Usage:
  snippets.py URL [URL ...] [--query "target query"] [--json]

Fetches each URL with a Googlebot user agent (redirects followed, same rules as
tech-audit/scripts/audit.py; the fetch is copied so this skill stays standalone) and
prints title, meta description, H1, og:title, dateModified as a table, then the flags:

  meta-is-title       meta description equals the title
  title-no-query      --query given and a content word of it is missing from the title; the flag
                      names the missing words, stopwords are ignored
  h1-missing          no <h1>
  h1-linebreak        the H1 text contains a line break or <br>
  h1-multiple         more than one <h1>
  title-multiple      more than one <title> (a page builder widget that pastes a whole HTML head)
  og-title-differs    og:title is set and differs from the title
  meta-long           meta description over 160 characters
  meta-number-absent  a number with a currency or percent sign in the meta does not occur in the body text

Stdlib only. Exit code 1 when any URL could not be fetched.
"""
import os
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA_BOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
MAX_BODY = 3_000_000
# English and German stopwords. A natural title does not repeat "how to ... for the", so a raw
# word-for-word comparison would flag almost every title. Same list as tech-audit/scripts/audit.py.
STOPWORDS = set("a an the and or of for to in on with vs versus your my is are how what why "
                "best top guide de der die das und für mit von im am zu ein eine".split())
META_MAX = 160          # heuristic, see seo/references/sources.md
NUMBER_RE = re.compile(r"(?:ab\s+)?\d[\d.,]*\s?(?:€|EUR|%|\$)", re.I)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


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


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(url, ua=UA_BOT, timeout=15, max_hops=10):
    """Follow redirects manually; return final URL, status, headers, body, chain."""
    chain, current = [], url
    for _ in range(max_hops):
        req = urllib.request.Request(current, headers={"User-Agent": ua, "Accept": "text/html,*/*;q=0.8",
                                                        "Accept-Language": "de,en;q=0.8"})
        try:
            with _OPENER.open(req, timeout=timeout) as resp:
                status, headers, raw = resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read(MAX_BODY)
        except urllib.error.HTTPError as e:
            status, headers = e.code, {k.lower(): v for k, v in e.headers.items()}
            try:
                raw = e.read(MAX_BODY)
            except Exception:
                raw = b""
        except Exception as e:
            chain.append((current, None))
            return {"url": url, "final_url": current, "status": None, "headers": {}, "body": "", "chain": chain, "error": str(e)}
        if status is None:      # a response with no status code: the URL was not http:// or https://
            chain.append((current, None))
            return {"url": url, "final_url": current, "status": None, "headers": {}, "body": "", "chain": chain,
                    "error": "no HTTP status; give an http:// or https:// URL"}
        chain.append((current, status))
        if 300 <= status < 400 and "location" in headers:
            # build_opener installs a FileHandler and an FTPHandler; a redirect never reaches them.
            target = urllib.parse.urljoin(current, headers["location"])
            if not target.lower().startswith(("http://", "https://")):
                chain.append((target, "scheme"))
                return {"url": url, "final_url": current, "status": None, "headers": {}, "body": "",
                        "chain": chain, "error": f"redirect to a non-HTTP target: {target}"}
            current = target
            continue
        ctype = headers.get("content-type", "")
        m = re.search(r"charset=([\w-]+)", ctype)
        try:
            body = raw.decode(m.group(1) if m else "utf-8", errors="replace")
        except LookupError:
            body = raw.decode("utf-8", errors="replace")
        return {"url": url, "final_url": current, "status": status, "headers": headers, "body": body, "chain": chain, "error": None}
    return {"url": url, "final_url": current, "status": None, "headers": {}, "body": "", "chain": chain, "error": "too many redirects"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = None
        self.meta = None
        self.og_title = None
        self.modified = None
        self.h1s = []
        self.title_count = 0
        self.text = []
        self._in_title = self._in_h1 = False
        self._skip = 0
        self._in_ld = False
        self._h1_raw = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1
            self._in_ld = tag == "script" and (a.get("type") or "").strip().lower() == "application/ld+json"
        elif tag == "title":
            self.title_count += 1
            self._in_title = self.title_count == 1   # the first title is the one Google reads first
        elif tag == "h1":
            self._in_h1, self._h1_raw = True, ""
        elif tag == "br" and self._in_h1:
            self._h1_raw += "\n"
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            content = (a.get("content") or "").strip()
            if name == "description" and self.meta is None:
                self.meta = content
            elif name == "og:title" and self.og_title is None:
                self.og_title = content
            elif name == "article:modified_time" and self.modified is None:
                self.modified = content

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template"):
            self._skip = max(0, self._skip - 1)
            self._in_ld = False
        elif tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
            self.h1s.append(self._h1_raw)

    def handle_data(self, data):
        if self._in_ld:
            for m in re.finditer(r'"dateModified"\s*:\s*"([^"]+)"', data):
                self.modified = self.modified or m.group(1)
            return
        if self._skip:
            return
        if self._in_title:
            self.title = ((self.title or "") + data)
        if self._in_h1:
            self._h1_raw += data
        self.text.append(data)


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def terms(s):
    """Content words of a string, lowercase, stopwords and one- and two-letter words dropped."""
    return {w for w in re.split(r"[^a-z0-9äöüß]+", (s or "").lower()) if len(w) > 2 and w not in STOPWORDS}


def inspect(url, query=None):
    r = fetch(url)
    out = {"url": url, "final_url": r["final_url"], "status": r["status"], "error": r["error"]}
    if r["error"] or not r["body"]:
        return out
    p = Page()
    try:
        p.feed(r["body"])
    except Exception:
        pass
    h1 = p.h1s[0].strip() if p.h1s else None
    body_text = clean(" ".join(p.text))
    out.update({"title": clean(p.title), "title_count": p.title_count, "meta": clean(p.meta), "h1": h1, "h1_count": len(p.h1s),
                "og_title": clean(p.og_title), "date_modified": p.modified,
                "cache": {k: v for k, v in r["headers"].items() if k in ("cf-cache-status", "x-flying-press-cache", "x-cache", "age")}})
    flags = []
    if out["meta"] and out["meta"] == out["title"]:
        flags.append("meta-is-title")
    missing_query = sorted(terms(query) - terms(out["title"])) if query else []
    if missing_query:
        flags.append("title-no-query:" + ";".join(missing_query))
    if not h1:
        flags.append("h1-missing")
    elif "\n" in h1:
        flags.append("h1-linebreak")
    if len(p.h1s) > 1:
        flags.append("h1-multiple")
    if p.title_count > 1:
        flags.append("title-multiple")
    if out["og_title"] and out["og_title"] != out["title"]:
        flags.append("og-title-differs")
    if out["meta"] and len(out["meta"]) > META_MAX:
        flags.append("meta-long")
    missing = [n for n in NUMBER_RE.findall(out["meta"] or "") if clean(n) not in body_text]
    if missing:
        flags.append("meta-number-absent:" + ";".join(clean(n) for n in missing))
    out["flags"] = flags
    return out


def render(o):
    """The console report: the snippet fields as fixed-width rows, text left, then the flags."""
    lines = [paint(f"snippet  {o['url']}", "head")]
    if o.get("error") or not o.get("status"):
        lines.append(paint(f"fetch failed: {o.get('error') or 'no body'}", "FAIL"))
        return "\n".join(lines) + "\n"
    if o["final_url"] != o["url"]:
        lines.append(f"redirected to {o['final_url']} ({o['status']})")
    cache = ", ".join(f"{k}: {v}" for k, v in o["cache"].items())
    lines.append("")
    lines.append(paint(f"{'field':<17}{'value':<60}chars", "dim"))
    for label, key in (("title", "title"), ("meta description", "meta"), ("H1", "h1"), ("og:title", "og_title"), ("dateModified", "date_modified")):
        v = o.get(key)
        shown = (v or "").replace("\n", "⏎") or "missing"
        lines.append(f"{label:<17}{shown:<60}{len(v) if v else 0:>5}")
    lines.append("")
    lines.append("flags  " + (", ".join(o["flags"]) if o["flags"] else "none"))
    if cache:
        lines.append(f"cache headers (bot UA)  {cache}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--query", help="target query; every word of it should appear in the title (applies to every URL given: one URL per call when queries differ)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between fetches")
    a = ap.parse_args()
    results = []
    for i, u in enumerate(a.urls):
        if i and a.delay:
            time.sleep(a.delay)
        results.append(inspect(u, a.query))
    if a.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("\n".join(render(o) for o in results))
    sys.exit(1 if any(o.get("error") or not o.get("status") for o in results) else 0)


if __name__ == "__main__":
    main()
