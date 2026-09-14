---
name: guards
description: "Do the guards of a generated repository still stand, and did anybody walk around one, in one pass via scripts/guards.py: suppressions no waiver names, waivers past their date, a gate nothing enforces on the server, contract files without an owner, declared guards with no command or no workflow, switched-off configuration, bars that stand nowhere, rule classes without a test, and the coverage, assertion, gate-time and dead-code bars. Use when a gate went red and a suppression is proposed, after a merge, for the weekly pass, or when asked whether the guards still stand or whether anything got past one."
---

# Stack guards

One pass over what an agent could have done to the locks. It reads the tree, the declaration, and what the gate left under `.stack/` and `coverage/`. It runs nothing: not the gate, not a linter, not a test. A guard the pass finds green because it never ran is exactly the case the pass exists for, so an artefact that was never written is `null` and not zero.

Three questions, in ladder order. Is there a way past the lock: nothing enforced on the server, nobody owning a contract file, a suppression no waiver names, a waiver past its date. Does every declared guard run: a command, a workflow, a configuration that does not switch it off, a bar that stands in a file, a rule with a test. Is the bar reached: coverage, assertions, gate time, dead code.

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <slug>
   python3 scripts/guards.py <guards flags from that output> --json \
     > <workspace>/repos/<slug>/audits/YYYY-MM-DD-guards.json
   ```

   The script paths are relative to this skill's directory. Run it without `--json` first when you only need to look. The gate should have run once before, on the full tree, or the three bars it writes stay unknown.
   Done when the JSON says how the declaration was read, how many source files it saw, and every one of the seventeen ids carries a number or `null`.

2. **Rank the findings, do not list them.** The pass already ranks by the `Rung` column of [../stack/references/fixes.md](../stack/references/fixes.md), and `--explain RANK` prints the chain behind one line: what it means, where it comes from, the fix, the way back, and what closes it. The answer is one table, `check id | cost | where | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`. A `null` is written as `unknown` with the artefact that is missing.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Close the ways past the lock first.** A suppression is fixed in the code; where it cannot be, a waiver with reason, date and owner goes into the declaration, which is a contract file, so it is a branch under review by a person and not a commit. An undated enforcement entry is dated only after the required check is confirmed on the server. A placeholder owner is replaced by a person.
   Done when every `escape.*` id reads zero or stands under a review that a person will merge.

4. **Make every declared guard run, then reach the bars.** A guard with no command or no workflow is wired again; a switched-off configuration loses its switch; a bar that stands in no file is pointed at the declaration. A bar that is not reached is reached by the code, never by moving the number, and a slow gate is split by cost.
   Done when every `guard.*` and `dead.*` id reads zero, or its row carries the number it stands at and a verify date.

5. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <file or guard name> --action "<what happened>" --class <class> \
     --then "<number> <unit>" --status applied
   ```

   The number and the unit both come from the finding's `measure` block, and the unit is copied as it stands there: `percent` for coverage, `seconds` for the gate, `count` for the rest. A finding nobody acted on is not a row.
   Done when each row names the check id, the class that ran, a measure the same script recomputes, and a verify date.

## Interpretation

- `null` names the artefact that is missing. `coverage/coverage-summary.json` comes from the unit runner, `.stack/gate-times.log` from a full run of the gate, `.stack/dead.json` from the dead-code step. A gate run with `--staged` writes no timing, because the hook's time is not the number the bar is about. A `null` is never a pass and never settles a log row (`decisions/0030`).
- Every `escape.*` id fails, and so do a guard with no command, one no workflow runs, and a rule with no test. Those are a lock that is gone. A bar that is not reached warns: the lock stands, and the number under it is what the row then measures.
- The local hook is not the lock. It is fast feedback, and a flag walks past it by design. The lock is the required check on the server, and `escape.unenforced` counts the gap between the two until a person confirms the check and dates the entry.
- A waiver is named and dated, and whoever enters it is not whoever needs it: the declaration stands under an owner, so the entry is a review (`decisions/0036`). An entry missing its reason, its date or its owner never counted, so it is not expired either.
- A rule without a test is not run by the gate, and this pass counts the same gap without running anything (`decisions/0037`).
- The suppression scanner and the assertion check are text rules. They count what the linter and the runner would also refuse, so a skipped run cannot hide it, and a spelling they do not know is not counted.
- `--accept` leaves a finding out of the counts when the declaration or the workspace records it as accepted with a reason and a date. `--snapshot` compares the repository's declaration to the workspace's copy and notes the keys that differ; a note is not a finding.
- A first pass on an adopted repository reports its suppressions as a list of proposed waivers waiting for a reason. That is the baseline. What matters at the second pass is which numbers moved.
