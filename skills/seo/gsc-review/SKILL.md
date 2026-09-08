---
name: gsc-review
description: Turn a Google Search Console export into a ranked action list via scripts/gsc_opportunities.py (striking-distance queries at position 8–20, CTR gaps, decayed pages, cannibalization, unindexed URLs), after grading the actions logged in earlier weeks. Use when the user shares GSC CSVs or a zip, asks what to optimize next or which pages to update, or runs the weekly SEO review.
---

# GSC review

Reads `docs/seo/<domain>/config.md` for `brand_regex`, `expected_ctr_1`, `min_impressions`, `gsc_export_window`, and the log for actions due for a verdict. No workspace: run `jorekai-seo:setup`, or ask the user for those four values and skip the log steps.

## Steps

1. **Get the export.** Needed: the zip or folder from GSC > Performance > Search results > Export > Download CSV, for the window in `gsc_export_window` (`config.md`; default 28 days). The first run on a site may use 3 months to see enough queries; every run that grades a verdict uses the configured window, because a 3-month window blurs the date the change went live. For decay and for the site baseline that every verdict is measured against, a second export of the preceding period of equal length. Optional: a page×query table and a not-indexed URL list. Exact clicks in [references/export-howto.md](references/export-howto.md). Without an export, send the user those steps and stop.
   Save the files as `exports/YYYY-MM-DD-gsc.zip` (and `-prev.zip`) in the workspace, and write the week's `Source:` line as `exports/<file> (<start> to <end>, <length>)`; `jorekai-seo:and-now` reads that line.
   Done when a path to a zip or folder containing the queries and pages tables exists and the `Source:` line names the period.

2. **Run the script.**

   ```bash
   python3 scripts/gsc_opportunities.py ./gsc-now.zip --previous ./gsc-prev.zip \
     [--page-queries pq.csv] [--not-indexed ni.csv] [--min-impressions 50] \
     [--brand "acme|acme shop"] [--expected-ctr-1 0.11]
   ```

   `--brand`, `--expected-ctr-1`, and `--min-impressions` come from `config.md`. Small sites: `--min-impressions 20`. Large sites: 200 or more. The export's locale does not matter. `--brand` keeps navigational queries out of the striking-distance and CTR buckets; `--expected-ctr-1` scales the CTR curve to the site's own position-1 CTR. The report suggests that value from this export's non-brand queries at position 1: when it differs from `config.md`, write it there and say so.
   Done when the report prints the site baseline and six buckets.

3. **Grade earlier actions.** `python3 <setup>/scripts/scaffold.py <domain> --due` (path relative to the `jorekai-seo:setup` skill) lists rows whose verify-after date has passed. For each row take Then from its `Then` column, Now from the new export, and the matching median from the report's "Site baseline" section. The bucket names the metric: position for `striking` and `unindexed`, CTR for `ctr`, clicks for `decay` and `content`. The verdict, in this order:
   - `verify`, when the export window does not yet reach the verify date. Nothing else is decided. `--due` lists a row against today, so a row is listed before any export can grade it; the export window decides.
   - `too-small`, when the row's impressions stay under `min_impressions` in both exports. The change was never testable; leave the page alone and raise the threshold if these pile up.
   - `won`, when the metric moved the right way by more than the baseline for that metric.
   - `no-change` otherwise, including a page that moved the right way but less than the baseline.

   A row with no baseline (no previous export, or too few pages) is graded on the raw change, and its Baseline cell reads `none`; seasonality is then inside the verdict. Fill the week's "Outcomes of earlier actions" table with Then, Now, Baseline, and the verdict, and update the row's Status in its original file.
   Done when no due row is left unsettled.

4. **Decide one action per row** with [references/actions.md](references/actions.md). The action per bucket is fixed; the judgement is whether the query matches the page's intent. Rows where the query means something other than what the page offers get skipped, with the note "different intent". Before writing a new title or meta, read what the page serves now:

   ```bash
   python3 scripts/snippets.py URL --query "the row's query"
   ```

   It fetches with a Googlebot user agent and prints title, meta description, H1, og:title, dateModified, plus flags (`meta-is-title`, `title-no-query`, `h1-missing`, `h1-linebreak`, `title-multiple`, `og-title-differs`, `meta-long`, `meta-number-absent`). Every price or number in the meta description is checked against the page text: `meta-number-absent` means the snippet promises what the page does not say, and that row's action starts with the correction. A new title always comes with the matching og:title; a new H1 without a line break.
   Done when the top 10 rows across buckets 1–4 each carry URL, query, the current snippet fields, action, and the concrete new title, meta, H1, or section heading where the action calls for one.

