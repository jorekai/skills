#!/usr/bin/env python3
"""Offline tests for this skill's scripts: gsc_opportunities.py (brand filter on query rows
only, locale-safe numbers, single-column exports, site baseline, CTR calibration) and
snippets.py (non-HTTP URL and redirect target, title-no-query on content words).

Run: python3 skills/seo/gsc-review/scripts/test_gsc.py
No network: a fake export directory with Queries.csv and Pages.csv is written to a temp folder.
"""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsc_opportunities as g  # noqa: E402
import snippets  # noqa: E402

HOST = "https://example-bootsschule.de"

# German-locale export as GSC writes it: comma decimals, dot thousands, "%" in the CTR column.
QUERIES = """Suchanfragen,Klicks,Impressionen,CTR,Position
acme,"1.200","3.000","40 %","1,2"
acme bootsschule,300,900,"33,3 %","1,1"
boot mieten köln,90,"18.628","0,48 %","15,8"
bootsführerschein kosten,700,"145.000","0,5 %","5,8"
"""

PAGES = f"""Seiten,Klicks,Impressionen,CTR,Position
{HOST}/,"2.000","20.000","10 %","3,4"
{HOST}/boot-mieten-in-koeln/,90,"18.628","0,48 %","15,8"
{HOST}/bootsfuehrerschein-kosten/,700,"145.000","0,5 %","5,8"
"""


class Args:
    """The subset of argparse options the bucket functions read."""
    pos_min = 8
    pos_max = 20
    min_impressions = 50
    brand_re = re.compile("acme|acme bootsschule|akme|acme boot", re.I)


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        for name, text in (("Queries.csv", QUERIES), ("Pages.csv", PAGES)):
            with open(os.path.join(cls.tmp, name), "w", encoding="utf-8") as f:
                f.write(text)
        cls.queries, cls.pages = g.split_export(g.load_export(cls.tmp))

    def test_tables_found(self):
        self.assertEqual(len(self.queries), 4)
        self.assertEqual(len(self.pages), 3)

    def test_locale_numbers(self):
        row = next(r for r in self.queries if r["key"] == "boot mieten köln")
        self.assertEqual(row["impressions"], 18628)
        self.assertAlmostEqual(row["position"], 15.8)
        self.assertAlmostEqual(row["ctr"], 0.0048)
        big = next(r for r in self.queries if r["key"] == "acme")
        self.assertEqual(big["clicks"], 1200)
        self.assertAlmostEqual(big["ctr"], 0.40)

    def test_brand_filter_drops_brand_queries(self):
        keys = [r["key"] for r in g.striking(self.queries, Args())]
        self.assertEqual(keys, ["boot mieten köln"])

    def test_brand_in_host_keeps_page_rows(self):
        """The brand regex matches the host of every page URL; page buckets must not go empty."""
        keys = [r["key"] for r in g.striking(self.pages, Args(), is_query=False)]
        self.assertEqual(keys, [HOST + "/boot-mieten-in-koeln/"])
        gap = [r["key"] for r in g.ctr_gap(self.pages, Args(), is_query=False)]
        self.assertIn(HOST + "/bootsfuehrerschein-kosten/", gap)

    def test_ctr_gap_queries_skip_brand(self):
        gap = [r["key"] for r in g.ctr_gap(self.queries, Args())]
        self.assertIn("bootsführerschein kosten", gap)
        self.assertNotIn("acme", gap)


class RenderTest(unittest.TestCase):
    """decisions/0028: a bucket head names its parameters, then fixed-width rows, text left,
    numbers right."""

    class A:
        min_impressions = 50
        pos_min = 8
        pos_max = 20
        top = 25
        brand = None
        expected_ctr_1 = None

    def test_bucket_head_and_aligned_row(self):
        a = self.A()
        a.brand_re = None
        queries = [{"key": "how to sail", "clicks": 5, "impressions": 300, "ctr": 5 / 300, "position": 12.4}]
        res = {"n_queries": 1, "n_pages": 0, "brand": None,
               "striking_queries": g.striking(queries, a), "striking_pages": [],
               "ctr_gap_queries": [], "ctr_gap_pages": [],
               "decay": None, "cannibal": None, "not_indexed": None, "baseline": None,
               "calibration": g.ctr_calibration(queries, a),
               "totals": {"source": "queries", "previous": None, "now": g.totals(queries)}}
        out = g.render(res, a)
        self.assertIn("striking-q  1 queries  pos 8 to 20  min 50 impressions", out)
        self.assertIn("how to sail                                    300         5     1.7%    12.4", out)
        self.assertIn("\nnext  ", out)


class TotalsTest(unittest.TestCase):
    """Site totals sum the rows the export holds, and the export caps a table at 1,000 rows."""

    def test_sums_and_ctr(self):
        t = g.totals([{"key": "a", "clicks": 10, "impressions": 100, "ctr": .1, "position": 3},
                      {"key": "b", "clicks": 30, "impressions": 300, "ctr": .1, "position": 4}])
        self.assertEqual((t["rows"], t["clicks"], t["impressions"]), (2, 40, 400))
        self.assertAlmostEqual(t["ctr"], 0.1)

    def test_an_empty_table_does_not_divide_by_zero(self):
        self.assertEqual(g.totals([])["ctr"], 0.0)


