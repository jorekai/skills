#!/usr/bin/env python3
"""Technical SEO audit for one URL, optionally crawling the site behind it.

Stdlib only. Fetches with a Googlebot user agent (what the index sees) and
compares against a browser user agent to detect JS-only content.

Usage:
  audit.py URL [--crawl N] [--rendered FILE] [--timeout S] [--delay S] [--json]

--rendered takes a saved rendered DOM for URL itself, from a browser tool or from
Search Console's live test, and names what exists only after JavaScript.

A crawl costs about one second per page (fetch plus --delay); run large crawls
in the background and write --json to a file. Cart, checkout, and account URLs
are counted but not fetched; tracking parameters are stripped before a URL is
queued and reported under crawl.tracking-params.

The crawl obeys robots.txt: a disallowed URL is reported, not fetched. The URL
given on the command line is fetched either way, because a robots block on it is
itself the finding. Redirects are followed only to http:// and https:// targets.

Exit code 0 always; findings are in the report, not the exit status.
"""
import os
import argparse
import csv
import ipaddress
import json
import pathlib
import random
import re
import socket
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import Counter, deque
from html.parser import HTMLParser

UA_BOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
UA_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MAX_BODY = 3_000_000
# The only two protocols this tool has any business speaking. build_opener() installs urllib's
# file and ftp handlers as well, so a target that names another scheme is refused before the
# request is built, not after a redirect names it.
SCHEME_OK = ("http://", "https://")
# Query parameters that only track a click. An internal link carrying one creates a URL variant.
TRACKING_PARAMS = re.compile(r"^(utm_\w+|gclid|gbraid|wbraid|fbclid|msclkid|dclid|mc_cid|mc_eid|_ga|_gl|ref|source)$", re.I)
# Cart, checkout, and account URLs (WooCommerce English and German slugs, Shopify, generic). Never indexable, never worth a fetch.
CART_RE = re.compile(r"[?&](add-to-cart|remove_item|wc-ajax|undo_item)=|/(cart|checkout|basket|my-account|warenkorb|kasse|mein-konto)(/|$)", re.I)
# A framework mount point that is still empty in the raw HTML. The closing tag has to sit within
# 200 characters, so a mount point that already holds the page does not match.
APP_ROOT_RE = re.compile(r"<(div|main|section)\b[^>]*\bid=[\"']?(root|app|__next|__nuxt|svelte)\b[^>]*>(?:.{0,200}?)</\1>", re.I | re.S)
# Consent-management platforms. Named only when the page is already thin: a CMP alone says nothing.
CMP_RE = re.compile(r"cookiebot|usercentrics|onetrust|borlabs|complianz|cookieyes|klaro|didomi|iubenda|cookie-?consent", re.I)
# Elements that repeat on every page. Their text says nothing about this page.
CHROME_TAGS = ("header", "nav", "footer", "aside")
# English and German stopwords; the audit is used on sites in both languages.
STOPWORDS = set("a an the and or of for to in on with vs versus your my is are how what why "
                "best top guide de der die das und für mit von im am zu ein eine".split())

# --------------------------------------------------------------------------- fetch

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(url, ua=UA_BOT, timeout=15, max_hops=10, delay=0.0):
    """Follow redirects manually and return the full chain plus final response."""
    chain = []
    current = url
    for _ in range(max_hops):
        if not current.lower().startswith(SCHEME_OK):
            chain.append((current, "scheme"))
            return {"url": url, "chain": chain, "final_url": current, "status": None,
                    "headers": {}, "body": "", "elapsed": 0.0,
                    "error": f"not an HTTP target: {current}"}
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(current, headers={"User-Agent": ua,
                                                        "Accept": "text/html,*/*;q=0.8",
                                                        "Accept-Language": "en,de;q=0.8"})
        t0 = time.time()
        try:
            with _OPENER.open(req, timeout=timeout) as resp:
                status = resp.status
                headers = {k.lower(): v for k, v in resp.headers.items()}
                raw = resp.read(MAX_BODY)
        except urllib.error.HTTPError as e:
            status = e.code
            headers = {k.lower(): v for k, v in e.headers.items()}
            try:
                raw = e.read(MAX_BODY)
            except Exception:
                raw = b""
        except Exception as e:  # DNS, timeout, TLS
            chain.append((current, None))
            return {"url": url, "chain": chain, "final_url": current, "status": None,
                    "headers": {}, "body": "", "error": str(e), "elapsed": time.time() - t0}
        elapsed = time.time() - t0
        chain.append((current, status))
        if 300 <= status < 400 and "location" in headers:
            target = urllib.parse.urljoin(current, headers["location"])
            if not target.lower().startswith(SCHEME_OK):
                chain.append((target, "scheme"))
                return {"url": url, "chain": chain, "final_url": current, "status": None,
                        "headers": {}, "body": "", "elapsed": time.time() - t0,
                        "error": f"redirect to a non-HTTP target: {target}"}
            current = target
            continue
        ctype = headers.get("content-type", "")
        body = ""
        if raw and ("html" in ctype or "xml" in ctype or "text" in ctype or not ctype):
            m = re.search(r"charset=([\w-]+)", ctype)
            enc = m.group(1) if m else "utf-8"
            try:
                body = raw.decode(enc, errors="replace")
            except LookupError:
                body = raw.decode("utf-8", errors="replace")
        return {"url": url, "chain": chain, "final_url": current, "status": status,
                "headers": headers, "body": body, "error": None, "elapsed": elapsed}
    chain.append((current, "loop"))
    return {"url": url, "chain": chain, "final_url": current, "status": None,
            "headers": {}, "body": "", "error": "too many redirects", "elapsed": 0}

# --------------------------------------------------------------------------- parse

