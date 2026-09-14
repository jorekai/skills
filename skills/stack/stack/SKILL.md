---
name: stack
description: "Choose the next stack skill for a new monorepo, an existing repository to adopt, or a weekly pass over the guards. Explains the declaration, the escapes, the ladder, and how a fix is measured."
disable-model-invocation: true
---

# Stack

One loop drives everything: **declare the repository, generate the guards, measure whether they still stand and whether anybody walked around them, repeat**. This theme is the first in the collection that creates something: a monorepo in which an agent cannot reach past a guard, because every guard is wired so that switching it off is a review by a person and not a commit.

A gate an agent can switch off is decoration. The list of exits is short and every agent finds it: `--no-verify`, `@ts-ignore`, `as any`, `eslint-disable`, `it.skip`, `it.only`, a test deleted instead of repaired, a bar lowered. So this theme measures not only whether a guard exists, but whether somebody went through the back door.

## Four sentences that carry the design

1. **No allowed amount, a list of names.** Every suppression breaks the build. One that stays is named under `waivers` in `stack.yaml` with file, line, reason, owner and a date it expires. What is not named is red now; what is past its date is red too.
2. **The agent does not grant itself anything.** `stack.yaml` and every other contract file stand under `CODEOWNERS`. Adding a waiver or raising a bar is a review by a person, which is why a soft bar stays hard.
3. **The server is the truth.** A local hook is fast feedback and a flag walks past it. The lock is the branch protection with the gate as its required check, and `escape.unenforced` measures exactly that gap.
4. **A project's own bans are first class.** A standard linter does not know this repository's architecture. One file per ban, with an id, a message that names the allowed state, and a test that proves the ban fires, is the only place an agent is taught a boundary of its own.

Two properties that pass for comfort and are security properties: **speed**, because a gate that takes five minutes is a gate people skip, so the declaration carries a time bar and there is one command, not seven; and **messages that lead to the fix**, because `boundary violation in packages/ui` makes an agent guess and `packages/ui imports @app/ports, allowed: @app/config` makes it correct the line. Every gate message and every rule names the rule, the place, and the allowed state.

## Workspace

Every skill reads and writes one private repository, `~/stack` in the examples and recorded during setup: `config.md`, `standards.md`, and one folder per repository under `repos/<slug>/` holding `config.md`, a snapshot of the repository's `stack.yaml`, `audits/` (one JSON per run, two tools), `log/stack/` (one file per ISO week), `proposals/` and `reports/stack/`.

The declaration itself lives in the measured repository, because the project's own tooling reads it. The findings live here. Reasons for a workspace of this theme's own, and what it costs against `decisions/0025`: `decisions/0035`.

A repository is this theme's business when its `config.md` says `role: stack`. No workspace yet, or no such repository: `jorekai-stack:setup` first.

## Flows

**New repository**, in this order:

1. `jorekai-stack:setup`: the workspace, the folder for this repository, the profile.
2. `jorekai-stack:choose`: the two axes, the eight adapters, the bars, written as `stack.yaml`.
3. `jorekai-stack:new`: the tree from the official generator, the guards over it, the ports wired, the gate green before any account exists.
4. `jorekai-stack:guards`, then `jorekai-stack:drift`: the first measure, which is the baseline and not a to-do list.

**Existing repository**: `jorekai-stack:setup`, then `jorekai-stack:new` with `--adopt --plan`, which names what it would write, what it leaves alone, and the waivers and bars it proposes so the repository is green on the day of the adoption. Then the same two passes.

**Weekly**, ten minutes: `jorekai-stack:and-now` names the stage, the open items in ladder order, and the next dated event. Each item that gets done leaves a log row with a measure and a verify date. A row past its verify date goes to `jorekai-stack:grade`, which recomputes the measure and writes the verdict.

**Monthly**: `jorekai-stack:report` writes what the month cost and what it gave back into `reports/stack/YYYY-MM.md`, from the audits and the log alone.

**A gate went red and the agent proposes a suppression**: that is the case this theme exists for. The answer is the code, or a waiver through review, never the flag. `jorekai-stack:guards` counts what was chosen.

**Lost the thread**: `jorekai-stack:and-now`. It reads files, never the network, and never the repository.