class BaselineTest(unittest.TestCase):
    """Site-wide drift is the yardstick: one page counts as won only above the median page."""

    @staticmethod
    def pages(n, clicks, position, ctr=0.05, impressions=1000):
        return [{"key": f"{HOST}/p{i}/", "clicks": clicks, "impressions": impressions,
                 "ctr": ctr, "position": position} for i in range(n)]

    def test_median_change_of_all_pages(self):
        b = g.baseline(self.pages(12, 90, 5.5, 0.045), self.pages(12, 100, 5.0, 0.05), Args())
        self.assertEqual(b["n"], 12)
        self.assertAlmostEqual(b["position"], 0.5)
        self.assertAlmostEqual(b["ctr"], -0.005)
        self.assertAlmostEqual(b["clicks"], -0.1)

    def test_too_few_pages_give_no_baseline(self):
        b = g.baseline(self.pages(4, 90, 5.5), self.pages(4, 100, 5.0), Args())
        self.assertEqual(b["n"], 4)
        self.assertIsNone(b["position"])

    def test_pages_under_the_impression_threshold_stay_out(self):
        b = g.baseline(self.pages(12, 90, 5.5, impressions=10), self.pages(12, 100, 5.0, impressions=10), Args())
        self.assertEqual(b["n"], 0)

    def test_pages_with_a_handful_of_clicks_do_not_move_the_click_median(self):
        b = g.baseline(self.pages(12, 0, 5.0, ctr=0.05), self.pages(12, 2, 5.0, ctr=0.05), Args())
        self.assertEqual(b["n_clicks"], 0)
        self.assertIsNone(b["clicks"])
        self.assertAlmostEqual(b["position"], 0.0)


class CalibrationTest(unittest.TestCase):
    """--expected-ctr-1 comes from the site's own non-brand queries at position 1."""

    @staticmethod
    def rows(keys, ctr, position=1.2, impressions=500):
        return [{"key": k, "clicks": int(impressions * ctr), "impressions": impressions,
                 "ctr": ctr, "position": position} for k in keys]

    def test_median_ctr_of_the_top_queries(self):
        c = g.ctr_calibration(self.rows([f"boot mieten {i}" for i in range(6)], 0.12), Args())
        self.assertEqual(c["n"], 6)
        self.assertAlmostEqual(c["ctr_1"], 0.12)

    def test_brand_queries_do_not_calibrate(self):
        c = g.ctr_calibration(self.rows(["acme"] * 6, 0.4), Args())
        self.assertEqual(c["n"], 0)
        self.assertIsNone(c["ctr_1"])

    def test_under_five_queries_suggest_nothing(self):
        c = g.ctr_calibration(self.rows(["boot a", "boot b", "boot c"], 0.12), Args())
        self.assertIsNone(c["ctr_1"])

    def test_position_two_is_not_position_one(self):
        c = g.ctr_calibration(self.rows([f"boot mieten {i}" for i in range(6)], 0.12, position=2.0), Args())
        self.assertEqual(c["n"], 0)


class SingleColumnTest(unittest.TestCase):
    """The not-indexed export is one column of URLs: no delimiter for the sniffer to find."""

    def test_url_list_without_a_delimiter(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "not-indexed.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"URL\n{HOST}/a/\n{HOST}/b/\n")
            self.assertEqual(g.load_url_list(path), [f"{HOST}/a/", f"{HOST}/b/"])


class SnippetsFetchTest(unittest.TestCase):
    """A URL that is not http:// or https:// answers without a status code, and that is a fetch error."""

    def test_non_http_url_reports_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "page.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write("<html><head><title>local</title></head><body></body></html>")
            r = snippets.fetch("file://" + path)
        self.assertIsNone(r["status"])
        self.assertIn("http", r["error"])


class SnippetsRedirectTest(unittest.TestCase):
    """build_opener installs a FileHandler; a redirect must never reach it."""

    class _Resp:
        status = 301
        headers = {"Location": "file:///etc/passwd"}

        def read(self, n=None):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def test_redirect_to_a_file_url_is_refused(self):
        opener = snippets._OPENER
        snippets._OPENER = type("O", (), {"open": staticmethod(lambda req, timeout=None: self._Resp())})()
        try:
            r = snippets.fetch("https://example.com/")
        finally:
            snippets._OPENER = opener
        self.assertIsNone(r["status"])
        self.assertIn("non-HTTP", r["error"])


class TitleQueryTest(unittest.TestCase):
    """title-no-query compares content words: a natural title drops "how", "to", "the"."""

    def test_stopwords_do_not_trigger_the_flag(self):
        self.assertEqual(snippets.terms("how to clean a boat hull") - snippets.terms("Clean a boat hull in 20 minutes"), set())

    def test_missing_content_word_is_named(self):
        self.assertEqual(snippets.terms("boot antifouling") - snippets.terms("Boot reinigen in 20 Minuten"), {"antifouling"})


class NumberTest(unittest.TestCase):
    def test_to_float(self):
        self.assertAlmostEqual(g.to_float("2,5 %"), 2.5)
        self.assertAlmostEqual(g.to_float("1.234,5"), 1234.5)
        self.assertAlmostEqual(g.to_float("1,234.5"), 1234.5)
        self.assertAlmostEqual(g.to_float("0.48%"), 0.48)

    def test_to_int(self):
        self.assertEqual(g.to_int("1.234"), 1234)
        self.assertEqual(g.to_int("1,234"), 1234)
        self.assertEqual(g.to_int(""), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
