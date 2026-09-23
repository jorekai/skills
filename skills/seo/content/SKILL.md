---
name: content
description: "Write or refresh a page for one search query. Review the top five results, build an outline, and draft with evidence slots. Check title, H1, slug, meta, FAQ, internal links, and alt text. Use for writing, rewriting, refreshing, or optimizing articles, landing pages, \"best X\", \"X vs Y\", \"X alternatives\", and how-to pages."
---

# SEO content

Goal: one page that answers one query better than the current top 5 and reads as first-hand experience.

Workspace: `docs/seo/<domain>/` holds `strategy.md` (clusters, evidence inventory), `glossary.md` (the words to use), `briefs/<slug>.md` (this page's brief), `drafts/<slug>.md` (the draft until review). Without a workspace the steps still run; the brief and draft then live where the user says.

## Steps

1. **Fix the target.** One primary query plus up to 5 secondary queries with the same intent. Source: this week's `jorekai-seo:gsc-review` row, else the highest-priority cluster in `strategy.md` without a page, else the user. Refresh beats new: when a URL on the site already earns impressions for the query, that URL is the target.
   Done when primary query, page URL (existing, or the planned slug), and page type are written down at the top of `briefs/<slug>.md`.

2. **SERP recon.** Search the primary query and fetch the top 5 organic results. Record format (listicle, guide, comparison, tool page), word-count range, the sections every result shares, the sections only the best result has, People-also-ask questions, and whether titles carry a year. The winning format is the format; a guide will not outrank five comparison tables. Result summaries do not say which blocks stand above the results, so a claim about them needs a look at the result page itself; what was not looked at is recorded as not looked at, never as absent.
   Done when the brief holds a shared-sections list, a gaps list, and one dated observation line under "SERP observations" naming market, device, and the blocks seen above the organic results, or naming that gap. The section is append-only: a refresh adds a line and keeps the earlier ones.

3. **Outline.** H1 = the primary query phrased naturally. H2s = shared sections, then gaps, then one section none of the top 5 has. The first paragraph answers the query in two sentences. Template from [references/page-types.md](references/page-types.md). Headings use the glossary's terms; an `_Avoid_` word never appears in an H1 or H2.
   Done when every H2 states what the reader gets and the primary query appears in the H1 and in one H2.

4. **Draft** into `drafts/<slug>.md` with evidence slots for the author: `[SCREENSHOT: …]`, `[OWN NUMBER: …]`, `[WHAT I TRIED: …]`. Fill a slot from the evidence inventory in `strategy.md` where a row fits; the rest go to the author as one numbered round of questions (slot, what is needed, why it matters), and the answers land under "Evidence answers" in the brief before the draft is called done. Everything experiential is a slot, never a sentence written as if lived. Include a byline slot and a one-line "how this was tested" slot. Short paragraphs, concrete nouns, a table wherever the SERP shows tables. Close with a 3-question FAQ built from real GSC queries for the page or People-also-ask.
   Done when every section carries body text or a slot, and no sentence claims an experience the author has not confirmed.

5. **On-page pass** with [references/on-page-checklist.md](references/on-page-checklist.md): title ≤ 60 characters with the keyword in the first half, meta 120–160 characters with a reason to click, slug = shortened H1, alt on the first image, 2 outgoing internal links to related pages, and 2 incoming internal links from older pages named as source URL plus anchor.
   Done when every checklist line is ticked or handed to the author as open.

6. **Refresh rule** for an existing page: change the body materially (new section, updated numbers, removed stale claims), re-check every dated claim about someone else in the sections the refresh keeps, then move the visible date, `dateModified`, and `lastmod` together. Without a body change the date stays.

## Rules

- Evidence carries the page. Google's helpful-content guidance asks who made the page, how, and why, and the rater guidelines (September 2025 edition, section 4.6.6) give the Lowest rating to content that is "copied, paraphrased, embedded, auto or AI generated, or reposted" with "little to no effort, little to no originality, and little to no added value". The tool does not matter, the added value does.
- A date moved without a content change is noise: Google reads the visible and the structured date against each other, and Mueller calls the bump "noise & useless".

## Then

Run `jorekai-seo:review` on the draft; it ships only on `ship` for both axes. Then move the draft into `content_dir` (a de-slop pass on the prose belongs here too, tool in [references/tools.md](../seo/references/tools.md)), submit the URL to IndexNow with `bash <connect>/scripts/indexnow.sh <domain> URL` (needs `INDEXNOW_KEY_FILE` in `connections.md`), ask the owner for "Request indexing" in Search Console URL Inspection (the owner's click; the Indexing API is limited to `JobPosting` and `BroadcastEvent`), write a `content` row to the week's log (`scaffold.py <domain> --log` in `jorekai-seo:setup`; `verify after` 28 days), and pass the URL to `jorekai-seo:distribution`.
