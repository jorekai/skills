---
name: dx
description: Entry point for the developer experience skill set: which sub-skill to reach for, the flows (new machine, weekly sweep, something hurts), the priority ladder, and the risk classes that sit in front of every destructive action.
disable-model-invocation: true
---

# Developer experience

One loop drives everything: **measure the friction, fix the thing that costs the most time for the least work, prove it held, repeat**. Nothing is removed that a person would have to rebuild by hand.

## Workspace

Every skill reads and writes one private repository, `~/dx` in the examples and recorded during setup: `config.md` (what holds across machines), `standards.md` (what good looks like here), and one folder per machine under `machines/<hostname>/` holding `config.md` (project roots, history sources, budgets), `audits/` (one JSON per run), `log/dx/` (every change and its outcome, one file per ISO week), and `proposals/` (what nobody has decided yet). Layout and log format: `README.md` in the workspace, written by `jorekai-dx:setup`.

The workspace sits outside every project because its subject is the machine, not one repository. It is private because it names project paths and hostnames. No workspace yet: `jorekai-dx:setup` first.

## Flows

**New machine**, in this order:

1. `jorekai-dx:setup`: the workspace, the project roots, the history sources, and `standards.md`, which every later check measures against.
2. `jorekai-dx:repos`: what holds unsaved work. Nothing destructive runs anywhere until this is answered.
3. `jorekai-dx:machine`: free space, memory, caches, container storage.
4. `jorekai-dx:agent-config`: what a session finds when it opens each project.

**Weekly**, ten minutes: `jorekai-dx:and-now` reads the workspace and names the stage, at most three open items, and the next dated event. Each item that gets done leaves a log row with a verify date, and `jorekai-dx:grade` settles the rows whose date has come.

**Monthly**: `jorekai-dx:friction` over the last quarter of command history, then at most three proposals. `jorekai-dx:github` for what is waiting on other people. Then `jorekai-dx:report`, which writes what the month cost and what it gave back into `reports/dx/YYYY-MM.md` and names the three rows the next month starts with.

**The disk is full, or the machine crawls**: `jorekai-dx:machine` first for the numbers, then `jorekai-dx:repos` before removing anything inside a repository.

**A verify date has come**: `jorekai-dx:grade`. It recomputes each due row's measure from the newest audit of the tool that found it and writes the verdict. A row it cannot grade says what is missing, usually a pass that has to run again.

**Something is red, or a review is waiting**: `jorekai-dx:github`.

**Lost the thread**: `jorekai-dx:and-now`. It reads files, never the machine, so it answers in a second and costs nothing.

## Sub-skills

| Need | Skill | Invoked by |
|---|---|---|
| Where do I stand, what comes next? | `jorekai-dx:and-now` | you |
| Set up the workspace for this machine | `jorekai-dx:setup` | you |
| Which repositories hold work that exists nowhere else? | `jorekai-dx:repos` | agent or you |
| What is eating the disk, the memory, the container storage? | `jorekai-dx:machine` | agent or you |
| What is red, stuck, or waiting on a review across the repositories? | `jorekai-dx:github` | agent or you |
| Does a session find its way in every project? | `jorekai-dx:agent-config` | agent or you |
| What does my command history say costs the most time? | `jorekai-dx:friction` | you |
| Did the fix hold, and what do the due rows say? | `jorekai-dx:grade` | agent or you |
| What did the month do to this machine? | `jorekai-dx:report` | you |

## Priority ladder

Each rung depends on the one before it. A finding on a lower rung waits.

