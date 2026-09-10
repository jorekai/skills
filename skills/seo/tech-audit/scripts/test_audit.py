#!/usr/bin/env python3
"""Offline tests for audit.py: URL normalization, tracking parameters, cart links, crawl dedupe.

Run: python3 skills/seo/tech-audit/scripts/test_audit.py
No network: fetch() is replaced by a fake site.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit  # noqa: E402

SCRIPT = os.path.abspath(audit.__file__)

HOST = "https://example.com"


def html(title, links=(), h1=True, canonical=None, robots=None):
    head = f"<title>{title}</title><meta name='description' content='desc of {title}'>"
    head += f"<link rel='canonical' href='{canonical}'>" if canonical else ""
    head += f"<meta name='robots' content='{robots}'>" if robots else ""
    body = (f"<h1>{title}</h1>" if h1 else "") + "".join(f"<a href='{l}'>x</a>" for l in links)
    return f"<html><head>{head}</head><body>{body}</body></html>"


# A fake site: one redirect lands on the host without a slash, one link carries utm_*, one links the cart.
SITE = {
    HOST + "/": (200, html("Home", [HOST + "/a/", HOST + "/old/", HOST + "/a/?utm_source=home", HOST + "/warenkorb/?add-to-cart=1", HOST + "/legal/"], canonical=HOST + "/")),
    HOST + "/a/": (200, html("A", [HOST + "/"], canonical=HOST + "/a/")),
    HOST + "/old/": (301, HOST),  # redirects to bare host: same page as "/"
    HOST: (200, html("Home", [HOST + "/a/"], canonical=HOST + "/")),
    HOST + "/legal/": (200, html("Legal", [], h1=False, canonical=HOST + "/legal/", robots="noindex")),
}


def fake_fetch(url, ua=None, timeout=15, max_hops=10, delay=0.0):
    chain = []
    current = url
    for _ in range(max_hops):
        status, payload = SITE.get(current, (404, ""))
        chain.append((current, status))
        if status in (301, 302):
            current = payload
            continue
        return {"url": url, "chain": chain, "final_url": current, "status": status,
                "headers": {"content-type": "text/html"}, "body": payload, "error": None, "elapsed": 0.01}
    raise AssertionError("redirect loop in fixture")


class Norm(unittest.TestCase):
    def test_root_with_and_without_slash_are_one_url(self):
        self.assertEqual(audit.norm(HOST), audit.norm(HOST + "/"))

    def test_trailing_slash_and_fragment_ignored(self):
        self.assertEqual(audit.norm(HOST + "/a/#x"), audit.norm(HOST + "/a"))

    def test_query_kept(self):
        self.assertNotEqual(audit.norm(HOST + "/a/?p=1"), audit.norm(HOST + "/a/"))


class Tracking(unittest.TestCase):
    def test_utm_stripped_other_params_kept(self):
        self.assertEqual(audit.strip_tracking(HOST + "/a/?utm_source=x&utm_medium=y&page=2"), HOST + "/a/?page=2")

    def test_clean_url_unchanged(self):
        self.assertEqual(audit.strip_tracking(HOST + "/a/?page=2"), HOST + "/a/?page=2")

    def test_click_ids(self):
        self.assertEqual(audit.strip_tracking(HOST + "/a/?gclid=abc"), HOST + "/a/")


class Cart(unittest.TestCase):
    def test_woocommerce_german_and_english(self):
        for u in ("/warenkorb/?add-to-cart=1", "/kasse/", "/cart/", "/checkout/", "/mein-konto/", "/a/?add-to-cart=5"):
            self.assertTrue(audit.is_cart(HOST + u), u)

    def test_content_is_not_cart(self):
        for u in ("/", "/a/", "/kassenbon-lesen/", "/carter-boats/"):
            self.assertFalse(audit.is_cart(HOST + u), u)


class Crawl(unittest.TestCase):
    def setUp(self):
        self._fetch = audit.fetch
        audit.fetch = fake_fetch
        self.rep = audit.Report()
        audit.crawl(HOST + "/", 50, self.rep, 5, 0, {HOST + "/", HOST + "/a/"})
        self.ids = {i["id"]: i for i in self.rep.items}

    def tearDown(self):
        audit.fetch = self._fetch

    def test_redirect_onto_bare_host_is_not_a_duplicate(self):
        self.assertNotIn("crawl.duplicate-title", self.ids, self.rep.items)
        self.assertIn("Crawled 3 pages", self.ids["crawl.size"]["message"])  # /, /a/, /legal/

    def test_redirected_link_reported_once(self):
        self.assertIn("crawl.redirected-link", self.ids)
        self.assertIn("/old/", self.ids["crawl.redirected-link"]["message"])

    def test_tracking_link_reported_and_clean_url_crawled(self):
        self.assertIn("crawl.tracking-params", self.ids)
        self.assertEqual(self.ids["crawl.tracking-params"]["data"], [{"from": HOST + "/", "link": HOST + "/a/?utm_source=home"}])

    def test_cart_link_counted_not_fetched(self):
        self.assertIn("crawl.cart-links", self.ids)
        self.assertNotIn("crawl.broken-link", self.ids)

    def test_h1_check_skips_noindex(self):
        self.assertNotIn("crawl.h1", self.ids)  # /legal/ has no H1 but is noindex

    def test_orphans_pass_when_queue_drained(self):
        self.assertEqual(self.ids["crawl.orphans"]["level"], "PASS")


class RobotsDirectives(unittest.TestCase):
    """A noindex can sit in three places; every check reads all three."""

    def test_x_robots_tag_header(self):
        page = audit.parse("<html><head><title>t</title></head><body>x</body></html>", HOST)
        self.assertIn("noindex", audit.robots_directives(page, {"x-robots-tag": "noindex, nofollow"}))

    def test_googlebot_meta(self):
        page = audit.parse("<html><head><meta name='googlebot' content='noindex'></head><body>x</body></html>", HOST)
        self.assertIn("noindex", audit.robots_directives(page, {}))


class RobotsCrawl(unittest.TestCase):
    """The crawl obeys robots.txt: a disallowed URL is reported, never fetched."""

    def setUp(self):
        self._fetch = audit.fetch
        self.asked = []

        def counting_fetch(url, ua=None, timeout=15, max_hops=10, delay=0.0):
            self.asked.append(url)
            return fake_fetch(url, ua, timeout, max_hops, delay)

        audit.fetch = counting_fetch
        rp = audit.urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Disallow: /a/"])
        self.rep = audit.Report()
        audit.crawl(HOST + "/", 50, self.rep, 5, 0, set(), rp)
        self.ids = {i["id"]: i for i in self.rep.items}

    def tearDown(self):
        audit.fetch = self._fetch

    def test_disallowed_url_not_fetched(self):
        self.assertNotIn(HOST + "/a/", self.asked)

    def test_disallowed_url_reported(self):
        self.assertEqual(self.ids["crawl.robots-disallowed"]["data"], [HOST + "/a/"])


class _FakeResponse:
    def __init__(self, status, headers):
        self.status, self.headers = status, headers

    def read(self, n=None):
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RedirectScheme(unittest.TestCase):
    """build_opener installs a FileHandler; a redirect must never reach it."""

    def setUp(self):
        self._opener = audit._OPENER
        audit._OPENER = type("O", (), {"open": staticmethod(
            lambda req, timeout=None: _FakeResponse(301, {"Location": "file:///etc/passwd"}))})()

    def tearDown(self):
        audit._OPENER = self._opener

    def test_non_http_target_is_refused(self):
        r = audit.fetch("https://example.com/")
        self.assertIsNone(r["status"])
        self.assertIn("non-HTTP", r["error"])
        self.assertEqual(r["body"], "")


class EntryScheme(unittest.TestCase):
    """A redirect was guarded and the first request was not, so remote content chose the scheme.

    robots.txt names the sitemap and a sitemapindex names the next one, both from the audited site.
    Either can say file:// or ftp://, and build_opener() carries the handlers for both.
    """

    def setUp(self):
        self.opened = []
        self._opener = audit._OPENER
        audit._OPENER = type("O", (), {"open": staticmethod(
            lambda req, timeout=None: self.opened.append(req) or _FakeResponse(200, {}))})()

    def tearDown(self):
        audit._OPENER = self._opener

    def test_a_file_target_is_refused_before_the_request_is_built(self):
        r = audit.fetch("file:///etc/passwd")
        self.assertEqual(self.opened, [])
        self.assertIsNone(r["status"])
        self.assertIn("not an HTTP target", r["error"])
        self.assertEqual(r["body"], "")

    def test_an_ftp_target_opens_no_connection(self):
        r = audit.fetch("ftp://example.invalid/x")
        self.assertEqual(self.opened, [])
        self.assertIn("not an HTTP target", r["error"])


class Routable(unittest.TestCase):
    """A sitemap is content the site serves, so it does not get to name an address in here.

    Every address below is a literal, so getaddrinfo answers without asking a resolver.
    """

    def test_loopback_private_and_link_local_are_refused(self):
        for host in ("127.0.0.1:8080", "192.168.1.1", "10.0.0.5", "169.254.169.254"):
            self.assertFalse(audit.routable(f"http://{host}/sitemap.xml", HOST), host)

    def test_a_public_address_is_allowed(self):
        self.assertTrue(audit.routable("http://93.184.216.34/sitemap.xml", HOST))

    def test_the_start_host_stays_allowed_whatever_it_resolves_to(self):
        """The operator aimed there; their own argument is not remote content."""
        self.assertTrue(audit.routable("http://127.0.0.1:8080/sitemap.xml", "http://127.0.0.1:8080"))


class MetaRefreshTest(unittest.TestCase):
    """A meta refresh must not overwrite the request delay: the browser-UA fetch sleeps on it."""

    # Thin page with a meta refresh: under 300 characters of text, so check_page compares user agents.
    THIN = ("<html lang='en'><head><title>Moved page</title>"
            "<meta http-equiv='refresh' content='0;url=https://elsewhere.example/'>"
            "<meta name='viewport' content='width=device-width'>"
            f"<link rel='canonical' href='{HOST}/'></head><body><h1>Moved</h1></body></html>")

    def setUp(self):
        self._fetch = audit.fetch
        self.delays = []

        def fake_fetch(url, ua=None, timeout=15, max_hops=10, delay=0.0):
            self.delays.append(delay)
            return {"url": url, "chain": [(url, 200)], "final_url": url, "status": 200,
                    "headers": {"content-type": "text/html"}, "body": self.THIN, "error": None, "elapsed": 0.1}

        audit.fetch = fake_fetch

    def tearDown(self):
        audit.fetch = self._fetch

    def test_delay_stays_a_number(self):
        rep = audit.Report()
        audit.check_page(HOST + "/", rep, 15, 0.25)
        ids = {i["id"] for i in rep.items}
        self.assertIn("head.meta-refresh", ids)
        self.assertEqual(self.delays, [0.25, 0.25])   # bot fetch, then browser fetch


SHELL_TEXT = ("draw a diagram in the browser. This app is free online diagram software. Use it as a flowchart "
              "maker, network diagram software, to create UML online, as an ER diagram tool, to design a "
              "database schema, to build BPMN online, as a circuit diagram maker, and more.")
SHELL = ("<html><head><title>Diagram app</title><link rel='canonical' href='" + HOST + "/app/'>"
         "<script src='/bundle.js'></script></head><body><h1>Diagram app</h1>"
         f"<p>{SHELL_TEXT}</p><div id='root'>Loading...</div>"
         "<p>Please ensure JavaScript is enabled.</p></body></html>")
FULL = ("<html><head><title>Guide</title><link rel='canonical' href='" + HOST + "/app/'></head><body>"
        f"<h1>Guide</h1><p>{SHELL_TEXT}</p><p>{SHELL_TEXT}</p>"
        f"<a href='{HOST}/a/'>a</a><a href='{HOST}/b/'>b</a></body></html>")


# A single-page app whose menu and footer clear every character threshold on their own: six internal
# links and more than 300 characters of text, with nothing but a mount point in between.
CHROME_SHELL = ("<html><head><title>Acme</title><link rel='canonical' href='" + HOST + "/app/'>"
                "<script src='/bundle.js'></script></head><body><nav>"
                + "".join(f"<a href='{HOST}/{s}/'>{s}</a>" for s in ("pricing", "blog", "about", "contact"))
                + f"</nav><div id='root'>Loading...</div><footer><a href='{HOST}/imprint/'>imprint</a>"
                f"<a href='{HOST}/privacy/'>privacy</a><p>{SHELL_TEXT}</p></footer></body></html>")
CONSENT_SHELL = CHROME_SHELL.replace("<body>", "<body><script src='https://consent.cookiebot.com/uc.js'></script>")


def one_page(body):
    """fetch() replacement that answers every request, both user agents, with the same body."""
    def f(url, ua=None, timeout=15, max_hops=10, delay=0.0):
        return {"url": url, "chain": [(url, 200)], "final_url": url, "status": 200,
                "headers": {"content-type": "text/html"}, "body": body, "error": None, "elapsed": 0.01}
    return f


class ShellPage(unittest.TestCase):
    """A shell whose boilerplate clears the 300-character mark still has nothing to crawl.

    Measured 2026-09-04 on a live single-page app: 386 characters of text, zero internal links.
    """
    def run_on(self, body):
        self._fetch = audit.fetch
        audit.fetch = one_page(body)
        try:
            rep = audit.Report()
            bot, page = audit.check_page(HOST + "/app/", rep, 5, 0)
            return page, {i["id"]: i for i in rep.items}
        finally:
            audit.fetch = self._fetch

    def test_shell_over_300_chars_without_internal_links_fails(self):
        page, ids = self.run_on(SHELL)
        self.assertGreaterEqual(page.text_chars, 300)  # the old text-only rule passed this page
        self.assertEqual(ids["render.bot-html"]["level"], "FAIL")
        self.assertIn("no internal links", ids["render.bot-html"]["message"])

    def test_shell_with_menu_and_footer_fails(self):
        """Nav plus footer clear both older rules: over 300 characters and six internal links."""
        page, ids = self.run_on(CHROME_SHELL)
        internal = sum(1 for href, _ in page.links if audit.same_site(href, HOST + "/app/"))
        self.assertGreaterEqual(page.text_chars, 300)
        self.assertGreater(internal, 0)
        self.assertEqual(ids["render.bot-html"]["level"], "FAIL")
        self.assertIn("outside header/nav/footer/aside", ids["render.bot-html"]["message"])
        self.assertIn('an empty <div id="root">', ids["render.bot-html"]["message"])

    def test_full_page_text_is_not_counted_as_chrome(self):
        page, _ = self.run_on(FULL)
        self.assertEqual(page.chrome_chars, 0)

    def test_consent_platform_named_on_a_thin_page(self):
        _, ids = self.run_on(CONSENT_SHELL)
        self.assertEqual(ids["render.consent-wall"]["level"], "WARN")
        self.assertIn("cookiebot", ids["render.consent-wall"]["message"])

    def test_consent_check_stays_quiet_on_a_full_page(self):
        _, ids = self.run_on(FULL.replace("<body>", "<body><script src='https://consent.cookiebot.com/uc.js'></script>"))
        self.assertNotIn("render.consent-wall", ids)

    def test_external_bundle_counts_as_javascript(self):
        page, _ = self.run_on(SHELL)
        self.assertEqual(page.script_srcs, 1)  # script_bytes stays 0: the bundle is not inline
        self.assertEqual(page.script_bytes, 0)

    def test_page_with_text_and_internal_links_passes(self):
        _, ids = self.run_on(FULL)
        self.assertEqual(ids["render.bot-html"]["level"], "PASS")
        self.assertIn("2 internal links", ids["render.bot-html"]["message"])


class Rendered(unittest.TestCase):
    """--rendered compares fields of the same URL, never raw HTML text."""
    def check(self, raw_body, rendered_body):
        rep = audit.Report()
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
            fh.write(rendered_body)
            path = fh.name
        try:
            audit.check_rendered(path, audit.parse(raw_body, HOST + "/app/"), HOST + "/app/", rep)
        finally:
            os.unlink(path)
        return {i["id"]: i for i in rep.items}

    def test_names_what_javascript_adds(self):
        ids = self.check(SHELL, SHELL.replace("<div id='root'>Loading...</div>",
                                              "<div id='root'><p>" + SHELL_TEXT * 4 + "</p>"
                                              + "".join(f"<a href='{HOST}/p{n}/'>p</a>" for n in range(20))
                                              + "</div>"))
        self.assertEqual(ids["render.js-only"]["level"], "FAIL")
        self.assertTrue(any(d.startswith("body text") for d in ids["render.js-only"]["data"]))
        self.assertTrue(any(d.startswith("internal links") for d in ids["render.js-only"]["data"]))

    def test_no_difference_passes(self):
        ids = self.check(FULL, FULL)
        self.assertEqual(ids["render.js-only"]["level"], "PASS")

    def test_missing_file_is_reported_not_raised(self):
        rep = audit.Report()
        audit.check_rendered("/no/such/file.html", audit.parse(FULL, HOST + "/"), HOST + "/", rep)
        self.assertEqual(rep.items[0]["level"], "FAIL")


class Schema(unittest.TestCase):
    """head.schema-*: what the markup is, what it cannot earn, and a rating a site gives itself."""

    def check(self, *blocks):
        body = ("<html><head><title>t</title>"
                + "".join(f"<script type='application/ld+json'>{b}</script>" for b in blocks)
                + "</head><body><h1>t</h1></body></html>")
        rep = audit.Report()
        audit.check_schema(audit.parse(body, HOST + "/"), rep, "Page")
        return {i["id"]: i for i in rep.items}

    def test_types_are_named_including_the_graph(self):
        ids = self.check('{"@graph":[{"@type":"Article"},{"@type":"BreadcrumbList"}]}')
        self.assertEqual(ids["head.json-ld"]["data"], ["Article", "BreadcrumbList"])

    def test_markup_without_a_rich_result_is_named(self):
        ids = self.check('{"@type":"FAQPage"}',
                         '{"@type":"WebSite","potentialAction":{"@type":"SearchAction"}}')
        self.assertIn("FAQPage", ids["head.schema-no-rich-result"]["message"])
        self.assertIn("SearchAction", ids["head.schema-no-rich-result"]["message"])

    def test_a_business_that_rates_itself_is_flagged(self):
        ids = self.check('{"@type":"LocalBusiness","aggregateRating":{"@type":"AggregateRating","ratingValue":5}}')
        self.assertEqual(ids["head.schema-review"]["level"], "WARN")

    def test_a_product_rating_is_left_alone(self):
        ids = self.check('{"@type":"Product","aggregateRating":{"@type":"AggregateRating","ratingValue":5}}')
        self.assertNotIn("head.schema-review", ids)

    def test_a_block_that_is_not_json_is_named_and_the_others_still_read(self):
        ids = self.check('{"@type":"Article",}', '{"@type":"Organization","name":"a"}')
        self.assertIn("block 1 of 2", ids["head.schema-invalid"]["message"])
        self.assertEqual(ids["head.json-ld"]["data"], ["Organization"])


OLD = "https://old.example.com"

# A move: one clean hop, a temporary hop, a chain, a dead target, a URL that never moved, a wrong target.
MOVED = {
    OLD + "/a/": (301, HOST + "/a/"),   HOST + "/a/": (200, "ok"),
    OLD + "/b/": (302, HOST + "/b/"),   HOST + "/b/": (200, "ok"),
    OLD + "/c/": (301, OLD + "/c2/"),   OLD + "/c2/": (301, HOST + "/c/"), HOST + "/c/": (200, "ok"),
    OLD + "/d/": (301, HOST + "/gone/"), HOST + "/gone/": (404, ""),
    OLD + "/e/": (200, "still here"),
    OLD + "/f/": (308, HOST + "/other/"), HOST + "/other/": (200, "ok"),
}

MAP = f"""old,new
{OLD}/a/,{HOST}/a/
{OLD}/b/,{HOST}/b/
{OLD}/c/,{HOST}/c/
{OLD}/d/,{HOST}/gone/
{OLD}/e/,{HOST}/e/
{OLD}/f/,{HOST}/f/
"""


def moved_fetch(url, ua=None, timeout=15, max_hops=10, delay=0.0):
    chain = []
    current = url
    for _ in range(max_hops):
        status, payload = MOVED.get(current, (404, ""))
        chain.append((current, status))
        if 300 <= status < 400:
            current = payload
            continue
        return {"url": url, "chain": chain, "final_url": current, "status": status,
                "headers": {"content-type": "text/html"}, "body": payload, "error": None, "elapsed": 0.0}
    raise AssertionError("redirect loop in fixture")


class RedirectMap(unittest.TestCase):
    """--redirects: one permanent hop per old URL, a live target, and the target the map names."""

    def run_map(self, text):
        real = audit.fetch
        audit.fetch = moved_fetch
        rep = audit.Report()
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            path = fh.name
        try:
            audit.check_redirects(path, rep, 5, 0)
        finally:
            audit.fetch = real
            os.unlink(path)
        return {i["id"]: i for i in rep.items}

    def test_every_shape_of_a_broken_move_is_named_once(self):
        ids = self.run_map(MAP)
        self.assertIn("6 rows checked, 1 land", ids["redirects.map"]["message"])
        self.assertIn("/b/", ids["redirects.temporary"]["message"])
        self.assertIn("2 hops", ids["redirects.chain"]["message"])
        self.assertIn("/d/", ids["redirects.broken"]["message"])
        self.assertIn("no redirect", ids["redirects.missing"]["message"])
        self.assertIn("/f/", ids["redirects.wrong-target"]["message"])
        self.assertEqual(ids["redirects.broken"]["level"], "FAIL")
        self.assertEqual(ids["redirects.temporary"]["level"], "WARN")

    def test_a_clean_map_passes(self):
        ids = self.run_map(f"old,new\n{OLD}/a/,{HOST}/a/\n")
        self.assertEqual(ids["redirects.map"]["level"], "PASS")
        self.assertEqual(len(ids), 1)

    def test_a_map_without_a_header_and_with_other_column_names(self):
        for text in (f"{OLD}/a/,{HOST}/a/\n", f"from,to\n{OLD}/a/,{HOST}/a/\n"):
            ids = self.run_map(text)
            self.assertEqual(ids["redirects.map"]["level"], "PASS", text)

    def test_a_file_without_urls_is_the_finding(self):
        ids = self.run_map("old,new\nnot a url,also not\n")
        self.assertEqual(ids["redirects.map"]["level"], "FAIL")


class ColourTest(unittest.TestCase):
    """Colour is a hint on a report that reads the same without it (decisions/0022)."""

    def report(self):
        rep = audit.Report()
        rep.add("Page", "FAIL", "title.missing", "no title")
        rep.add("Site", "WARN", "sitemap.stale", "lastmod is old")
        return rep

    def test_a_pipe_reads_plain_text(self):
        out = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True,
                             text=True).stdout
        self.assertNotIn("\033", out)

    def test_every_escape_removed_leaves_the_same_report(self):
        rep = self.report()
        audit.COLOUR = False
        plain = audit.render(rep, "https://example.com")
        audit.COLOUR = True
        painted = audit.render(rep, "https://example.com")
        audit.COLOUR = audit.colour_on()
        self.assertIn("\033", painted)
        self.assertEqual(re.sub(r"\033\[[0-9;]*m", "", painted), plain)


if __name__ == "__main__":
    unittest.main(verbosity=1)
