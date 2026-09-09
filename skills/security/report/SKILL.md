---
name: report
description: Monthly report for this repository, written from the workspace files: what every check cost when the month opened and what it costs now, every action of the month with its verdict and the class it ran under, what is still open in ladder order, and the three things next month starts with.
disable-model-invocation: true
argument-hint: "[repository] [YYYY-MM]"
---

# Monthly report

Writes `repos/<slug>/reports/security/YYYY-MM.md`. `jorekai-security:and-now` answers "what next" in the middle of the loop; this answers "what did the month do to this repository". Every number comes from files that already exist: the audits in the workspace and the log weeks of the month.

Needs the workspace from `jorekai-security:setup`, one audit inside the month, and one before it. Missing: the report says which half is missing rather than reporting a repository nobody measured.

## Steps

1. **Run the pass for the month.**

   ```bash
   python3 scripts/report.py --root <workspace> <slug> --month YYYY-MM
   ```

   Read it before writing anything. A month with no audit inside it, or with one and nothing before it, says so in its own line, and that line is the answer until a measuring pass has run.
   Done when the console report names the log weeks it read and the audits behind every number.

2. **Fill the gap, or say it stays open.** A tool with no audit inside the month has no line in the report. Run that skill now and the numbers close the month; leave it and the report names what it does not cover.
   Done when every tool that was supposed to run either has an audit in the window or stands under "what is not in here".

3. **Write the file.**

   ```bash
   python3 scripts/report.py --root <workspace> <slug> --month YYYY-MM --write
   ```

   Done when `reports/security/YYYY-MM.md` holds no placeholder and every action row carries a log id.

4. **Turn the three next steps into rows.** The report names the three open rows at the top of the ladder. Each one is already a row, or it becomes one now with `scaffold.py --append-row` in `jorekai-security:setup`, so the next month grades what this one proposed.
   Done when each of the three names a log id that exists.

5. **Hand over the file, not a summary.** The answer is one line: the path, the headline, and the counts. Everything else is in the file. This skill writes no table into the conversation.
   Done when the path and the one line are the whole answer.

## Rules

- The report states what the files hold. A month with two actions and no movement reads that way; no verdict is upgraded because the month looks thin.
- A number in the report is a number a script recomputed. Two measures in different families do not compare and are left out rather than converted into a change nobody can check.
- No value ever reaches this file. A credential is named by its fingerprint and its place, the same way the audit named it, because a report is the document most likely to be pasted somewhere else.
- An action belongs to the month it was applied in. A week that straddles two months belongs to the month holding most of its days, so no action is counted twice across a year.
- The report reads the tools of this theme alone. An audit written by another tool is named under what the report does not cover, never counted into it.
- A row that carries a verdict is settled, whatever its status cell still says. Listing it as open would put a finished action into the next month's three next steps.
- What is still open is not scoped to the month. A row from an older week that nobody settled is exactly what a monthly read is for.
- One page. What needs more space is a link into the workspace.