1. **Nothing is lost, and nothing leaks.** `git.dirty`, `git.unpushed`, `repo.no-remote`, `repo.secret-exposed`. These outrank everything, including a full disk, and nothing destructive runs against a repository that reports one of them. An exposed credential sits on this rung because it is the finding a later commit cannot undo: a history keeps what it was given, so the cost is a rotation, not an edit.
2. **The machine runs.** `disk.low`, `mem.pressure`. Nothing else finishes on a full disk.
3. **Someone else is waiting.** `pr.review-requested`, `ci.failing`, `alert.open`. The cost of these falls on other people, which is why they come before anything that only costs you.
4. **The projects and the sessions work.** `repo.lock-drift`, `agent.hook-broken`, `agent.pointer-drift`. A broken hook or a lying pointer costs time in every session until someone looks.
5. **Space and time come back.** `disk.cache`, `container.*`, `disk.large-dir`, then `friction.*`. Biggest return for the smallest risk first.
6. **Tidiness.** `git.stale-branch`, `repo.no-readme`, and the rest. Worth doing, never worth doing first.

## Reading a report

Every measuring script prints the same shape without `--json`, so one reading order works everywhere:

1. The first two lines say what was measured and what it was measured against, so a number can be judged without opening `standards.md`.
2. The counting line is a bar of four counts, `FAIL`, `WARN`, notes, passed, in that order. A zero is dimmed.
3. Each finding is one line of three columns: its level, its check id, and what it costs now as one number and one unit. Findings come in level order, and the costliest first inside a level.
4. Under a finding stand at most five targets with their own share of the cost, then `+N more` when the JSON holds more. Identical notes fold into one line.
5. The last zone is `next`: one line that starts with a verb, and under it the gate it waits on. Every id is looked up in [references/fixes.md](references/fixes.md) for the fix and the risk class.

The console report is for the decision, the JSON is for the record. Only the JSON is written to `audits/`.

A terminal gets the same report in colour: the level word, the verdict, the check id and the measure carry the colour their role already has. Nothing is coloured that a word does not already say, and a pipe, a redirect and a subagent see plain text. Reason: `decisions/0022`; the layout inside each zone: `decisions/0028`.

## Writing the answer

The report is for the terminal; the answer is for the person, and it has one shape everywhere in this theme:

1. One line first: what ran, what it was measured against, and the path of the JSON. The reader can open it, so nothing inside it is repeated in prose.
2. One table, in ladder order, at most five rows, one row per check id and never one per target. What the table drops is one sentence under it, never a second table.
3. Every cost is one number and one unit, copied from the finding's `measure` block. A cost written as prose cannot be graded later.
4. The fix cell names who does it when that is not you.
5. One line last: the single next action.

The columns, per skill:

- `jorekai-dx:repos`, `jorekai-dx:machine`, `jorekai-dx:github`, `jorekai-dx:agent-config`: `check id | cost | targets | fix | class`
- `jorekai-dx:friction`: `shape | cost | what would replace it | what must be true`
- `jorekai-dx:grade`: `row | then | now | verdict | next`
- `jorekai-dx:and-now`: no table. The script's `stage`, at most three `now`, one `then`.
- `jorekai-dx:setup`: no table. The files it wrote and the values still unconfirmed.
- `jorekai-dx:report`: no table. The path of the report, its headline, and the four counts.

A skill whose answer is a file names the file and writes no table. Reason: `decisions/0023`.

## Principles

- A change is logged only with a measure the same script can recompute later. Reclaimed bytes, a count of failing checks, a duration. Without one it is a proposal, not an action.
- Every measure counts a cost, written as one number and one unit, so lower is better and zero means the finding is gone. Free space is logged as the bytes missing from the floor for that reason. A measure that drifts on its own, such as an age, is the wrong measure.
- Every destructive action carries a class, and the class decides the flow, not the judgment of the moment. See [references/risk-classes.md](references/risk-classes.md).
- Findings are facts, fixes are decisions. A script reports what is, a person or the model decides what happens.
- The same finding gets one row, not one row per affected path.
- Raw history never enters the workspace unredacted. Command lines carry tokens, customer names, and customer paths.
- A measurement that needs the network says so. Everything else works offline.

## Reference

- The three risk classes and the gate above them: [references/risk-classes.md](references/risk-classes.md)
- What every check id means, its fix, its class, and its measure: [references/fixes.md](references/fixes.md)
- Tools and what each is for: [references/tools.md](references/tools.md)
- Documented facts with source and check date, and the list of heuristics: [references/sources.md](references/sources.md)
