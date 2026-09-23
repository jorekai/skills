---
name: grade
description: "Check whether a logged stack fix held, using the newest audit from the pass that found it: won, no-change, or returned, written into the log. Use when a verify date is due or overdue, during the weekly pass, or when asked whether a guard fix, a waiver removal, or a boundary change worked."
---

# Stack grade

A log row is a claim: this action removed this much cost, and by this date the same measure will show it. Grading is the moment the claim is settled. Every measure counts a cost, so the verdict is arithmetic: the cost fell or reached zero (`won`), it stayed inside the tolerance (`no-change`), it rose past it (`returned`). `dropped` belongs to a person, because it means the action was never carried out.

This skill reads the workspace only. It never reads a repository, so a row whose newest audit is older than the action is reported as ungradable instead of being graded against a number from before.

## Steps

1. **Run the pass without writing anything.**

   ```bash
   python3 scripts/grade.py --root <workspace path> [slug]
   ```

   The script path is relative to this skill's directory. Exit code 2 means there is no workspace or no such repository folder: the answer is `jorekai-stack:setup`, stop here.
   Done when every row past its verify date carries either a verdict or one sentence saying what is missing.

2. **Resolve missing evidence, then measure again.** Check the reason given: a missing audit, an audit from before the change, a measure the pass could not take, incompatible units, a table row malformed enough to not parse, or a `Verify after` cell that is not a `YYYY-MM-DD` date. A measure that was not taken means the gate has not run in full since the change; run it, then the measuring skill with the original arguments, then grade again. A malformed row or a bad date needs a hand edit to the log file itself.
   Done when every gradable row has a fresh audit behind it, and every remaining gap is one a person has to answer.

3. **Write the verdicts.**

   ```bash
   python3 scripts/grade.py --root <workspace path> [slug] --write
   ```

   One outcome row per verdict, and the action row's status set to it. Nothing else moves.
   Done when every settled row appears once under the outcomes table and no longer counts as due.

4. **Answer per verdict, not per row.** One table, `row | then | now | verdict | next`, at most five rows; the rest of the shape is in the router's `## Writing the answer`. A `won` needs no next step. A `no-change` and a `returned` each need one, and the next step is not the same action again.
   Done when every `returned` row names what the next attempt does differently, and every ungradable row names who has to look.

## Interpretation

- `won` means the cost fell or reached zero at this date. It does not mean the class of finding is gone from the repository: it means this finding, on this target, no longer costs what it cost.
- `returned` on anything under `escape.*` is the serious one. A suppression that counts again is either a merge that brought the old line back or a new one somebody wrote, and both mean the review gate did not hold. It goes to the front of the ladder, above everything else that is open.
- `returned` on `guard.*` usually means a generated file was edited by hand and the guard lost its bar. The next attempt regenerates the file and looks at why the edit was made.
- `no-change` twice on the same bar (`guard.coverage`, `guard.slow`, `dead.*`) means the bar is the wrong measure for the work, not that the work failed. Rewrite the row against the finding the work moves, or record the finding under `accepted` in `config.md` with its reason.
- A measure the pass could not take is `null`, and a `null` keeps the row open (`decisions/0030`). The passes read what the gate left behind, so a coverage report, a gate timing, or a dead-code count that was never written is not a zero.
- A count compares exactly, because a count does not drift. `percent` and `seconds` allow five percent of the starting value, because a coverage shortfall and a gate time move under a tree that is being worked on.
- An audit from before the action cannot show whether the fix held. Measure again before grading.
