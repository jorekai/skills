---
name: tech-audit
description: Audit a URL or whole site for technical SEO and indexability: runs scripts/audit.py (bot rendering, title/meta/H1/canonical, noindex conflicts, robots.txt, sitemap lastmod, redirects and their type, hreflang, dates, structured data, images, host variants, soft 404, pagination, duplicates, orphans) and prescribes fixes. Use when asked to check a site for SEO, why a page is not indexed, before a launch, or for canonical, redirect, sitemap, or robots questions.
---

# Tech SEO audit

With a workspace, `docs/seo/<domain>/config.md` names the files to fix (`head_template`, `sitemap`, `robots_txt`, `static_dir`), the `framework`, and the canonical host; step 2 goes straight there. Before the crawl, ask for the Search Console screenshots in step 3 so they arrive while it runs.

## Steps

1. **Run the audit once, large.** One page plus site-level checks; `--crawl N` adds duplicate titles, broken links, tracking parameters, and orphans. A crawl costs about one second per page, and the orphan check only runs when the queue drains, so set N above the sitemap URL count (`site.sitemap` prints it) and run in the background:

   ```bash
   python3 scripts/audit.py https://example.com/ --crawl 400 --json > docs/seo/<domain>/audits/YYYY-MM-DD-tech.json
   ```

   The script path is relative to this skill's directory. Every item in the JSON carries its own full list under its `data` field; the text report shows examples only. Without a workspace, write the JSON to a scratch file. Cart, checkout, and account URLs are counted, not crawled; a URL that robots.txt disallows is reported, not fetched.
   Done when the JSON has no `http.fetch` item and `crawl.size` says "site exhausted". A fetch failure means DNS, TLS, or timeout: report that first, nothing else is measurable. Limit hit: raise N once, do not rerun in small steps.

2. **Map every FAIL and WARN to a fix** with [references/fixes.md](references/fixes.md), keyed by check id. Inside the site's repository, apply the fix in the layout or template that emits the `<head>` instead of describing it: `head_template` from `config.md`, or grep for `<title`, `rel="canonical"`, `sitemap`, `robots`. Site not in the repository (`framework` is a hosted CMS, `head_template` blank): hand the findings to a session on the server with the prompt described in the `seo` skill's [references/session-contract.md](../seo/references/session-contract.md) (`ssh_host` and `cli` from `config.md`), or, without server access, write each fix as a CMS admin step with the replacement value from the CMS section of fixes.md. In both cases the returned table becomes the log rows and you verify with a rerun.
   Done when every FAIL has a code change, an admin step with the exact new value, or a named owner, and every WARN has a decision: fixed, or accepted with the reason.

3. **Cover what the script cannot see.** GSC-only signals: Pages report reasons, Core Web Vitals, URL Inspection verdicts, manual actions. Walk [references/gsc-checks.md](references/gsc-checks.md) with the user, or ask for the screenshots and exports it names.
   Done when each item there is green or listed as open with its reason.

4. **Deliver** one table ordered Critical, High, Hygiene, and save the text report next to the JSON as `audits/YYYY-MM-DD-tech.md` (with a workspace) so log rows can point at it instead of repeating URLs. Critical blocks indexing: fetch, noindex, robots (including noindex hidden behind a robots block), canonical pointing elsewhere, client-only rendering, soft 404, duplicate hosts. High costs ranking or signals: title, H1, thin text, redirect chains and temporary redirects, hreflang errors, pagination canonicals, images without src, orphans, duplicates. Hygiene is every INFO. Each row: `check id | URLs | fix | how to verify` (re-run the script, or GSC URL Inspection > Test live URL). Every fix gets a `tech` row in the week's log (`scaffold.py <domain> --log` in `jorekai-seo:setup`): status `todo` with the check id and a pointer to the audit file when someone else applies it, `applied` with the date when you did, `verify after` 14 days out. One row per check id, not per URL.

## Reading the report

- `render.bot-html` FAIL is the most expensive finding: the index sees a shell. Four signals, each enough on its own, and the message names the ones that fired: under 300 characters of visible text; under 300 characters outside `header`, `nav`, `footer`, and `aside`; no internal `<a href>`, because only `<a href>` is crawlable; an empty framework mount point (`id` of `root`, `app`, `__next`, `__nuxt`, or `svelte`). The second signal exists because a menu and a footer clear any character threshold and are identical on every page. It counts only those four elements, so chrome built from plain `div`s is caught by one of the other three or not at all. Server-render or pre-render; confirm with `curl -sA Googlebot URL | grep '<h1'`.
- `render.consent-wall` fires only on a page that is already thin, and names the consent platform found in the HTML. A banner covering the page for a reader is not the problem; content that reaches the HTML only after consent is. Fetch the URL raw and read what stands in it before treating the thinness as a rendering bug.
- `render.js-only` needs a rendered DOM to compare against, and only for the audited URL itself. Save one when a browser tool or Search Console's live test is at hand, then pass `--rendered FILE`; install or start nothing to obtain it. The rendered DOM is the fast check, Search Console's live test is the verdict, and a raw-only audit stays a complete result.
- `head.canonical` pointing elsewhere is correct for paginated, filtered, or syndicated pages and wrong for anything meant to rank. Ask before changing it.
- `head.noindex` is a FAIL on a page meant to rank and correct on thank-you, admin, and internal search pages.
- Crawl findings cover the crawled set only. "Orphan check skipped" means raise `--crawl` until the queue drains, or accept the gap.
- `crawl.robots-disallowed` lists linked URLs the crawl did not fetch because `robots.txt` disallows them; the audit stops where Googlebot stops. A long list means internal links point into an area that can never rank.
- The script reads HTML only. Speed is judged by GSC's Core Web Vitals report, not by the TTFB warning here.
- `head.hreflang` checks self-reference, x-default, and code format on this page only; return links on the alternates are not fetched.
- `--redirects FILE` fetches every row of a move's redirect map once and answers one question per row: one permanent hop, a live target, the target the map names. It belongs to `jorekai-seo:migrate`, which is where the map comes from.
- `head.json-ld` lists the types on the page. `head.schema-invalid` means a block did not parse, so Google reads none of it. The other two are about what the markup earns, not about syntax: `head.schema-no-rich-result` names markup Google shows nothing for any more, and `head.schema-review` names a rating on a node outside the types stars are shown for, which is where a site rates itself. Field-level validation stays with Google's Rich Results Test; the script reports what is there.
- `site.sitemap-lastmod` fires when 90 % or more of URLs share one date: a generator stamping the build time. Google discards lastmod it cannot trust, so that sitemap loses its freshness signal.
- `crawl.tracking-params`: internal links with `utm_*` on the site's own URLs. Each variant is a crawlable duplicate of the clean URL; it also shows up under `crawl.not-in-sitemap`. Fix the links, not the sitemap.
- `crawl.orphans` on a shop or CMS often lists pages that exist only in the sitemap (old campaigns, location pages without a hub). Decide per URL: link it from a related page, or drop it from the sitemap and `noindex` it.
- `crawl.cart-links` and `crawl.non-indexable` are counts, not findings. High numbers on a shop are normal.