## Sub-skills

| Need | Skill | Invoked by |
|---|---|---|
| Where does this repository stand, what comes next? | `jorekai-stack:and-now` | you |
| Take a repository into the workspace, with a profile | `jorekai-stack:setup` | you |
| Which OSS level, which target, which adapter per port, which bars? | `jorekai-stack:choose` | you |
| Generate the tree and the guards, wire the ports, or adopt a repository that exists | `jorekai-stack:new` | you |
| Do the guards still stand, and did anybody walk around one? | `jorekai-stack:guards` | agent or you |
| Does the tree still match the declaration: boundaries, adapters, lock, generated files? | `jorekai-stack:drift` | agent or you |
| Did the fix hold? Settle measured rows and name what still needs evidence | `jorekai-stack:grade` | agent or you |
| What did the month do to this repository? | `jorekai-stack:report` | you |

## What this theme does not do

- It does not grade what the wired guards find. The pipeline checker, the secret scanner and the advisory lookup are wired into the gate and measured by `jorekai-security` as `build.*`, `cred.*` and `dep.*`. This theme measures that they are wired and cannot be walked around; that theme measures what they catch. No check is counted twice (`decisions/0015`).
- It does not measure the machine or the session. Whether anything runs on push is `repo.no-ci` in `jorekai-dx`; whether the declared guard runs there is `guard.unwired` here. The five borders stand in [references/fixes.md](references/fixes.md).
- It builds depth 3 as declaration lines, not as code: seven things with a recommendation and a date, and `decl.undecided` counts the ones past it.
- It has no ratchet for suppressions. A suppression is named or it is red. Dead code alone has a bar, because its stock in an old repository is too large for a list of names, and the bar stands under `CODEOWNERS`.
- It runs no mutation tests. The assertion requirement in the runner and the text rule beside it catch the common shape of an agent's empty test.
- It carries no price, free tier or limit for any adapter. An adapter name is an opinion; a price would be a platform fact that ages every month.
- It supports one app generator. A second one costs a row in `references/generators.md` of `jorekai-stack:new` and a second entry in its generated-files table, never a second template tree.
- `jorekai-stack:new` writes no log row. A scaffold runs once, and there is no measure to recompute for it later; it ends on the green gate, and the rows are written by the two passes.

## Priority ladder

Each rung depends on the one before it. A finding on a lower rung waits.

1. **The declaration is right.** `decl.absent`, `decl.unmatched`. Every check below reads this file as its bar.
2. **The lock cannot be walked around.** `escape.unenforced`, `escape.unowned`, `escape.expired`. A gate green on a laptop with nothing enforcing it on the server is an agreement, not a lock.
3. **Nobody went through the back door.** `escape.type`, `escape.lint`, `escape.test`. A suppression without a waiver is the cheapest way to make a rule disappear.
4. **A declared guard runs.** `guard.missing`, `guard.disabled`, `guard.unwired`, `guard.unbarred`, `guard.rulegap`. A guard that is written down and never runs is worse than none, because everybody believes the branch is defended.
5. **The install is reproducible.** `lock.incomplete`, `lock.runtime`. Two machines that install two trees make a green pipeline say nothing about the next run.
6. **The convention holds.** `boundary.crossed`, `boundary.cycle`, `adapter.bypassed`, `decl.generated`. Each of these costs more every day, because the next file is written like the one beside it.
7. **The bar is reached.** `guard.coverage`, `guard.assertionless`, `guard.slow`, `dead.export`, `dead.file`, `dead.dep`, `boundary.deep-import`, `adapter.missing`, `adapter.untargeted`. The guard exists and runs, and the number under it is below what the declaration promised.
8. **What stayed open.** `decl.undeclared`, `decl.undecided`. Costs nothing today and everything at the next handover.

## Reading a report

Every measuring script prints the same shape without `--json`, so one reading order works everywhere:

