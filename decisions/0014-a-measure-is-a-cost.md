# 0014: A measure is a cost, written as one number and one unit

Date: 2026-09-05

## Context

Both themes promise the same loop: every action gets a measure and a verify date, and at the date the measure is recomputed and the row gets a verdict. The recomputation was left to whoever read the log. It never happened, because the measure sat in the log as free text ("41 GB free", "four repos clean now"), and free text cannot be compared to a number a script produced last week.

Two shapes were on the table. Keep the measure as the check's natural reading and add a direction column, so `disk.low` stays "free bytes" with the goal `up` while `repo.no-ci` stays "repositories" with the goal `down`. Or define every measure so that it counts what the finding costs, and let zero mean the finding is gone.

A direction column is one more thing to look up, one more thing to get wrong, and it splits the comparison into two cases in every script that grades a row.

## Decision

Every measure counts a cost. Lower is better, and zero means the check no longer fires. A measure that reads naturally as a benefit is inverted at the source: `disk.low` measures bytes short of the floor, not bytes free; `mem.pressure` measures percentage points below the floor, not points available.

A measure is one number and one unit from a closed set: `bytes` (written in the log as `B`, `KB`, `MB`, `GB`, or `TB`), `count`, `percent`, `seconds`. A unit outside the set is rejected when the row is written, not discovered when the row is graded.

A finding in an audit JSON carries the measure as `"measure": {"value": N, "unit": U, "by": {target: value}}`, beside `id`, `level`, `message`, and `data`. `by` holds the same measure per target, so a row about one repository is graded against that repository and a row about the machine is graded against the total. A check that could not measure carries `"measure": null`. A passing check carries zero, which is what makes "the finding is gone" a fact rather than an absence.

`references/fixes.md` names the unit of every check id, and `scripts/check.sh` fails when a script emits a unit the table does not name.

The four verdicts stay: `won` when the cost fell past the tolerance or reached zero, `no-change` inside the tolerance, `returned` when it rose past it. `dropped` is never computed, because it means a person decided not to carry the action out.

## Consequences

Grading is arithmetic on two numbers, so `jorekai-dx:grade` proposes a verdict without reading prose, and a row that cannot be graded says why instead of getting a guess.

The cost of the rule is one inversion per check that reads as a benefit. Two exist today, both in `jorekai-dx:machine`, and both state the floor they measure against in `references/fixes.md`.

Tolerance belongs to the unit, not to the check: `count` compares exactly, the continuous units allow five percent of the starting value, because a disk moves under a machine that is being used. A measure that drifts on its own is the wrong measure, so an age in days is never one: `git.stash-old` counts stash entries past the retention rather than the age of the oldest.
