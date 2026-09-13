---
name: report
description: "Write the owner's monthly SEO report from the workspace. Include export totals, the median page, action results, visibility in AI answers, and three next steps."
disable-model-invocation: true
argument-hint: "[domain] [YYYY-MM]"
---

# Monthly report

Writes `docs/seo/<domain>/reports/YYYY-MM.md` for the person who pays for the site. `jorekai-seo:and-now` answers "what next" for whoever runs the loop; this answers "what happened, and what did it earn". Every number comes from files that already exist: the month's exports, the month's log weeks, `strategy.md`.

Needs the workspace from `jorekai-seo:setup` and at least one log week inside the month. Missing: name what is missing and stop.

## Steps

1. **Collect the month's files.** The export whose `Source:` line covers the month, the export of the period before it, and every `log/YYYY-Www.md` with most of its days inside the month. No export of the month itself: use the newest one inside it and name the window it covers.
   Done when both export paths and the list of log files exist, and the report's `Source:` line names both windows.

2. **Numbers.** Run `python3 <gsc-review>/scripts/gsc_opportunities.py EXPORT --previous EXPORT` (path relative to the `jorekai-seo:gsc-review` skill) with `brand_regex` and `min_impressions` from `config.md`, and copy its site totals and site baseline into the report. Nothing in this section is added up by hand.
   Done when totals, the median page, and the number of rows still open in the buckets stand in the file.

3. **What the month did.** One row per action from the month's log files: id, what changed, where, the verdict, and the number behind it. A row still inside its verify window is listed as open with the date it is graded on. A `too-small` row says so and is not a loss.
   Done when every action row of those weeks appears exactly once, the four counts under the table match it, and a week that fell to the neighbouring month is named under the table.

4. **AI answers.** Fill that section from the three sources in [references/ai-visibility.md](references/ai-visibility.md): the two console reports the owner exports, and the prompt set from `strategy.md`, asked once per assistant in the market's language. Each line carries the date it was read. A source nobody delivered reads "not read this month", never zero.
   Done when each of the three lines holds a number with a date, or those words.

5. **Write and hand over.** Copy [templates/report.md](templates/report.md) to `reports/YYYY-MM.md`, fill every placeholder, and end with the three things next month does in the loop's priority order. Each of the three is a `todo` row in the current week's log, or becomes one now (`scaffold.py <domain> --log` in `jorekai-seo:setup` gives path and id).
   Done when the file holds no placeholder and the three next steps carry log ids.

## Rules

- The report states what the files hold. A month with two shipped pages and no movement reads that way; no verdict is upgraded because the month looks thin.
- Every number names its source: totals and the median page name the export windows, verdicts name their log ids.
- The owner's words, not the loop's: "the page for boat licences moved from position 12 to 8", not "striking row won". Check ids and bucket names stay in the log.
- One page. What needs more space is a link into the workspace.
