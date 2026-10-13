---
name: flow
description: "Choose the short command that steers this session: how far the agent may run, where its context comes from, how work ships, and how a person hears back."
disable-model-invocation: true
---

# Flow

Steering a session takes the same few sentences every day: **go on alone, pick up where the last session stopped, ship it when green, tell me when it is done, where do we stand, write me a handoff**. Each sentence here is one command, and each command carries the limits a person would otherwise type again.

This theme measures nothing and keeps no workspace or log (`decisions/0040`). Its subject is the session in front of it, which leaves no state on disk to measure between two runs.

## Two questions, kept apart

Every command answers one of two questions, never both:

1. **Where does the context come from?** This session, or the last one in this project. Only `jorekai-flow:resume` changes it.
2. **How far may the agent run before it stops?** One step, until the goal is met, or through push, merge, and deploy. `jorekai-flow:go` and `jorekai-flow:ship` set it.

A plain "continue" needs no command. The agent understands it, and a command earns its place only through the limits it carries.

## Flows

**Start of the day**: `jorekai-flow:resume` for the state of the last session, then `jorekai-flow:go` once the goal it names is still the goal. `/jorekai-flow:resume go` does both in one line.

**Work is done and checked**: `jorekai-flow:ship`. It is the only command that grants push, merge, and deploy.

**Something takes long**: `jorekai-flow:watch` with the condition, then do other work. The notice arrives when it holds or when the watch gives up.

**Lost the thread mid-session**: `jorekai-flow:status`.

**The session is full or the work moves elsewhere**: `jorekai-flow:handoff`.

## Sub-skills

| Need | Skill | Invoked by |
|---|---|---|
| Work on alone until the goal is met, or for one step | `jorekai-flow:go` | you |
| Continue from the last session of this project | `jorekai-flow:resume` | you |
| Test, commit, push, merge on green, deploy, and prove it | `jorekai-flow:ship` | you |
| Tell me when a condition holds, without me asking again | `jorekai-flow:watch` | you |
| Where does this session stand, and what is running? | `jorekai-flow:status` | you |
| A prompt a new session can start from, on the clipboard | `jorekai-flow:handoff` | you |

## Grants

A command grants what its row names and nothing more. Everything outside the row stops and asks, even inside a long run.

| Command | Granted | Still stops before |
|---|---|---|
| `jorekai-flow:go` | edit, run, test, commit on the current branch | push, merge, deploy, production data, deletion outside the work tree, a message to another person, spending money |
| `jorekai-flow:ship` | the above, plus push, a pull request, merge on green, and the deploy the project documents | force push, merge on red, skipped hooks, a deploy the project does not document, production data |
| `jorekai-flow:watch` | read and check on a schedule, one notice | any change to what it watches |
| `jorekai-flow:resume`, `jorekai-flow:status`, `jorekai-flow:handoff` | read | any change |

A grant lasts until the goal of that command is met or the person says otherwise. It never carries over into the next request.

## Writing the answer

Every command ends the same way, so a person can read the last lines and know what to do:

1. One line first: what ran and whether it reached its goal.
2. At most one table, at most seven rows. What it drops is one sentence under it.
3. One line last: the single next action, and who takes it.

The columns, per skill:

- `jorekai-flow:go`: `step | result | proof`
- `jorekai-flow:resume`: `goal | state | open | next`
- `jorekai-flow:ship`: `stage | result | link`
- `jorekai-flow:watch`: no table. The condition, how it is checked, how often, and when the watch gives up.
- `jorekai-flow:status`: `item | state | next`
- `jorekai-flow:handoff`: no table. The size of the prompt, that it sits on the clipboard, and its first line.

Reason for one shape per theme: `decisions/0023`.

## Rules

- A command never widens itself. A step that needs more than its grant stops, names what it needs, and waits.
- A stop is a question with a recommendation, never an open question. Collect open questions and ask them once, numbered, each with a short reason.
- "Done" means proved: a test, a check, a response, or a reading named in the `proof` column. "Should work" is not a result.

## Reference

- Tools and what each is for: [references/tools.md](references/tools.md)
- Documented facts with source and check date, and the list of heuristics: [references/sources.md](references/sources.md)
