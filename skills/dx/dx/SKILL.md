---
name: dx
description: Entry point for the developer experience skill set: which sub-skill to reach for, the flows (new machine, weekly sweep, something hurts), the priority ladder, and the risk classes that sit in front of every destructive action.
disable-model-invocation: true
---

# Developer experience

One loop drives everything: **measure the friction, fix the thing that costs the most time for the least work, prove it held, repeat**. Nothing is removed that a person would have to rebuild by hand.

## Workspace

Every skill reads and writes one private repository, `~/dx` in the examples and recorded during setup: `config.md` (what holds across machines), `standards.md` (what good looks like here), and one folder per machine under `machines/<hostname>/` holding `config.md` (project roots, history sources, budgets), `audits/` (one JSON per run), `log/` (every change and its outcome, one file per ISO week), and `proposals/` (what nobody has decided yet). Layout and log format: `README.md` in the workspace, written by `jorekai-dx:setup`.

The workspace sits outside every project because its subject is the machine, not one repository. It is private because it names project paths and hostnames. No workspace yet: `jorekai-dx:setup` first.

## Flows

**New machine**: `jorekai-dx:setup` writes the workspace, records the project roots and the history sources, and asks what good looks like. The answers become `standards.md`, which every later check measures against.

**Weekly**, ten minutes: `jorekai-dx:and-now` reads the workspace and names the stage, at most three open items, and the next dated event. Each item that gets done leaves a log row with a verify date.

**Lost the thread**: `jorekai-dx:and-now`. It reads files, never the machine, so it answers in a second and costs nothing.

## Sub-skills

| Need | Skill | Invoked by |
|---|---|---|
| Where do I stand, what comes next? | `jorekai-dx:and-now` | you |
| Set up the workspace for this machine | `jorekai-dx:setup` | you |

## Priority ladder

Each rung depends on the one before it. A finding on a lower rung waits.

1. **No work is at risk.** Uncommitted and unpushed changes outrank everything, including a full disk. Nothing destructive runs against a repository that holds either.
2. **The machine runs.** Free space, memory pressure, and port conflicts stop work outright.
3. **The projects build.** Dependency drift, a toolchain that no longer matches, a red pipeline.
4. **The agent finds its way.** Pointer files, permissions, hooks, and servers that a session depends on.
5. **Friction goes down.** Repeated command sequences, failed commands, and slow waits, ranked by the time they cost.

## Principles

- A change is logged only with a measure the same script can recompute later. Reclaimed bytes, a count of failing checks, a duration. Without one it is a proposal, not an action.
- Every destructive action carries a class, and the class decides the flow, not the judgment of the moment. See [references/risk-classes.md](references/risk-classes.md).
- Findings are facts, fixes are decisions. A script reports what is, a person or the model decides what happens.
- The same finding gets one row, not one row per affected path.
- Raw history never enters the workspace unredacted. Command lines carry tokens, customer names, and customer paths.
- A measurement that needs the network says so. Everything else works offline.

## Reference

- The three risk classes and the gate above them: [references/risk-classes.md](references/risk-classes.md)
- Documented facts with source and check date, and the list of heuristics: [references/sources.md](references/sources.md)
