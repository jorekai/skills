---
name: diagnose
description: Diagnose a drop in clicks, impressions, or position for a page, a query, or the whole site: make the drop visible in Search Console data first, then test six fixed hypotheses in order (seasonality, SERP feature, Google update, technical regression, own-site change, competition), change one thing, and log a verify date. Use when traffic fell, rankings dropped, a page lost its snippet, or the user asks why numbers went down.
---

# SEO diagnose

Six hypotheses, one change. The loop: **make it red, rank, test one at a time, one fix, verify date**. Reading the site to build a theory before the drop is visible in data is the failure this skill prevents.

Reads `docs/seo/<domain>/config.md` and the log when the workspace exists; works without it.

## Steps

1. **Scope.** What dropped (clicks, impressions, position, CTR), where (site, page, query), since when, compared to what. The user's dashboard is not the evidence; Search Console is.
   Done when the claim reads like "clicks for /pricing fell from about 40 to about 12 a week since mid-August".

2. **Make it red.** Reproduce the drop in Search Console data: Performance > Compare, the two ranges that bracket the change, filtered to the page or query; export both and save them to `exports/` as `YYYY-MM-DD-drop-<what>.csv`. Then write the red line: metric, before, after, the week it turned. Also record the shape: sitewide or one page; position moved or only CTR; impressions moved or only clicks. Sitewide or one page is a number, not an impression: run `jorekai-seo:gsc-review`'s opportunity script over the two exports and read its site baseline, the median change of every page. The shape ranks the hypotheses.
   Done when the red line exists with numbers from the export. If the export does not show the drop, stop and say so: the dashboard and Search Console disagree, and that is the finding.

3. **Rank the six hypotheses** from [references/hypotheses.md](references/hypotheses.md) by fit to the shape, and state each one's prediction ("if this is the cause, then X in the data"). Show the ranking to the user before testing; they often know what changed (a deploy, a redesign, a migration). One table, `hypothesis | prediction | check | evidence | verdict`, six rows in rank order; the last two columns stay empty until step 4 fills them.
   Done when six rows exist, each with a prediction and the check that would confirm it.

4. **Test in rank order, one at a time**, using the checks in hypotheses.md. Stop at the first confirmed cause. A check that needs the audit script or URL Inspection runs now, not later. Fill `evidence` and `verdict` in the same table; a hypothesis the run never reached reads `not tested`, never `ruled out`. Six unconfirmed: report that, with the evidence per hypothesis, and ask for what is missing (access, dates of changes, older exports).
   Done when one hypothesis is confirmed by its predicted evidence, or all six are ruled out with the evidence stated.

5. **One change, one row.** Apply the fix the confirmed hypothesis names (in hypotheses.md), write a `diagnose` row to the week's log with `verify after` 28 days out (`scaffold.py <domain> --log` in `jorekai-seo:setup` gives path and id), and stop. A second change before the verify date makes the outcome unreadable.

## Rules

- Seasonality and SERP features are not fixed by editing the page; say so and close them as `no-change` expected.
- One variable per change, including "just also" title tweaks.
- Google's own list of causes (technical issues, security, spam violations, algorithmic updates, seasonality and changing interests, site migrations) is the boundary of this skill: the six hypotheses cover it; a cause outside it is an escalation, not a seventh hypothesis.