class Page(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.title = None
        self._in_title = False
        self._skip = 0  # inside script/style/noscript/template
        self._in_h1 = False
        self.h1s = []
        self.metas = {}
        self.canonicals = []
        self.images = []  # (src, has_alt)
        self.links = []  # (href, rel)
        self.text_chars = 0
        self.chrome_chars = 0   # text inside header/nav/footer/aside: the same on every page
        self._chrome = 0
        self.script_bytes = 0
        self.script_srcs = 0  # <script src>: script_bytes counts inline code only, a bundle weighs nothing there
        self._in_script = False
        self.jsonld = 0
        self.lang = None
        self.hreflang = []  # (hreflang, href)
        self.feeds = []  # (type, href)
        self.meta_refresh = None
        self.jsonld_texts = []
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag in ("script", "style", "noscript", "template"):
            self._skip += 1
            if tag == "script":
                self._in_script = True
                if a.get("src"):
                    self.script_srcs += 1
                if (a.get("type") or "").lower() == "application/ld+json":
                    self.jsonld += 1
                    self._in_jsonld = True
                    self.jsonld_texts.append("")
        elif tag in CHROME_TAGS:
            self._chrome += 1
        elif tag == "h1":
            self._in_h1 = True
            self.h1s.append("")
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if key:
                self.metas.setdefault(key, a.get("content", ""))
            if key == "refresh":
                self.meta_refresh = a.get("content", "")
        elif tag == "link":
            rel = (a.get("rel") or "").lower().split()
            if "canonical" in rel and a.get("href"):
                self.canonicals.append(urllib.parse.urljoin(self.base, a["href"].strip()))
            if "alternate" in rel and (a.get("type") or "").lower() in ("application/rss+xml", "application/atom+xml") and a.get("href"):
                self.feeds.append((a["type"].lower(), urllib.parse.urljoin(self.base, a["href"].strip())))
            if "alternate" in rel and a.get("hreflang"):
                self.hreflang.append((a["hreflang"].strip(), urllib.parse.urljoin(self.base, (a.get("href") or "").strip())))
        elif tag == "img":
            self.images.append({"src": a.get("src") or a.get("data-src") or "", "alt": "alt" in a,
                                "has_src": bool(a.get("src")), "lazy": (a.get("loading") or "").lower() == "lazy",
                                "sized": bool(a.get("width") and a.get("height"))})
        elif tag == "a" and a.get("href"):
            href = a["href"].strip()
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                self.links.append((urllib.parse.urljoin(self.base, href), (a.get("rel") or "").lower()))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style", "noscript", "template"):
            self._skip = max(0, self._skip - 1)
            if tag == "script":
                self._in_script = False
                self._in_jsonld = False
        elif tag in CHROME_TAGS:
            self._chrome = max(0, self._chrome - 1)
        elif tag == "h1":
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_title:
            self.title = ((self.title or "") + data).strip()
            return
        if self._in_script:
            self.script_bytes += len(data)
            if self._in_jsonld and self.jsonld_texts:
                self.jsonld_texts[-1] += data
        if self._skip:
            return
        stripped = data.strip()
        if stripped:
            self.text_chars += len(stripped)
            if self._chrome:
                self.chrome_chars += len(stripped)
            if self._in_h1 and self.h1s:
                self.h1s[-1] = (self.h1s[-1] + " " + stripped).strip()


def parse(body, base):
    p = Page(base)
    try:
        p.feed(body)
    except Exception:
        pass
    return p

# --------------------------------------------------------------------------- helpers

def tokens(s):
    return {t for t in re.split(r"[^a-z0-9äöüß]+", (s or "").lower()) if len(t) > 2 and t not in STOPWORDS}


def norm(url):
    """Normalize for comparisons: drop fragment, lowercase host, strip trailing slash (not root)."""
    u = urllib.parse.urlsplit(url)
    path = u.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urllib.parse.urlunsplit((u.scheme.lower(), u.netloc.lower(), path, u.query, ""))


def strip_tracking(url):
    """Return the URL without tracking parameters (utm_*, gclid, fbclid, ...), other parameters kept."""
    u = urllib.parse.urlsplit(url)
    if not u.query:
        return url
    kept = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)]
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(kept), u.fragment))


def is_cart(url):
    return bool(CART_RE.search(url))


