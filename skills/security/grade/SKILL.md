---
name: grade
description: "Give a verdict to log rows whose verify date has passed via scripts/grade.py: recompute each row's measure from the newest audit of the tool that found it, then write won, no-change, or returned into the log. Use when a row is due for a verdict, when the weekly pass reports rows past their verify date, or when asked whether a security fix held."
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

2. **Close the gaps, then measure again.** A row that cannot be graded names its reason: no audit of that tool, an audit older than the action, a check the audit does not carry, or two units that do not compare. Run the measuring skill the row names, with the same arguments as before, then grade again.
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
- A row about a rule from `jorekai-security:review` is graded against the rule, so it settles when the sink is gone or the mitigation stands beside it. A rule whose file no longer exists reads zero and needs a person: a file that was deleted and a flaw that was fixed look the same to a matcher.
- A count compares exactly, because a count does not drift. The other unit families allow five percent of the starting value, which is why almost every check in this theme measures in `count`.
- An audit older than the action grades nothing. The verdict would otherwise be measured from before the change, which always reads as `won`.