1. The first two lines say what was measured and what it was measured against.
2. The counting line is a bar of four counts, `FAIL`, `WARN`, notes, passed, in that order. A zero is dimmed.
3. Each finding is one line of a table: rank, level, check id, cost, the place it names, and the risk class. Findings come in level order, and inside a level in the order of the `Rung` column of [references/fixes.md](references/fixes.md), which is the ladder above.
4. `--explain RANK` prints the chain behind one line: `what`, `weight` with the gate the id stands under, `means`, `cause` when the pass proved one, `fix`, `undo`, `verify`. `--previous FILE` takes an earlier findings JSON and adds a `change` column of `=`, a signed number, or `new`. A finding with no cost, which is every note, carries its sentence dimmed under its row.
5. The last zone is `next`: one line that starts with a verb, and under it the gate it waits on.

The console report is for the decision, the JSON is for the record. Only the JSON is written to `audits/`.

A note without a measure is not a pass. A coverage report that was never written, a gate that never logged its time, a dead-code count nothing produced: each carries `null` and no number, because a zero there would settle a log row with a figure nobody took (`decisions/0030`).

A terminal gets the same report in colour: the level word, the check id and the measure carry the colour their role already has, and a pipe, a redirect and a subagent see plain text (`decisions/0022`, layout `decisions/0028` and `decisions/0031`).

## Writing the answer

The report is for the terminal; the answer is for the person, and it has one shape everywhere in this theme:

1. One line first: what ran, what it was measured against, and the path of the JSON. The reader can open it, so nothing inside it is repeated in prose.
2. One table, in ladder order, at most five rows, one row per check id and never one per file. What the table drops is one sentence under it, never a second table.
3. Copy measured costs from the finding's `measure` block, keeping the number and the unit. Write `unknown` when a measurement is `null`, and say which artefact is missing. Do not replace it with zero.
4. A finding is named by its path and its line, never by a value. A key in an env file is quoted as its name and its shape.
5. One line last: the single next action, and the gate it waits on when it touches a contract file.

The columns, per skill:

- `jorekai-stack:guards`, `jorekai-stack:drift`: `check id | cost | where | fix | class`
- `jorekai-stack:grade`: `row | then | now | verdict | next`
- `jorekai-stack:new`: `path | action | reason`, the plan before anything is written; after the write, no table: the generator command, the paths written, and the gate's exit code.
- `jorekai-stack:and-now`: no table. The script's stage, at most three open items in ladder order, the next verify date.
- `jorekai-stack:setup`: no table. The folder it wrote, the profile that was chosen, and the pointer block.
- `jorekai-stack:choose`: no table. The path of `stack.yaml`, the two axes, the eight adapters, and the caveat when there is one.
- `jorekai-stack:report`: no table. The path of the report, its headline, and the four counts.

A skill whose answer is a file names the file and writes no table. Reason: `decisions/0023`.

## Principles

- A finding earns a log row when it earns a check. What a model found and no script recomputes is a proposal, not an action.
- Findings are facts, fixes are decisions. A script reports what is, a person decides what happens, and a contract file changes through review.
- Every measure counts a cost, as one number and one unit, so lower is better and zero means the finding is gone.
- The declaration is data, not memory. Whatever a session decides about this repository goes into `stack.yaml`, or the next session decides it again.
- An exception is named and dated. Whoever enters it is not whoever needs it (`decisions/0036`).
- A rule without a test is not run (`decisions/0037`).
- The same finding gets one row, not one row per affected path.
- A pass reads files and never runs the gate. What the gate left under `.stack/` is the evidence; what it never wrote is `null`.

## Reference

- What every check id means, its fix, its class, its rung, and its measure: [references/fixes.md](references/fixes.md)
- The declaration, section by section, and the bars: [references/declaration.md](references/declaration.md)
- The eight ports, the two axes, the adapters, the env keys, the vendor modules: [references/ports.md](references/ports.md)
- The contract files, the generated files, the gate order, the artefacts: [references/contracts.md](references/contracts.md)
- The rule engine and the six starting rules: [references/rules.md](references/rules.md)
- The three depths and what adopting means: [references/tiers.md](references/tiers.md)
- The three risk classes and the gate above them: [references/risk-classes.md](references/risk-classes.md)
- Tools, what each is for, and what happens when it is missing: [references/tools.md](references/tools.md)
- Documented facts with source and check date, and the list of heuristics: [references/sources.md](references/sources.md)
