---
name: grill
description: "Interview the owner about the site's niche, audience, offer, competitors, keywords, evidence, and vocabulary. Write strategy.md and glossary.md in the SEO workspace."
disable-model-invocation: true
argument-hint: "[domain]"
---

# SEO grill

Interview the user until `docs/seo/<domain>/strategy.md` and `glossary.md` hold everything `jorekai-seo:content` needs to write a page without asking. Needs the workspace from `jorekai-seo:setup`; missing: run that first.

## Rules

- **Design tree.** The questions hang off each other; [references/question-bank.md](references/question-bank.md) is the tree. The **frontier** is every question whose prerequisites are settled. Ask the whole frontier in one round, numbered, each with your recommended answer. Wait. Recompute the frontier from the answers. A question that depends on an answer still open in this round belongs to the next round.
- **Facts are the agent's job, decisions are the user's.** Before asking about competitors, search the seed queries and list who ranks. Before asking about keywords, expand the seeds from the SERP, People-also-ask, and a Search Console export if `exports/` has one. Ask the user only what the environment cannot tell you: what they sell, whom they serve, what evidence they hold, what they refuse to publish. A running lookup blocks only the questions downstream of it; ask the rest.
- **Write as decisions land**, not at the end: each settled branch goes into its `strategy.md` section or a glossary entry in the same turn. A session cut short still leaves a usable file.
- **Vocabulary is checked in every round.** A word the user uses that the audience would not search for, or two words for one thing, becomes a glossary entry with the audience's term first and the rest under `_Avoid_`.

Question format, one per question:

```
Q3. <title>: <question, with the options where there are options>
Recommended: <answer and the one-line reason>
```

## Steps

1. **Load.** Read `config.md`, existing `strategy.md` and `glossary.md` (a re-run starts from what is there, and asks only what is blank or stale), the site's own description of itself (home page, about page, top titles from `content_dir`), and the latest export in `exports/` when present.
   Done when the frontier for round 1 is the tree's roots minus what these files already answer.

2. **Rounds** until the frontier is empty. Every branch of the tree visited; nothing silently assumed.
   Done when every `strategy.md` section has content or an explicit "none" with the reason, the keyword table has a primary query and a priority per cluster, the evidence inventory has at least three rows or says "none yet", and the glossary has the terms every cluster title uses.

3. **Check the URLs.** Every money page and cluster URL written into `strategy.md` is fetched once: `curl -sIL -A Mozilla URL | grep -E '^(HTTP|location)'`. A URL that redirects or 404s is replaced by the final URL or marked "planned" in the table; a page the site describes as a money page but redirects to a product URL means the product URL is the money page.
   Done when every URL in `strategy.md` returns 200 on its own address or carries "planned".

4. **Close.** Show the user the keyword table sorted by priority and the open-questions list, and name the first cluster to hand to `jorekai-seo:content`. No log row: the site did not change.