def load_redirect_map(path):
    """Rows of (old, new or None) from a CSV. Header names old/from/source and new/to/target are
    read when present; without a header the first column is the old URL and the second the target."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        rows = [r for r in csv.reader(f) if r and r[0].strip()]
    if not rows:
        return []
    head = [c.strip().lower() for c in rows[0]]
    old_i, new_i, start = 0, (1 if len(head) > 1 else None), 0
    if not head[0].startswith("http"):
        start = 1
        for i, h in enumerate(head):
            if h in ("old", "from", "source", "old url", "alt"):
                old_i = i
            elif h in ("new", "to", "target", "new url", "neu"):
                new_i = i
    out = []
    for r in rows[start:]:
        old = r[old_i].strip() if len(r) > old_i else ""
        new = r[new_i].strip() if new_i is not None and len(r) > new_i else ""
        if old.lower().startswith(("http://", "https://")):
            out.append((old, new or None))
    return out


def check_redirects(path, rep, timeout, delay, section="Redirect map"):
    """Every old URL of a move: one permanent hop, a live target, and the target the map names."""
    rows = load_redirect_map(path)
    if not rows:
        rep.add(section, "FAIL", "redirects.map", f"No URL rows in {path}: the first column holds the old URLs")
        return
    problems = {k: [] for k in ("error", "missing", "temporary", "chain", "broken", "wrong-target")}
    ok = 0
    for old, new in rows:
        r = fetch(old, timeout=timeout, delay=delay)
        hops = [(u, st) for u, st in r["chain"] if isinstance(st, int) and 300 <= st < 400]
        if r["status"] is None:
            problems["error"].append(f"{old}: {r.get('error', 'no response')}")
            continue
        clean = True
        if not hops:
            problems["missing"].append(f"{old}: answers {r['status']} itself, no redirect")
            continue
        if hops[0][1] not in (301, 308):
            problems["temporary"].append(f"{old}: first hop {hops[0][1]}, signals stay on the old URL")
            clean = False
        if len(hops) > 1:
            problems["chain"].append(f"{old}: {len(hops)} hops to {r['final_url']}")
            clean = False
        if r["status"] != 200:
            problems["broken"].append(f"{old}: target {r['final_url']} answers {r['status']}")
            clean = False
        elif new and norm(r["final_url"]) != norm(new):
            problems["wrong-target"].append(f"{old}: lands on {r['final_url']}, the map says {new}")
            clean = False
        ok += clean
    rep.add(section, "PASS" if ok == len(rows) else "INFO", "redirects.map",
            f"{len(rows)} rows checked, {ok} land on their target with one permanent hop")
    levels = {"error": "FAIL", "missing": "FAIL", "broken": "FAIL", "wrong-target": "FAIL",
              "temporary": "WARN", "chain": "WARN"}
    for key, items in problems.items():
        if items:
            rep.add(section, levels[key], f"redirects.{key}",
                    f"{len(items)}: " + "; ".join(items[:5]) + (" ..." if len(items) > 5 else ""), data=items)


def check_schema(p, rep, section):
    """What the structured data on the page is, and what it cannot earn."""
    if not p.jsonld:
        rep.add(section, "INFO", "head.json-ld", "No JSON-LD structured data")
        return
    nodes = []
    for i, text in enumerate(p.jsonld_texts, 1):
        try:
            schema_nodes(json.loads(text), nodes)
        except ValueError as e:
            rep.add(section, "WARN", "head.schema-invalid",
                    f"JSON-LD block {i} of {p.jsonld} is not valid JSON and is ignored whole: {e}")
    seen = {}
    for n in nodes:
        for t in node_types(n):
            seen.setdefault(t.lower(), t)
    if not seen:
        return
    rep.add(section, "INFO", "head.json-ld",
            f"{p.jsonld} JSON-LD block(s), types: {', '.join(seen[k] for k in sorted(seen))}",
            data=sorted(seen.values()))
    dead = [f"{seen[k]} ({why})" for k, why in NO_RICH_RESULT.items() if k in seen]
    if dead:
        rep.add(section, "WARN", "head.schema-no-rich-result",
                "Markup that earns no rich result: " + "; ".join(dead))
    rated = sorted({seen[t.lower()] for n in nodes if "aggregateRating" in n or "review" in n
                    for t in node_types(n) if t.lower() not in REVIEWABLE})
    if rated:
        rep.add(section, "WARN", "head.schema-review",
                f"Rating or review markup on {', '.join(rated)}: a page that rates the entity running it "
                "is ineligible for the star review feature, and invented reviews are a policy violation")


def same_site(a, b):
    ha = urllib.parse.urlsplit(a).netloc.lower().removeprefix("www.")
    hb = urllib.parse.urlsplit(b).netloc.lower().removeprefix("www.")
    return ha == hb


def routable(url, origin):
    """Whether an address a document the audited site served may aim this machine at.

    A sitemap is remote content, and it names the next URL to fetch. Left alone it can point at the
    network this tool runs in, and the report then says whether a private address answered. The
    start URL is the operator's own argument, so its host stays allowed whatever it resolves to.
    """
    host = urllib.parse.urlsplit(url).hostname or ""
    if not host or same_site(url, origin):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True                      # a name that does not resolve is the fetch's problem
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    return True


def looks_random(slug):
    return bool(re.search(r"[0-9a-f]{8,}|\d{6,}|(?=[a-z]*\d)(?=\d*[a-z])[a-z0-9]{14,}", slug))


def robots_directives(page, headers):
    """meta robots, meta googlebot and the X-Robots-Tag header as one lowercase string.
    All three carry the same directives, so a check that reads one of them misses the other two."""
    return " ".join((page.metas.get("robots", ""), page.metas.get("googlebot", ""),
                     headers.get("x-robots-tag", ""))).lower()


# Types Google shows stars for. A rating on any other node is a site rating itself: "If the entity
# that's being reviewed controls the reviews about itself, their pages that use LocalBusiness or any
# other type of Organization structured data are ineligible for star review feature" (Google).
REVIEWABLE = {"product", "book", "course", "event", "movie", "recipe", "softwareapplication",
              "mobileapplication", "webapplication", "game", "videogame", "mediaobject",
              "musicplaylist", "musicrecording", "episode", "creativeworkseason", "creativeworkseries"}

# Markup that earns no rich result on an ordinary site. Each line has a row in seo/references/sources.md.
NO_RICH_RESULT = {
    "faqpage": "FAQ rich results only for well-known government and health sites since 2023",
    "howto": "HowTo rich results deprecated in 2023",
    "searchaction": "the sitelinks search box was removed in November 2024",
}


def schema_nodes(obj, out):
    """Every node carrying an @type in a JSON-LD document, @graph and nesting included."""
    if isinstance(obj, list):
        for x in obj:
            schema_nodes(x, out)
    elif isinstance(obj, dict):
        if "@type" in obj:
            out.append(obj)
        for v in obj.values():
            schema_nodes(v, out)
    return out


def node_types(node):
    t = node.get("@type")
    if isinstance(t, str):
        return [t]
    return [x for x in t if isinstance(x, str)] if isinstance(t, list) else []


class Report:
    def __init__(self):
        self.items = []  # (section, level, check_id, message)

    def add(self, section, level, cid, msg, data=None):
        """data: the full list behind a message that shows only examples; printed by --json."""
        item = {"section": section, "level": level, "id": cid, "message": msg}
        if data is not None:
            item["data"] = data
        self.items.append(item)

    def counts(self):
        return Counter(i["level"] for i in self.items)

# --------------------------------------------------------------------------- page checks

def check_page(url, rep, timeout, delay, section="Page", compare_ua=True):
    bot = fetch(url, UA_BOT, timeout, delay=delay)
    if bot["error"] or bot["status"] is None:
        rep.add(section, "FAIL", "http.fetch", f"{url}: {bot['error']}")
        return bot, None
    final = bot["final_url"]
    hops = len(bot["chain"]) - 1
    if hops:
        chain = " -> ".join(f"{u} [{s}]" for u, s in bot["chain"])
        level = "WARN" if hops > 1 else "INFO"
        rep.add(section, level, "http.redirect-chain",
                f"{hops} redirect hop(s): {chain}" + (" (collapse to a single 301)" if hops > 1 else "")
                + (" (Google's crawlers follow at most 10 hops; Mueller advises under 5)" if hops >= 5 else ""))
        temp = [s for _, s in bot["chain"] if s in (302, 303, 307)]
        if temp:
            rep.add(section, "WARN", "http.redirect-temporary",
                    f"Chain uses temporary redirect(s) {temp}: Google follows them but does not treat the target as canonical. "
                    "Use 301 or 308 for a permanent move.")
    if bot["status"] != 200:
        rep.add(section, "FAIL", "http.status", f"{final} returned {bot['status']}")
        return bot, None
    if not final.startswith("https://"):
        rep.add(section, "FAIL", "http.https", f"{final} is served without HTTPS")
    p = parse(bot["body"], final)
    robots_meta = robots_directives(p, bot["headers"])
    noindex = "noindex" in robots_meta
    if noindex:
        rep.add(section, "FAIL", "head.noindex", f"{final} carries noindex ({robots_meta.strip()}). Intended?")
    if p.meta_refresh is not None:
        # Own name: `delay` is the seconds between requests and is still needed below.
        refresh_seconds = re.match(r"\s*(\d+)", p.meta_refresh or "")
        instant = refresh_seconds and int(refresh_seconds.group(1)) == 0
        rep.add(section, "WARN", "head.meta-refresh",
                f"Meta refresh present ({p.meta_refresh!r}): Google reads an instant one as a permanent redirect and a delayed one as temporary. "
                "Prefer a server-side 301/308." if instant else
                f"Delayed meta refresh ({p.meta_refresh!r}): Google treats it as a temporary redirect. Prefer a server-side 301/308.")

    # Rendering: does the bot response carry real content the crawler can use? Four signals, because each
    # one alone lets a shell through. Text length: measured 2026-09-04, a shell with a marketing sentence
    # and "Loading..." clears 300 characters. Text outside header/nav/footer/aside: a menu and a footer
    # clear it again, and they are identical on every page. Internal links: only <a href> is crawlable.
    # An empty mount point: the shell of a JavaScript framework, whatever its nav and footer weigh.
    if compare_ua:
        internal = sum(1 for href, _ in p.links if same_site(href, final))
        own = p.text_chars - p.chrome_chars
        root = APP_ROOT_RE.search(bot["body"])
        why = []
        if p.text_chars < 300:
            why.append(f"{p.text_chars} chars of visible text")
        elif own < 300:     # the total already says it; the split only adds something above the threshold
            why.append(f"{own} chars outside header/nav/footer/aside")
        if internal == 0:
            why.append("no internal links")
        if root:
            why.append(f'an empty <{root.group(1).lower()} id="{root.group(2)}">')
        if why:
            browser = fetch(final, UA_BROWSER, timeout, delay=delay)
            pb = parse(browser["body"], final) if browser["body"] else None
            js = p.script_bytes > 20_000 or p.script_srcs or len(re.findall(r"<script", bot["body"], re.I)) > 5
            if pb and pb.text_chars > p.text_chars * 2 + 200:
                rep.add(section, "FAIL", "render.bot-html",
                        f"Googlebot UA gets {p.text_chars} chars of text, browser UA gets {pb.text_chars}: "
                        "server discriminates by user agent")
            elif js:
                rep.add(section, "FAIL", "render.bot-html",
                        "The crawler sees a shell (" + ", ".join(why) + ") and the page runs JavaScript. "
                        "Serve it as HTML (SSR/SSG).", data=why)
            else:
                rep.add(section, "WARN", "render.thin", "Little for the crawler: " + ", ".join(why), data=why)
            cmp_hit = CMP_RE.search(bot["body"])
            if cmp_hit:
                rep.add(section, "WARN", "render.consent-wall",
                        f"A consent platform ({cmp_hit.group(0)}) runs on this thin page. The banner may cover the "
                        "content for a reader, the text below it must still stand in the raw HTML. Fetch with "
                        "curl -sA Googlebot and read what is there before treating the thinness as a rendering bug.")
        else:
            rep.add(section, "PASS", "render.bot-html",
                    f"{p.text_chars} chars of visible text ({own} outside header/nav/footer/aside) and "
                    f"{internal} internal links in the raw HTML")

    # Head
    if not p.title:
        rep.add(section, "FAIL", "head.title", "No <title>")
    else:
        n = len(p.title)
        if n > 60:
            rep.add(section, "WARN", "head.title", f"Title is {n} chars (heuristic: about 60, Google truncates by pixel width; keyword first): “{p.title}”")
        elif n < 20:
            rep.add(section, "WARN", "head.title", f"Title is only {n} chars: “{p.title}”")
        else:
            rep.add(section, "PASS", "head.title", f"“{p.title}” ({n} chars)")
    desc = p.metas.get("description")
    if not desc:
        rep.add(section, "WARN", "head.meta-description", "No meta description (Google will invent one)")
    elif len(desc) > 160:
        rep.add(section, "WARN", "head.meta-description", f"Meta description is {len(desc)} chars (heuristic: 120–160; Google sets no limit)")
    else:
        rep.add(section, "PASS", "head.meta-description", f"{len(desc)} chars")
    if not p.canonicals:
        rep.add(section, "FAIL", "head.canonical", "No canonical link. Add a self-referencing absolute canonical.")
    elif len(p.canonicals) > 1:
        rep.add(section, "FAIL", "head.canonical", f"{len(p.canonicals)} canonical links: {p.canonicals}")
    else:
        c = p.canonicals[0]
        if not c.startswith("http"):
            rep.add(section, "WARN", "head.canonical", f"Canonical is not absolute: {c}")
        elif norm(c) != norm(final):
            rep.add(section, "WARN", "head.canonical", f"Canonical points elsewhere: {c} (this page will not be indexed on its own URL. Intended?)")
            if noindex:
                rep.add(section, "WARN", "head.noindex-canonical",
                        "noindex plus a canonical to another URL on the same page: mixed signals. Pick one (Mueller, 2024).")
            m = re.search(r"(?:[?&]page=|/page/|/seite/)(\d+)", final)
            if m and int(m.group(1)) >= 2:
                rep.add(section, "WARN", "url.pagination-canonical",
                        f"Paginated page {m.group(1)} canonicalizes to another URL. Google: give each page its own canonical, do not point page 2+ at page 1.")
        else:
            rep.add(section, "PASS", "head.canonical", "self-referencing")
    if "viewport" not in p.metas:
        rep.add(section, "FAIL", "head.viewport", "No viewport meta: page is not mobile-friendly")
    if not p.lang:
        rep.add(section, "WARN", "head.lang", "No lang attribute on <html>")
    if p.hreflang:
        codes = [c.lower() for c, _ in p.hreflang]
        problems = []
        if not any(norm(h) == norm(final) for _, h in p.hreflang):
            problems.append("no self-referencing alternate (each version must list itself)")
        if "x-default" not in codes:
            problems.append("no x-default")
        bad = [c for c, _ in p.hreflang if c.lower() != "x-default" and not re.fullmatch(r"[a-z]{2,3}(-[a-z]{2}|-[0-9]{3}|-[a-z]{4}(-[a-z]{2})?)?", c.lower())]
        bad += [c for c, _ in p.hreflang if c.lower().split("-")[-1] in ("uk", "eu", "un")]
        if bad:
            problems.append(f"invalid codes {sorted(set(bad))} (language first, ISO 3166 region; UK/EU/UN are ignored)")
        if problems:
            rep.add(section, "WARN", "head.hreflang", f"{len(p.hreflang)} hreflang alternates, " + "; ".join(problems))
        else:
            rep.add(section, "PASS", "head.hreflang", f"{len(p.hreflang)} alternates incl. self and x-default (return links not verified)")
    dates = {}
    for t in p.jsonld_texts:
        for key in ("datePublished", "dateModified"):
            m = re.search(r'"%s"\s*:\s*"(\d{4}-\d{2}-\d{2})' % key, t)
            if m:
                dates.setdefault(key, m.group(1))
    if dates:
        today = time.strftime("%Y-%m-%d")
        future = [f"{k}={v}" for k, v in dates.items() if v > today]
        if future:
            rep.add(section, "WARN", "head.dates", f"Structured-data date in the future: {future}. Google: dates must be the real publish/update date, never a future date.")
        elif "datePublished" in dates and "dateModified" in dates and dates["dateModified"] < dates["datePublished"]:
            rep.add(section, "WARN", "head.dates", f"dateModified {dates['dateModified']} is before datePublished {dates['datePublished']}")
        else:
            rep.add(section, "INFO", "head.dates", f"JSON-LD dates {dates}; the visible date on the page must match them (not checked)")
    check_schema(p, rep, section)
    missing_og = [k for k in ("og:title", "og:description", "og:image") if k not in p.metas]
    if missing_og:
        rep.add(section, "INFO", "head.open-graph", f"Missing Open Graph tags: {', '.join(missing_og)}")

    # Body
    if not p.h1s:
        rep.add(section, "WARN", "body.h1", "No <h1> (Google does not require one; readers and the title/H1 keyword match do)")
    elif len(p.h1s) > 1:
        rep.add(section, "INFO", "body.h1", f"{len(p.h1s)} <h1> elements (Google accepts several; one is the convention): {p.h1s[:3]}")
    else:
        rep.add(section, "PASS", "body.h1", f"“{p.h1s[0]}”")
    # English and German error phrases (soft-404 detection).
    err_words = r"not found|no results|nicht gefunden|keine ergebnisse|page unavailable|seite nicht verfügbar|404"
    err_hit = [x for x in ([p.title or ""] + p.h1s[:1]) if re.search(err_words, x, re.I)]
    if err_hit:
        rep.add(section, "WARN", "body.error-text", f"Title or H1 reads like an error page: {err_hit[:1]}. Google may classify a 200 page as soft 404 from its text alone.")
    if p.h1s and p.title:
        overlap = tokens(p.h1s[0]) & tokens(p.title)
        if not overlap:
            rep.add(section, "WARN", "body.h1-title-match", "H1 and title share no keyword")
    slug = urllib.parse.urlsplit(final).path.rstrip("/").split("/")[-1]
    if urllib.parse.urlsplit(final).query:
        rep.add(section, "WARN", "url.query-string", "Indexable URL carries a query string")
    if slug:
        if looks_random(slug):
            rep.add(section, "WARN", "url.slug", f"Slug looks machine-generated: {slug}")
        if "_" in slug or slug != slug.lower():
            rep.add(section, "WARN", "url.slug", f"Slug uses underscores or uppercase: {slug}")
        if p.h1s and not (tokens(slug.replace("-", " ")) & tokens(p.h1s[0])):
            rep.add(section, "INFO", "url.slug-h1-match", f"Slug “{slug}” shares no keyword with the H1 (a very small ranking factor; matters for readers and link previews)")
    imgs = [i for i in p.images if not i["src"].startswith("data:")]
    noalt = [i["src"] for i in imgs if not i["alt"]]
    if imgs and noalt:
        rep.add(section, "WARN", "img.alt", f"{len(noalt)}/{len(imgs)} images without alt attribute, e.g. {noalt[:3]}")
    elif imgs:
        rep.add(section, "PASS", "img.alt", f"all {len(imgs)} images have alt")
    nosrc = [i["src"] for i in imgs if not i["has_src"]]
    if nosrc:
        rep.add(section, "WARN", "img.src-fallback", f"{len(nosrc)} <img> without a src attribute (data-src only), e.g. {nosrc[:3]}. Google asks for a fallback src; JS-only lazy loading hides the image until rendering.")
    if imgs and imgs[0]["lazy"]:
        rep.add(section, "WARN", "img.lcp-lazy", f"First image is loading=\"lazy\" ({imgs[0]['src']}). If it is the LCP element, lazy-loading delays LCP; use fetchpriority=\"high\" instead (web.dev).")
    unsized = [i["src"] for i in imgs if not i["sized"]]
    if imgs and len(unsized) > len(imgs) // 2:
        rep.add(section, "INFO", "img.dimensions", f"{len(unsized)}/{len(imgs)} images without width and height attributes (layout shift risk, CLS)")
    internal = [h for h, _ in p.links if same_site(h, final)]
    if not internal:
        rep.add(section, "WARN", "links.internal", "No internal links on the page")
    else:
        rep.add(section, "PASS", "links.internal", f"{len(internal)} internal links")
    if bot["elapsed"] > 2.5:
        rep.add(section, "WARN", "http.ttfb", f"HTML took {bot['elapsed']:.1f}s to arrive")
    return bot, p

# --------------------------------------------------------------------------- site checks

def check_site(start_final, rep, timeout, delay, page=None, page_headers=None):
    u = urllib.parse.urlsplit(start_final)
    origin = f"{u.scheme}://{u.netloc}"
    host = u.netloc
    sitemap_urls = set()

    # robots.txt
    rtxt = fetch(origin + "/robots.txt", UA_BOT, timeout, delay=delay)
    rp = None
    if rtxt["status"] == 200 and rtxt["body"]:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(rtxt["body"].splitlines())
        if not rp.can_fetch("Googlebot", start_final):
            rep.add("Site", "FAIL", "site.robots", f"robots.txt blocks Googlebot from {start_final}")
            if page is not None and "noindex" in (page.metas.get("robots", "") + page.metas.get("googlebot", "")).lower():
                rep.add("Site", "FAIL", "site.robots-noindex",
                        "Page is blocked by robots.txt and carries noindex: Google never sees the noindex, the URL can stay indexed. Unblock it if the goal is removal.")
        else:
            rep.add("Site", "PASS", "site.robots", "robots.txt present, page allowed")
        blocked_ai = [b for b in ("OAI-SearchBot", "PerplexityBot", "Bingbot", "Claude-SearchBot") if not rp.can_fetch(b, start_final)]
        if blocked_ai:
            rep.add("Site", "WARN", "site.robots-ai-search", f"robots.txt blocks {', '.join(blocked_ai)}: the page cannot be cited by ChatGPT search / Perplexity / Bing-based assistants / Claude")
        sm = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rtxt["body"])
        if sm:
            sitemap_urls.update(sm)
        else:
            rep.add("Site", "WARN", "site.robots-sitemap", "robots.txt has no Sitemap: line")
    else:
        rep.add("Site", "WARN", "site.robots", f"robots.txt returned {rtxt['status']} (add one: allow public paths, list the sitemap)")
    if not sitemap_urls:
        sitemap_urls.add(origin + "/sitemap.xml")

    # sitemap
    urls_in_sitemap = set()
    lastmod = 0
    lastmod_values = []
    seen_maps = set()
    queue = deque(sitemap_urls)
    while queue and len(seen_maps) < 20:
        smu = queue.popleft()
        if smu in seen_maps:
            continue
        seen_maps.add(smu)
        if not routable(smu, origin):
            rep.add("Site", "FAIL", "site.sitemap",
                    f"{smu} names an address that is not reachable from the public internet; "
                    "not fetched. A sitemap is content the site serves, and it does not get to "
                    "aim this machine at the network it runs in")
            continue
        r = fetch(smu, UA_BOT, timeout, delay=delay)
        if r["status"] != 200 or not r["body"]:
            rep.add("Site", "FAIL", "site.sitemap", f"{smu} returned {r['status'] if r['status'] else 'no response (' + str(r['error']) + ')'}")
            continue
        body = r["body"]
        if "<sitemapindex" in body:
            queue.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body))
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
        urls_in_sitemap.update(locs)
        mods = re.findall(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", body)
        lastmod += len(mods)
        lastmod_values.extend(mods)
    if urls_in_sitemap:
        foreign = [x for x in urls_in_sitemap if not same_site(x, origin)]
        http_only = [x for x in urls_in_sitemap if x.startswith("http://")]
        msg = f"{len(urls_in_sitemap)} unique URLs in {len(seen_maps)} sitemap file(s), {lastmod} with <lastmod>"
        rep.add("Site", "PASS" if lastmod else "WARN", "site.sitemap",
                msg + ("" if lastmod else ". Add real <lastmod> dates; Google ignores priority/changefreq"))
        if lastmod_values:
            today = time.strftime("%Y-%m-%d")
            days = [v[:10] for v in lastmod_values]
            future = [v for v in days if v > today]
            top, top_n = Counter(days).most_common(1)[0]
            if future:
                rep.add("Site", "WARN", "site.sitemap-lastmod", f"{len(future)} <lastmod> values lie in the future (e.g. {future[:2]}); Google discards lastmod it cannot trust")
            if len(days) >= 10 and top_n >= 0.9 * len(days):
                rep.add("Site", "WARN", "site.sitemap-lastmod",
                        f"{top_n}/{len(days)} URLs share the same <lastmod> {top}: looks like the generation date, not real changes. "
                        "Google uses lastmod only when it is consistently accurate and stops trusting it otherwise.")
        if foreign:
            rep.add("Site", "WARN", "site.sitemap-hosts", f"{len(foreign)} sitemap URLs on another host, e.g. {foreign[:2]}")
        if http_only:
            rep.add("Site", "WARN", "site.sitemap-hosts", f"{len(http_only)} sitemap URLs use http://")
        if norm(start_final) not in {norm(x) for x in urls_in_sitemap} and len(urls_in_sitemap) < 50_000:
            rep.add("Site", "INFO", "site.sitemap-membership", "The audited URL is not listed in the sitemap")

    # RSS/Atom feed: Google accepts it as a sitemap, and WebSub can push changes
    if page is not None and page.feeds:
        rep.add("Site", "INFO", "site.feed", f"Feed found ({page.feeds[0][1]}): submit it in GSC as an extra sitemap for fast discovery of new posts")

    # www / non-www and http -> https
    alt_host = host[4:] if host.startswith("www.") else "www." + host
    alt = fetch(f"{u.scheme}://{alt_host}{u.path}", UA_BOT, timeout, delay=delay)
    if alt["status"] == 200 and norm(alt["final_url"]) != norm(start_final):
        rep.add("Site", "FAIL", "site.host-variant", f"{alt_host} serves the page too (200) without redirecting. Pick one host and 301 the other")
    elif alt["status"] == 200:
        rep.add("Site", "PASS", "site.host-variant", f"{alt_host} redirects to {host}")
    elif alt["status"] is None:
        rep.add("Site", "INFO", "site.host-variant", f"{alt_host} does not resolve (fine if you never advertised it)")
    else:
        rep.add("Site", "WARN", "site.host-variant", f"{alt_host} returned {alt['status']}")
    if u.scheme == "https":
        plain = fetch(f"http://{host}{u.path}", UA_BOT, timeout, delay=delay)
        if plain["status"] == 200 and plain["final_url"].startswith("http://"):
            rep.add("Site", "FAIL", "site.http-redirect", "http:// serves content instead of redirecting to https://")
        elif plain["status"] == 200:
            rep.add("Site", "PASS", "site.http-redirect", "http:// redirects to https://")
    # Read the header from the page's own response first: an unreachable robots.txt would otherwise
    # report a missing header that the site does send.
    if u.scheme == "https" and not ((page_headers or {}).get("strict-transport-security")
                                    or rtxt["headers"].get("strict-transport-security")):
        rep.add("Site", "INFO", "site.hsts", "No Strict-Transport-Security header")

    # soft 404
    junk = "".join(random.choices(string.ascii_lowercase, k=12))
    nf = fetch(f"{origin}/{junk}-does-not-exist", UA_BOT, timeout, delay=delay)
    if nf["status"] == 200:
        rep.add("Site", "FAIL", "site.soft-404", "Unknown URLs return 200 (soft 404). Return a real 404/410")
    elif nf["status"] in (404, 410):
        rep.add("Site", "PASS", "site.soft-404", f"unknown URLs return {nf['status']}")
    elif nf["status"]:
        rep.add("Site", "WARN", "site.soft-404", f"Unknown URL returned {nf['status']}")

    # trailing slash variant
    if len(u.path) > 1:
        variant = start_final[:-1] if start_final.endswith("/") else start_final + "/"
        v = fetch(variant, UA_BOT, timeout, delay=delay)
        if v["status"] == 200 and norm(v["final_url"]) == norm(start_final) and len(v["chain"]) == 1:
            pv = parse(v["body"], variant)
            if not pv.canonicals:
                rep.add("Site", "WARN", "site.trailing-slash", "Both slash and no-slash variants return 200 without a canonical: duplicate URLs")
    return urls_in_sitemap, rp

# --------------------------------------------------------------------------- crawl

def crawl(start_final, limit, rep, timeout, delay, urls_in_sitemap, rp=None):
    seen = {norm(start_final): start_final}
    q = deque([start_final])
    pages = {}  # final_url -> dict(title, desc, canonical, status)
    pages_seen = set()  # norm(final_url), so one page parsed twice via redirects counts once
    link_targets = Counter()
    link_sources = {}  # norm(target) -> first page linking to it
    redirected_links = {}
    broken = {}
    tracking_links = []  # (source page, href with tracking parameters)
    cart_links = Counter()  # cart/checkout targets, not fetched
    disallowed = {}  # norm(url) -> url, robots.txt says no; reported, never fetched
    while q and len(pages) < limit:
        url = q.popleft()
        if rp is not None and not rp.can_fetch("Googlebot", url):
            disallowed[norm(url)] = url
            continue
        r = fetch(url, UA_BOT, timeout, delay=delay)
        if r["status"] is None:
            broken[url] = r["error"]
            continue
        if len(r["chain"]) > 1 and url != start_final:
            redirected_links[url] = r["final_url"]
        if r["status"] != 200:
            broken[url] = r["status"]
            continue
        if "html" not in r["headers"].get("content-type", "html"):
            continue
        final = r["final_url"]
        if not same_site(final, start_final):
            continue  # redirected off-site: not our page
        if norm(final) in pages_seen:
            continue  # a redirect landed on a page already parsed (e.g. host vs host/)
        pages_seen.add(norm(final))
        p = parse(r["body"], final)
        pages[final] = {"title": p.title, "desc": p.metas.get("description"),
                        "canonical": p.canonicals[0] if p.canonicals else None,
                        "h1": len(p.h1s), "noindex": "noindex" in robots_directives(p, r["headers"])}
        for href, rel in p.links:
            if not same_site(href, start_final):
                continue
            href = href.split("#")[0]
            if re.search(r"\.(png|jpe?g|gif|svg|webp|pdf|zip|mp4|css|js|ico|xml)$", href, re.I) or "/cdn-cgi/" in href:
                continue
            if is_cart(href):
                cart_links[norm(href)] += 1
                continue
            clean = strip_tracking(href)
            if clean != href:
                tracking_links.append((final, href))
                href = clean
            link_targets[norm(href)] += 1
            link_sources.setdefault(norm(href), final)
            if norm(href) not in seen:
                seen[norm(href)] = href
                q.append(href)
    truncated = bool(q)
    rep.add("Crawl", "INFO", "crawl.size",
            f"Crawled {len(pages)} pages" + (f" (limit hit, {len(q)} URLs left in queue, orphan check skipped)" if truncated else " (site exhausted)"))
    if disallowed:
        rep.add("Crawl", "INFO", "crawl.robots-disallowed",
                f"{len(disallowed)} linked URLs are disallowed in robots.txt and were not fetched, "
                f"e.g. {sorted(disallowed.values())[:3]}. Googlebot stops at the same line.",
                data=sorted(disallowed.values()))
    for url, status in list(broken.items())[:30]:
        rep.add("Crawl", "FAIL", "crawl.broken-link", f"Internal link target {url} -> {status} (linked from {link_sources.get(norm(url), '?')})")
    if len(broken) > 30:
        rep.add("Crawl", "FAIL", "crawl.broken-link", f"{len(broken) - 30} more broken link targets not listed (full list in --json)",
                data=[{"link": u, "status": st, "from": link_sources.get(norm(u))} for u, st in broken.items()])
    redirected_links = {s: d for s, d in redirected_links.items() if not is_cart(d)}  # a shortlink into the cart is a cart link
    for src, dst in list(redirected_links.items())[:30]:
        rep.add("Crawl", "WARN", "crawl.redirected-link", f"Internal link points at redirecting URL {src} -> {dst} (link the final URL; linked from {link_sources.get(norm(src), '?')})")
    if len(redirected_links) > 30:
        rep.add("Crawl", "INFO", "crawl.redirected-link", f"{len(redirected_links) - 30} more redirecting link targets not listed (full list in --json)",
                data=[{"link": s, "final": d, "from": link_sources.get(norm(s))} for s, d in redirected_links.items()])
    if tracking_links:
        pages_with = sorted({src for src, _ in tracking_links})
        rep.add("Crawl", "WARN", "crawl.tracking-params",
                f"{len(tracking_links)} internal links carry tracking parameters (utm_*, gclid, ...), e.g. {[h for _, h in tracking_links[:3]]}. "
                f"Each variant can be crawled and indexed as a duplicate of the clean URL; link the clean URL and measure in analytics by referrer. Linked from {len(pages_with)} page(s)",
                data=[{"from": s, "link": h} for s, h in tracking_links])
    if cart_links:
        rep.add("Crawl", "INFO", "crawl.cart-links",
                f"{sum(cart_links.values())} links to {len(cart_links)} cart/checkout/account URLs not crawled (noindex by design)",
                data=sorted(cart_links))
    indexable = {u: v for u, v in pages.items()
                 if not v["noindex"] and (not v["canonical"] or norm(v["canonical"]) == norm(u))}
    skipped = len(pages) - len(indexable)
    if skipped:
        rep.add("Crawl", "INFO", "crawl.non-indexable", f"{skipped} crawled URLs are noindex or canonicalize elsewhere (cart, tracking, variants); excluded from duplicate checks")
    by_title = Counter(v["title"] for v in indexable.values() if v["title"])
    for t, n in by_title.items():
        if n > 1:
            urls = [u for u, v in indexable.items() if v["title"] == t][:5]
            paginated = all(re.search(r"(?:[?&]page=|/page/|/seite/)\d+", u) for u in urls[1:])
            rep.add("Crawl", "INFO" if paginated else "WARN", "crawl.duplicate-title",
                    f"{n} pages share title “{t}”: {urls}" + (" (paginated series: add the page number to the title)" if paginated else ""),
                    data=[u for u, v in indexable.items() if v["title"] == t])
    by_desc = Counter(v["desc"] for v in indexable.values() if v["desc"])
    for d, n in by_desc.items():
        if n > 1:
            urls = [u for u, v in indexable.items() if v["desc"] == d][:5]
            paginated = all(re.search(r"(?:[?&]page=|/page/|/seite/)\d+", u) for u in urls[1:])
            rep.add("Crawl", "INFO" if paginated else "WARN", "crawl.duplicate-description", f"{n} pages share the same meta description: {urls}",
                    data=[u for u, v in indexable.items() if v["desc"] == d])
    no_canon = [u for u, v in pages.items() if not v["canonical"] and not v["noindex"]]
    if no_canon:
        rep.add("Crawl", "FAIL", "crawl.canonical", f"{len(no_canon)} crawled pages without canonical, e.g. {no_canon[:5]}", data=no_canon)
    pag = [u for u, v in pages.items() if v["canonical"] and norm(v["canonical"]) != norm(u)
           and (m := re.search(r"(?:[?&]page=|/page/|/seite/)(\d+)", u)) and int(m.group(1)) >= 2]
    if pag:
        rep.add("Crawl", "WARN", "crawl.pagination-canonical", f"{len(pag)} paginated pages canonicalize elsewhere (Google: each page keeps its own canonical), e.g. {pag[:3]}")
    multi_h1 = [u for u, v in indexable.items() if v["h1"] != 1]
    if multi_h1:
        rep.add("Crawl", "INFO", "crawl.h1", f"{len(multi_h1)} indexable pages with zero or multiple H1, e.g. {multi_h1[:5]}", data=multi_h1)
    if urls_in_sitemap:
        crawled = {norm(u) for u in pages}
        orphans = [x for x in urls_in_sitemap if norm(x) not in crawled and norm(x) not in link_targets]
        if orphans and not truncated:
            rep.add("Crawl", "WARN", "crawl.orphans", f"{len(orphans)} sitemap URLs have no internal link pointing at them, e.g. {orphans[:5]}", data=orphans)
        elif not orphans and not truncated:
            rep.add("Crawl", "PASS", "crawl.orphans", "every sitemap URL is internally linked")
        not_in_map = [u for u in pages if norm(u) not in {norm(x) for x in urls_in_sitemap} and not pages[u]["noindex"]]
        if not_in_map:
            rep.add("Crawl", "INFO", "crawl.not-in-sitemap", f"{len(not_in_map)} crawled pages missing from the sitemap, e.g. {not_in_map[:5]}", data=not_in_map)

# --------------------------------------------------------------------------- main

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


def check_rendered(path, raw, final, rep, section="Page"):
    """Compare a saved rendered DOM against the raw fetch of the same URL.

    Fields, not text: hydration markers and attribute order make a literal diff noise.
    """
    try:
        body = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        rep.add(section, "FAIL", "render.js-only", f"cannot read {path}: {e}")
        return
    r = parse(body, final)
    raw_internal = sum(1 for href, _ in raw.links if same_site(href, final))
    ren_internal = sum(1 for href, _ in r.links if same_site(href, final))
    only = []
    if not raw.title and r.title:
        only.append("title")
    if not raw.h1s and r.h1s:
        only.append("h1")
    if not raw.canonicals and r.canonicals:
        only.append("canonical")
    if r.text_chars > raw.text_chars * 2 + 200:
        only.append(f"body text ({raw.text_chars} raw, {r.text_chars} rendered)")
    if ren_internal > raw_internal * 2 + 5:
        only.append(f"internal links ({raw_internal} raw, {ren_internal} rendered)")
    if r.jsonld > raw.jsonld:
        only.append(f"structured data ({raw.jsonld} raw, {r.jsonld} rendered)")
    if only:
        rep.add(section, "FAIL", "render.js-only",
                "Exists only after JavaScript: " + ", ".join(only) + ". Google renders in a second pass; "
                "server-render or pre-render these.", data=only)
    else:
        rep.add(section, "PASS", "render.js-only", "The rendered DOM adds nothing the raw HTML lacks")
    gone = [name for name, a, b in (("title", raw.title, r.title), ("h1", raw.h1s, r.h1s),
                                    ("canonical", raw.canonicals, r.canonicals)) if a and not b]
    if gone:
        rep.add(section, "INFO", "render.raw-only",
                "In the raw HTML but not in the rendered DOM: " + ", ".join(gone) + ". JavaScript removes it.",
                data=gone)


def render(rep, url):
    c = rep.counts()
    counts = " · ".join(f"{paint(level, level)} {c.get(level, 0)}"
                        for level in ("FAIL", "WARN", "INFO", "PASS"))
    out = [paint(f"# Tech SEO audit: {url}", "head"), "", counts, ""]
    for section in ("Page", "Site", "Crawl"):
        items = [i for i in rep.items if i["section"] == section]
        if not items:
            continue
        out.append(paint(f"## {section}", "head"))
        out.append("")
        for i in sorted(items, key=lambda x: LEVEL_ORDER[x["level"]]):
            level = paint(f"**{i['level']}**", i["level"])
            out.append(f"- {level} `{paint(i['id'], 'id')}`: {i['message']}")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--crawl", type=int, default=0, metavar="N", help="crawl up to N internal pages for duplicates, broken links, orphans")
    ap.add_argument("--rendered", metavar="FILE", help="saved rendered DOM of URL itself; names what exists only after JavaScript")
    ap.add_argument("--redirects", metavar="FILE", help="CSV of the old URLs of a move (and their targets); each is fetched once")
    ap.add_argument("--timeout", type=float, default=15)
    ap.add_argument("--delay", type=float, default=0.25, help="seconds between requests")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    url = a.url if a.url.lower().startswith(("http://", "https://")) else "https://" + a.url
    rep = Report()
    bot, page = check_page(url, rep, a.timeout, a.delay)
    final = bot["final_url"] if bot["status"] == 200 else url
    sitemap, robots = set(), None
    if a.rendered and page:
        check_rendered(a.rendered, page, final, rep)
    if bot["status"]:
        sitemap, robots = check_site(final, rep, a.timeout, a.delay, page, bot["headers"])
        if a.crawl:
            crawl(final, a.crawl, rep, a.timeout, a.delay, sitemap, robots)
    if a.redirects:
        check_redirects(a.redirects, rep, a.timeout, a.delay)
    if a.json:
        print(json.dumps({"url": url, "final_url": final, "counts": rep.counts(), "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        print(render(rep, url))
    if a.crawl and not a.json:
        print("Full lists (every broken link, duplicate, orphan) are in the --json output.", file=sys.stderr)


if __name__ == "__main__":
    main()
