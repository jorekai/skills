# Action per bucket

## 1–2. Striking distance (position 8–20)

The page already ranks; Google wants one more signal.

1. Put the exact query in the title (first 60 characters) if it reads naturally, and in the H1 or one H2.
2. Open the current top 3 for the query. Add the one section they all have and this page lacks.
3. Answer the query in the first paragraph, two sentences.
4. Add 2 internal links to the page from older pages, query as anchor.
5. Update `lastmod`, Request indexing.

Skip when the query's intent differs from the page (informational query on a product page). That case wants a new page, via `jorekai-seo:content`.

## 3–4. CTR gap

Rankings are fine; the snippet loses the click.

1. Rewrite the title: keyword first, then the differentiator (number, year, outcome, "free", "template"). ≤ 60 characters.
2. Rewrite the meta description: 120–160 characters, keyword once, one concrete promise.
3. Check the SERP for what steals clicks: AI Overview, featured snippet, video carousel, a competitor's rich result. Match the format that wins the snippet (a definition paragraph, a numbered list, a table) at the top of the page. Google builds the shown title from the `<title>`, headings, `og:title`, and inbound anchor text, so align the H1 with the new title.
4. If an AI Overview shows: aim to be cited in it. Seer Interactive (3,119 terms, 42 organisations, September 2025) measured 35 % higher organic CTR for brands cited in the AI Overview than for uncited brands on the same SERP. Eligibility is only "indexed and snippet-eligible"; a direct answer in the first paragraph is the on-page lever.
5. Re-check CTR after 14 days.

## 5. Decayed pages

Update before writing anything new.

1. In GSC, Compare last 3 months year over year for the page: impressions down with position stable is demand (seasonal or an AI Overview since March 2025 in Germany); position down is the page. Then compare the page against the current top 3: what changed in format, what is newer, what is missing.
2. Replace stale numbers, screenshots, and claims. Add one new section. Remove what is no longer true.
3. Move the visible date and `lastmod` only after step 2 changed the body.
4. Re-add internal links if the old page lost them in a redesign.
5. Request indexing.

## 6. Cannibalization

Two of your URLs show for one query. Google does not penalize this; it consolidates duplicates into one canonical and otherwise shows whichever pages fit. Act only when the pages duplicate each other or the wrong one ranks.

1. Keep the URL with more clicks; on a tie, the better position, then the more links.
2. Move the unique content of the weaker page into the keeper.
3. 301 the weaker URL to the keeper; update internal links and the sitemap; remove it from the sitemap.
4. If both pages must exist (different intents), differentiate the titles and H1s so each targets its own query, and cross-link them.

## 7. Not indexed

1. Add ≥ 2 internal links from indexed pages.
2. Make sure the page has substance and a self-referencing canonical (run `jorekai-seo:tech-audit` on it). URL Inspection "URL is unknown to Google" means no link or sitemap has reached it yet.
3. Request indexing once. On Bing, IndexNow pushes the URL the same minute (no indexing guarantee, per its FAQ).
4. Still out after 4 weeks (heuristic window): merge into a stronger page and 301, or remove with 410. Google says small sites with good content often clear "Discovered" on their own; "Crawled – currently not indexed" that persists is a quality verdict and rarely flips without a real change.
