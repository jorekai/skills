---
name: friction
description: What the command history says costs time, via scripts/friction.py: command shapes that repeat, pairs run one after the other, shapes that fail, retry loops, and the slowest totals. Every line is redacted before it is counted. Writes proposals, not actions.
disable-model-invocation: true
argument-hint: "[days]"
---

# Friction

Turns months of command history into a short list of things worth automating. Reads the history sources named in `machines/<hostname>/config.md` and the thresholds in `standards.md`. No workspace: ask for the history paths and skip the log steps.

This skill reads history and writes proposals. It changes nothing on the machine, and it never opens a session transcript to read what was said: agent sessions count as volume only.

## Steps

1. **Run the pass over the window that matters.** A quarter is enough to see a habit and short enough that the machine has not changed underneath it.

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags
   python3 scripts/friction.py <friction flags from that output> --days 90 --json > <workspace>/machines/<hostname>/proposals/YYYY-MM-DD-friction.json
   ```

   The script paths are relative to this skill's directory. The `friction` line holds every history source the machine config records and the threshold from `standards.md`; a source that is recorded but missing on disk is skipped, not an error. Without `--json` the report prints shapes only, never a command line.
   Done when the report names a command count above zero. Zero means the paths are wrong, not that the machine is quiet.

2. **Pick at most three, by time cost.** A shape that runs eighty times and takes two seconds costs less than one that runs six times and takes four minutes. A retry loop costs more than either, because the person is waiting and guessing. Ignore what is merely frequent.
   Done when each pick has a number behind it: runs, failure rate, or total seconds.

3. **Turn each pick into a proposal, not an action.** Write `proposals/<slug>.md` with the finding, the number, what would replace it, and what would have to be true for it to be worth the change. A proposal becomes a log row only once it has a measure the same pass recomputes: the same shape's runs, failure rate, or seconds in the next window. The answer is one table, `shape | cost | what would replace it | what must be true`, one row per proposal and at most three; the rest of the shape is in the router's `## Writing the answer`.
   Done when every proposal names its measure, and nothing was changed on the machine.

4. **Say what the numbers cannot.** A high failure rate on a program that exits on a keypress is a person quitting, not a broken command. A sequence that repeats may be two habits that happen to be adjacent. Ask before proposing.
   Done when each proposal survived one question about whether the number means what it looks like.

## Rules

- No raw history reaches the workspace. Every command line is redacted before it is counted and again before it is written, and the text report prints shapes only. The redaction is wide on purpose: a lost example costs readability, a missed credential costs more.
- Agent sessions are counted, never read. How many sessions a project needed is a measure. What was said in them is not this skill's business.
- A proposal without a measure stays a proposal. The point of the loop is to find out later whether the change helped, and a change nobody can grade is a preference.
- One change per window. Two automations landing in the same fortnight make both unreadable.

## Interpretation

- A negative exit code means the source recorded no result, usually a command still running when the history was written. It is not a failure and is not counted as one.
- Exit code 130 is an interrupt. On an interactive program it is how a person leaves; on a script it is a person giving up. The first is noise, the second is the finding.
- Shapes group by program and up to two words after it, so `npm run dev` and `npm run build` stay apart while their arguments fall away.
- Trivial commands are dropped before counting. A shell where `cd` is the top result says nothing about friction.
- A pair in `friction.repeat-sequence` is the cheapest thing to fix: two commands that always follow each other are one command that does not exist yet.
