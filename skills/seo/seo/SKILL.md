---
name: seo
description: Entry point for the SEO skill set: which sub-skill to reach for, the three flows (new site, weekly loop, drop), the priority ladder, launch checklist, domain naming, tool stack.
disable-model-invocation: true
---

# SEO

One loop drives everything: **get indexed, find what almost ranks, fix that page, earn links, repeat**. New content comes last.

## Workspace

Every skill reads and writes `docs/seo/<domain>/` in the site's repository: `config.md` (site facts), `connections.md` (what is connected), `strategy.md` and `glossary.md` (from the interview), `log/` (every action and its outcome, one file per week), `briefs/` (page briefs and their review), `drafts/`, `exports/`, `audits/`, `reports/`. Layout and log format: `docs/seo/README.md`, written by `jorekai-seo:setup`. No workspace yet: `jorekai-seo:setup` first.

## Flows

**New site or domain**, in this order:

1. `jorekai-seo:setup`: workspace, `config.md`, pointer block in `AGENTS.md` and `CLAUDE.md`.
2. `jorekai-seo:connect`: wizard for Search Console, sitemap, Bing, IndexNow.
3. `jorekai-seo:grill`: interview, writes `strategy.md` (clusters, competitors, evidence) and `glossary.md`.
4. `jorekai-seo:tech-audit --crawl` until zero FAIL, then [references/launch-checklist.md](references/launch-checklist.md).

**Weekly loop** (15 minutes): export GSC; `jorekai-seo:gsc-review` (site baseline from both exports, then the verdicts on last weeks' rows, then the new buckets); top row via `jorekai-seo:content`; `jorekai-seo:review` before it ships; 2 internal links from older pages; request indexing (IndexNow by the agent via `connect/scripts/indexnow.sh`; Google "Request indexing" by the owner in URL Inspection, the Indexing API covers only `JobPosting` and `BroadcastEvent`); `jorekai-seo:distribution`. Every step leaves a log row.

**Monthly**, for the site's owner: `jorekai-seo:report` writes `reports/YYYY-MM.md` from the month's exports and log weeks: totals against the median page, every action with its verdict, visibility in AI answers, and the three things next month does.

**Site not in a repository** (hosted CMS): fixes and snippet rows go to a session on the server, prompt and report format in [references/session-contract.md](references/session-contract.md), stack recipes in [references/stacks/](references/stacks/).

**Moving a domain, a host, or the URLs**: `jorekai-seo:migrate`. Inventory, redirect map, the owner's console steps, then `--redirects` until zero FAIL.

**Something dropped**: `jorekai-seo:diagnose`. Six hypotheses, one change, verify date in the log.

**Lost the thread**: `jorekai-seo:and-now` reads the workspace and names the stage, the open items, and the next skill.

## Sub-skills

| Need | Skill | Invoked by |
|---|---|---|
| Where am I in the loop, what comes next? | `jorekai-seo:and-now` | you |
| What did the month change and earn, for the owner? | `jorekai-seo:report` | you |
| Set up the workspace for a repo or a new domain | `jorekai-seo:setup` | you |
| Connect Search Console, sitemap, Bing, IndexNow; submit changed URLs to IndexNow (`scripts/indexnow.sh`) | `jorekai-seo:connect` | you |
| Pin niche, audience, competitors, keywords, evidence, vocabulary | `jorekai-seo:grill` | you |
| Is the site technically sound and indexable? | `jorekai-seo:tech-audit` | agent or you |
| What should I work on this week? | `jorekai-seo:gsc-review` | agent or you |
| Write or refresh a page | `jorekai-seo:content` | agent or you |
| Is this draft right for the query and clean on the page? | `jorekai-seo:review` | agent or you |
| Why did clicks, impressions, or position drop? | `jorekai-seo:diagnose` | agent or you |
| Moving a domain, a host, or the URL structure | `jorekai-seo:migrate` | agent or you |
| Get links | `jorekai-seo:links` | agent or you |
| Promote a page | `jorekai-seo:distribution` | agent or you |

## Priority ladder

Each rung depends on the one before it.

1. **Indexable**: audit shows zero FAIL, sitemap submitted, pages report as indexed. Nothing else counts until this holds.
2. **Almost ranking**: positions 8–20 and CTR gaps from GSC. Closer to page 1 than any new article.
3. **Decayed**: pages that used to get clicks. Real updates, never date bumps.
4. **Links**: to the pages from rungs 2 and 3. Internal links first.
5. **New content**: one good post a week, on clusters from `strategy.md` where the site already has impressions.

## Writing the answer

What a skill hands back has a shape, so two runs are comparable and a table can go into the log without being rewritten:

1. One line first: what was read and where it sits. A file the workspace already holds is named, never repeated.
2. One table, ordered by what it costs or earns, one row per thing to decide. What the table drops is one sentence under it, never a second table.
3. Every number names its source: an export window, a check id, or a log id.
4. One line last: the single next action and who does it.

The columns, per skill:

- `jorekai-seo:tech-audit`: `check id | URLs | fix | how to verify`, ordered Critical, High, Hygiene
- `jorekai-seo:gsc-review`: `URL | query | current snippet | action | expected gain`, ordered by expected gain
- `jorekai-seo:diagnose`: `hypothesis | prediction | check | evidence | verdict`, six rows in rank order
- `jorekai-seo:distribution`: `piece | platform | first line | where the link sits`, the texts under the table
- `jorekai-seo:review`: no table. `## Intent` and `## Standards`, one line per axis: finding count, worst finding, verdict.
- `jorekai-seo:content`: no table. `briefs/<slug>.md`, `drafts/<slug>.md`, and one numbered round of questions to the author.
- `jorekai-seo:links`: no table. `outreach.csv` itself, and the internal links as source URL, anchor, paragraph.
- `jorekai-seo:grill`: no table of its own. `strategy.md` and `glossary.md`, then that file's keyword table sorted by priority and the open questions.
- `jorekai-seo:migrate`: no table. The inventory, `redirect-map.csv`, and the two audit files, each with its FAIL count.
- `jorekai-seo:report`: no table. `reports/YYYY-MM.md`, one page, not repeated in the answer.
- `jorekai-seo:and-now`: no table. The script's `stage`, at most three `now`, one `then`.
- `jorekai-seo:setup`, `jorekai-seo:connect`: no table. The files they wrote and what is still open.

Reason: `decisions/0023`.

## Principles that survive algorithm updates

- One page, one query intent. Two pages for one intent cannibalize each other.
- Title, H1, slug, and first paragraph agree on the keyword, in the glossary's words.
- Original evidence on every page: screenshots, own numbers, what was actually tried. The evidence inventory in `strategy.md` says what exists.
- The visible date changes only when the content changed.
- Link out, and accept links, only where a reader expects the link.
- Pages exist for a reader. Many pages generated at scale without added value fall under Google's scaled-content-abuse policy and put the whole site at risk.
- Bots get full HTML. Client-only rendering is invisible until Google gets around to rendering it.
- One change per page per verify window; the log is how you learn what worked.

## Reference

- New site or domain: [references/launch-checklist.md](references/launch-checklist.md), [references/domain-naming.md](references/domain-naming.md)
- Five-minute fixes when there is no time for the loop: [references/five-minute-fixes.md](references/five-minute-fixes.md)
- Tools and what each is for: [references/tools.md](references/tools.md)
- Fixing a site that lives in a CMS on a server: [references/session-contract.md](references/session-contract.md) (protocol) and [references/stacks/wordpress.md](references/stacks/wordpress.md) (recipes)
- Documented facts with source and check date, and the list of heuristics: [references/sources.md](references/sources.md)
