---
name: links
description: "Find link opportunities for a target page and draft outreach. Start with internal links, then unlinked brand mentions and pages cited by Google or AI search for the keyword. Also consider roundups, directories, and guest posts. Use for backlinks, link building, outreach, internal linking, or getting cited by AI search."
---

# Links

Order: internal links, then mentions that already exist, then pages already ranking or cited, then new placements. Cheapest and safest first.

With a workspace, the target list is `docs/seo/<domain>/outreach.csv`, the anchors use `glossary.md` terms, and every placement gets a `links` row in the week's log.

## Steps

1. **Internal links, before any outreach.** Find 2–5 existing pages on the site that discuss the target topic (grep the content directory; site not in this repository: the crawl from `jorekai-seo:tech-audit` or the page rows of the newest export). Add one contextual link each with a descriptive anchor: the target query or a natural variant. Highest-traffic relevant page first.
   Done when the target has ≥ 2 new inbound internal links, each listed as source URL, anchor, and paragraph.

2. **Target list.** `outreach.csv` with `url, site, contact, why, status` from:
   - Unlinked mentions: WebSearch `"brand name" -site:yourdomain` and the product name; pages that name you without linking.
   - Ranking pages: WebSearch the target query; the top 10, plus `best [category]`, `[category] tools`, `[competitor] alternatives`.
   - AI-cited pages: the user asks ChatGPT, Claude, Perplexity, and Gemini "best tool for [query]" and "alternatives to [competitor]" and pastes the cited URLs. Those pages are what the models read; a placement there is AI-search visibility. Collect this list and the ranking list separately, because they overlap only in part.
   - Directories and roundups in the niche.
   Fetching and judging the candidates is subagent work: each subagent returns the `outreach.csv` columns for its share of the targets, under 200 words, and the pages it read stay in its context.
   Done when the list has ≥ 20 rows and every row has a `why` (mention, ranks #n, cited by X, roundup).

3. **Qualify** with [references/link-quality.md](references/link-quality.md): real traffic, topical match, a natural spot for the link. Rows that fail are dropped, with the reason kept in `status`.

4. **Outreach.** One email per target from [references/outreach-templates.md](references/outreach-templates.md), personalized with the exact page and the exact sentence where the link fits. Offer in this order: value (a better resource, a missing section, data), a reciprocal link from a relevant page of yours, then payment. AI-cited pages get contacted the same day they are found; those lists move fast.
   Done when every qualified row has a draft and a follow-up date 7 days out.

5. **Track.** `status` moves through `sent`, `replied`, `placed`, `declined`. Placement is verified by fetching the page and confirming the link and its `rel`, then logged as a `links` row (`scaffold.py <domain> --log` in `jorekai-seo:setup`, `verify after` 28 days).

## Rules

- AI citation runs on the indexes you already rank in. ChatGPT search and Copilot retrieve through Bing, Perplexity through `PerplexityBot`, Claude through `Claude-SearchBot` and `Claude-User`, AI Overviews and AI Mode through Googlebot, and Gemini's grounding is gated by `Google-Extended`. Ranking in Bing and Google for the query is the underlying lever, and `robots.txt` must let those tokens through. Since March 2026 (Ahrefs, 863,000 keywords) only 38 % of pages cited in AI Overviews sit in the organic top 10, so the cited list differs from the ranking list.
- Paid or exchanged placements carry `rel="sponsored"` (or `nofollow`) on the linking side; ask for it in the email. An undisclosed paid link violates Google's spam policies and risks a manual action on both sites. A sponsored link still brings referral traffic and puts the brand in what AI models read; Google has treated `nofollow`, `ugc`, and `sponsored` as hints since 2019 and says a nofollowed link is not dampened but simply carries no value. Press releases count as advertising: links in them get `nofollow`.
- Unlinked mentions are a source of link targets, not a ranking signal: Mueller (2020, 2022) says mentions "usually" do not help and there is no factor that tracks them. Ask for the link; do not count the mention.
- Directories: Google's policy names "low-quality directory or bookmark site links" as link spam, and Illyes (2016) warns that directories are "very often not the right way to build links". Only listings a customer would use (industry bodies, local chambers, the Google Business Profile). Skip bulk submission.
- Disavow only for links you built and that caused or will cause a manual action; Google says most sites never need the tool. Remove first, disavow the rest.
- A reciprocal link now and then between related pages is normal; systematic exchanges ("link to me and I link to you") and partner pages built for cross-linking count as link spam under the same policy.
- Cross-linking your own sites is fine between topically related pages and harmful as a sitewide footer web.
- Guest posts go only on sites that already rank for your keywords, and the post has to be worth reading with the link removed. Google's spam policy names "links with optimized anchor text in articles, guest posts, or press releases distributed on other sites" as link spam, and its site reputation abuse policy (effective May 5, 2024, no first-party exemption since November 19, 2024) hits hosts that publish third-party pages to borrow their ranking; a guest post section on a strong host is exactly that pattern. Vary anchors, one link, editorial placement.