5. **Deliver** one table, `URL | query | current snippet | action | expected gain`, ordered by expected gain: missed clicks for CTR gaps, impressions for striking distance, lost clicks for decay. Rows that need writing go to `jorekai-seo:content`; rows that need merging follow the merge recipe in actions.md; unindexed rows get internal links and a request for indexing. Every row the user accepts becomes an `Actions` row in this week's log (`scaffold.py <domain> --log` gives the path and the next id), Status `todo`; a row applied in this session gets `applied`, today's date, and `verify after` 14 days out for `ctr`, 28 days for the rest. `Then` holds the bucket's metric and the impressions from this export, so the later verdict has a starting point.
   Site in the repository: apply title, meta, and H1 rows in `head_template` and the page source. Site in a hosted CMS (`framework` in `config.md`, `head_template` blank): the accepted rows go as one prompt to the session on the server, format and rules in the `seo` skill's [references/session-contract.md](../seo/references/session-contract.md); its report fills the Outcome column, and every item under "Open, owner decision" gets its own `tech` row with Status `todo`.
   After a change is applied, read the page back: `python3 scripts/snippets.py URL` prints what a bot gets now. A title, meta, or H1 that is still the old one means a cache or a build swallowed the change, and the row is not `applied`. After the changes are live: `bash <connect>/scripts/indexnow.sh <domain> URL [URL ...]` submits them to IndexNow. Google indexing stays the owner's click, "Request indexing" in URL Inspection per URL: ask for it and note the date in the log row.
   Done when the log holds one row per accepted action with its `Then` value, `snippets.py` shows every applied change live, and the IndexNow status code is in the log.

## Interpretation

- IndexNow reaches Bing and the other participants; Google is not one. On the Google side only the owner's "Request indexing" click counts, with a daily limit Google does not number, and the Indexing API is limited to `JobPosting` and `BroadcastEvent` pages.
- Position is an average over queries, devices, and countries. A page at 9.4 may sit at 3 for one query and 30 for another; read the query-level rows before rewriting anything.
- High impressions with CTR near zero at position 5 or better usually means an AI Overview, featured snippet, or sitelink takes the click. In GSC every link inside one AI Overview shares a single position and a click from it counts as a normal click, so the row looks like a good position with a bad snippet. Rewrite the title and meta for a reason to click (number, year, outcome), then accept the ceiling. A page that wins the featured snippet is not repeated in the ten blue links (Google, January 2020), so its position can improve while clicks stay flat.
- Decay with a stable position is demand shift or a new SERP feature; decay with a worse position is content or competition. Only the second is fixed by updating the page. Confirm with GSC Compare, last 3 months year over year, weekly granularity: if the drop repeats last year's curve it is seasonal.
- Cannibalization needs page×query data; the UI export has none. Without `--page-queries`, filter one query in GSC and read its Pages tab. Google consolidates duplicates into one canonical rather than penalizing them, and Mueller (September 2025) calls several pages in one result "not problematic just because it's more than 1"; merge only pages that duplicate each other, differentiate the rest.
- The expected-CTR curve in the script is a heuristic. Study results for calibration: Sistrix, Germany, 100M keywords (2026): position 1 about 27 % overall, 11 % with an AI Overview; Ahrefs, 300,000 keywords, desktop (December 2025): 7.3 % without and 1.6 % with an AI Overview. Set `--expected-ctr-1` from the site's own data before trusting the CTR-gap bucket.
- The Generative AI performance report (all properties since August 31, 2026) shows impressions in AI Overviews and AI Mode by page, without clicks or queries. Use it to see which pages get cited; ranking in the top 10 no longer predicts citation (Ahrefs, 863,000 keywords, March 2026: 38 % of cited pages in the top 10).
- The site baseline is the median change of all pages in both exports. Seasonality, a core update, and site-wide drift move every page at once, so a page that gained less than the median lost ground. Pages changed in the period are a small share of all pages, and the median ignores them; on a site with a few dozen pages that stops being true, and the baseline carries part of the change it is measuring.
- Fewer than 50 impressions per query is noise on a 28-day window. Widen the range instead of lowering the threshold below 20. A row that stays under the threshold in both exports gets `too-small` rather than a verdict: forcing `won` or `no-change` onto that data teaches the log noise.
