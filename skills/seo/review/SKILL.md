---
name: review
description: "Review a draft or live page before publication. Check intent against the top five results, then check on-page standards, glossary terms, and evidence for every experiential claim. Give separate verdicts for intent and standards. Use for SEO reviews, QA, page or draft checks, or before moving a draft into the content directory."
---

# SEO review

Two axes, reported apart, never merged:

- **Intent**: is this the right page for the query, and is it better than what ranks?
- **Standards**: is the page correct on the page, and is every claim backed?

A draft can pass one and fail the other; merging the reports lets one axis hide the other.

## Steps

1. **Pin the inputs.** The draft (a path under `drafts/`, a file in `content_dir`, or a URL), the brief in `briefs/<slug>.md` when one exists, `strategy.md` (evidence inventory) and `glossary.md` from `docs/seo/<domain>/`. No brief: the primary query comes from the user, and the Intent reviewer does its own SERP recon.
   Done when the primary query and the draft text are in hand.

2. **Run both reviews as parallel subagents**, each with only its own inputs. In a harness without subagents, run them one after the other, Intent first, and keep the reports separate.

   **Intent reviewer** gets: the draft, the primary query, the brief's SERP recon (or the instruction to fetch the top 5 now). Brief: "Report (a) shared sections of the top 5 the draft lacks; (b) whether the first paragraph answers the query in two sentences; (c) format mismatch (the SERP is tables or listicles and the draft is prose, or the reverse); (d) sections that serve no reader of this query (scope creep); (e) the one thing the best-ranking page does that the draft does not. Quote the draft line for each finding. Under 400 words."

   **Standards reviewer** gets: the draft, [the on-page checklist](../content/references/on-page-checklist.md), `glossary.md`, the brief's evidence answers and `strategy.md`'s evidence inventory. Brief: "Report (a) every unticked checklist line, quoting the element; (b) every term that has a glossary entry but appears as an `_Avoid_` word; (c) the fabrication check: list every sentence that states first-hand experience, a number, a date, a named study, or a quote, and for each name the evidence answer, inventory row, or linked source it traces to; a sentence with no trace is a blocker, an unfilled `[SLOT]` is open, not a blocker. Under 400 words."
   Done when both reports exist.

3. **Aggregate** under `## Intent` and `## Standards`, each report verbatim or lightly cleaned, then one line per axis: finding count, worst finding, verdict `ship` or `fix first`. A fabrication blocker makes Standards `fix first` regardless of anything else. No single winner across axes. With a workspace the file is `briefs/<slug>.review.md`.

## Then

`fix first`: hand the findings to `jorekai-seo:content` (Intent) or apply them directly (Standards), then review again. `ship` on both: the draft moves into `content_dir`, and `jorekai-seo:content`'s after-publishing steps run.
