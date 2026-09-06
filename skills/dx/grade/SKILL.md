---
name: grade
description: Give a verdict to log rows whose verify date has passed via scripts/grade.py: recompute each row's measure from the newest audit of the tool that found it, then write won, no-change, or returned into the log. Use when a row is due for a verdict, when the weekly pass reports rows past their verify date, or when asked whether a fix held.
---

# Grade

A log row is a claim: this action removed this much cost, and by this date the same measure will show it. Grading is the moment the claim is settled. Every measure counts a cost, so the verdict is arithmetic: the cost fell or reached zero (`won`), it stayed inside the tolerance (`no-change`), it rose past it (`returned`). `dropped` belongs to a person, because it means the action was never carried out.

This skill reads the workspace only. It never measures the machine, so a row whose newest audit is older than the action is reported as ungradable instead of being graded against a number from before.

## Steps

1. **Ask what is due and what it would be graded against.** Run the script without writing anything. Each row prints its starting measure, the recomputed one, the proposed verdict, and the audit it came from.

   ```bash
   python3 scripts/grade.py --root <workspace> [machine]
   ```

   A row with no verdict prints why: no audit of that tool, an audit older than the action, a check id the pass did not produce, a measure the row never carried.
   Done when every due row has either a proposed verdict or a stated reason.

2. **Close the gaps the script named, then ask again.** An audit older than the action or a missing check id is answered by running the skill that owns the check with the same arguments the workspace prints, and saving the new audit. A row whose `Then` is not a number and a unit cannot be graded at all: settle it by hand and write the outcome row yourself.
   Done when every row that can be measured again has been, and the rest are named.

3. **Write the verdicts.** The same command with `--write` appends one outcome row per verdict and sets the action row's status to it, so the same row is never graded twice.

   ```bash
   python3 scripts/grade.py --root <workspace> [machine] --write
   ```

   A row nobody carried out gets `dropped` by hand, with the reason in the outcome row. Never write `dropped` over a row that has a measure: that hides a fix that did not hold.
   Done when no row is left both past its verify date and without a verdict.

4. **Answer what each verdict asks for.** `won` closes the row and nothing follows. `no-change` means the action was not the cost: the finding goes back to open, or to `proposals/` if nobody knows what would move it. `returned` means the fix treated a symptom, so the next row addresses what refills it, not the same removal again.
   Done when every `no-change` and `returned` row has a next step or a written decision to stop.

## Interpretation

- A count compares exactly. Bytes, seconds, and percentages allow five percent of the starting measure, because a machine in use moves under the measurement. A change smaller than that is `no-change`, whatever it feels like.
- A row about one target is graded against that target's own share of the finding, not the total. A target the finding no longer names costs nothing, which is the win.
- A row with no target is graded against the total, so it answers for the machine and not for one path.
- `returned` inside a short verify window is the most useful row in the log. It says the removal works and the cause was never touched.
- Two verdicts in a row on the same check id mean the check is the wrong measure for the work, not that the work failed. Rewrite the row, or move the finding to `standards.md` as accepted.
