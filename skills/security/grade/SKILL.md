---
name: grade
description: "Check whether logged security fixes held, using the latest audit from the tool that found each issue. Write won, no-change, or returned. Use when a review date is due or overdue, during the weekly pass, or when asked whether a security fix worked."
---

# Security grade

A log row is a claim: this action removed this much cost, and by this date the same measure will show it. Grading is the moment the claim is settled. Every measure counts a cost, so the verdict is arithmetic: the cost fell or reached zero (`won`), it stayed inside the tolerance (`no-change`), it rose past it (`returned`). `dropped` belongs to a person, because it means the action was never carried out.

This skill reads the workspace only. It never reads a repository, so a row whose newest audit is older than the action is reported as ungradable instead of being graded against a number from before.

## Steps

1. **Run the pass without writing anything.**

   ```bash
   python3 scripts/grade.py --root <workspace path> [slug]
   ```

   The script path is relative to this skill's directory. Exit code 2 means there is no workspace or no such repository folder: the answer is `jorekai-security:setup`, stop here.
   Done when every row past its verify date carries either a verdict or one sentence saying what is missing.

2. **Resolve missing evidence, then measure again.** Check the reason given: a missing audit, an audit from before the change, an unchecked rule, incompatible units, a table row malformed enough to not parse, or a `Verify after` cell that is not a `YYYY-MM-DD` date. Rerun the measuring skill with the original arguments, then grade again; a malformed row or a bad date needs a hand edit to the log file itself.
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

- `won` means the cost fell or reached zero at this date. It does not mean the class of flaw is gone from the repository: it means this finding, on this target, no longer costs what it cost.
- `returned` on anything under `cred.*` is the serious one. A credential that counts again means either the rotation did not happen or a second copy of the value exists. It goes to the front of the ladder, above everything else that is open.
- `returned` on `build.*` usually means a merge brought the old file back. The next attempt is a check in the pipeline itself, not the same edit again.
- `no-change` twice on the same check id means the check is the wrong measure for the work, not that the work failed. Rewrite the row, or record the finding under `accepted` in `config.md` with its reason.
- Close a review action only when the audit records a result for its rule. A missing result or `null` keeps the action open. Rerun review if the audit has no results per rule (`decisions/0030`).
- A missing total does not prevent grading another rule whose result is known.
- A count compares exactly, because a count does not drift. The other unit families allow five percent of the starting value, which is why almost every check in this theme measures in `count`.
- An audit from before the action cannot show whether the fix held. Measure again before grading.
