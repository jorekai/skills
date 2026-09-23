# Tool stack

## Free and mandatory

- **Google Search Console**: indexing status, queries, positions, Core Web Vitals report, URL Inspection and Request indexing, and since 2026 the Generative AI performance report (impressions in AI Overviews and AI Mode). Source of truth for `jorekai-seo:gsc-review`. Bulk data export to BigQuery when the 1,000-row UI cap bites.
- **Bing Webmaster Tools**: import from GSC; IndexNow submissions; the AI Performance report (citations in Copilot and Bing's AI answers, public preview since February 2026). Bing's index feeds ChatGPT search and Copilot, so this is also the AI-visibility console.
- **PageSpeed Insights**: LCP, INP, CLS. Green in GSC's Core Web Vitals report is enough; a 100 score is not a goal.
- **Google Trends**: trend spotting for `jorekai-seo:distribution`.

## Free and optional

- **`unslop`**: a de-slop rewrite pass over a draft's prose (removes AI writing patterns) after `jorekai-seo:review` ships it and before it moves into `content_dir`. Run it when the skill is available in the environment; the loop does not depend on it.

## Paid, optional, interchangeable

- **Backlink index** (Ahrefs, Semrush, Moz; smallest plan): competitor links, unlinked mentions, referring domains after outreach.
- **GSC dashboard** (e.g. seogets): daily view of decay and growth, orphan pages. Replaces the manual weekly export.
- **Indexing automation** (e.g. indexrusher): bulk Request indexing across Google and Bing. Same effect as pressing the GSC button page by page; worth it above roughly 100 URLs. Google's Indexing API is documented for job-posting and livestream pages only; pushing other pages through it is outside its documented scope.
- **Directory submission** (e.g. listingbott): bulk listings. Policy boundary: Google names "low-quality directory or bookmark site links" as link spam and Illyes (2016) warned directories can bring manual actions. Use only for listings customers actually use (industry bodies, local chambers, app marketplaces); referral and AI-training exposure, not ranking, is the return.
- **AI article drafting** (e.g. seobotai): volume drafts to discover which topics earn impressions. Winners get rewritten by a human through `jorekai-seo:content`. Policy boundary: Google's scaled-content-abuse policy names "using generative AI tools to generate many pages without adding value for users" as spam. Publishing many raw drafts to test traction sits inside that description; the risk is a site-wide manual action, not a per-page loss. Publish drafts only after a human adds evidence, or keep them `noindex` until then.

## Not a tool

- **llms.txt**: no search engine or assistant documents reading it; Google's Mueller (January and June 2026) says none is known to. Create one only if a platform that sends traffic asks for it.

## What the agent does instead of a tool

- Technical checks: `tech-audit/scripts/audit.py`.
- Opportunity mining: `gsc-review/scripts/gsc_opportunities.py`.
- SERP recon: WebSearch the query, fetch the top results.
