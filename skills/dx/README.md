# jorekai-dx

One machine to work on: the workspace, the weekly sweep, and what to do next. Part of the [jorekai skills](../../README.md) collection.

```bash
claude plugin install jorekai-dx@jorekai
```

Start with `/jorekai-dx:setup` on a new machine, or with `/jorekai-dx:and-now` on a machine that has a workspace.

## The loop

Setup once per machine, then a short weekly pass for good. Monthly, two further passes ask what the command history and the forge say. The workspace is a private repository of its own, because the subject is the machine: a finding like "four repositories hold unpushed commits" belongs to none of the four.

```mermaid
flowchart TD
    subgraph E["Setup, once per machine"]
        S1["/jorekai-dx:setup<br/>private workspace repository: config.md, standards.md,<br/>machines/&lt;hostname&gt;/ with audits, log, proposals"]
        S2["jorekai-dx:repos<br/>credentials one git add from a history,<br/>work that exists on this disk only"]
        S3["jorekai-dx:machine<br/>free space against the floor, caches,<br/>rebuildable trees, memory, container storage"]
        S4["jorekai-dx:agent-config<br/>what a session finds when it opens each project"]
        S1 --> S2 --> S3 --> S4
    end

    subgraph W["Weekly, ten minutes"]
        W1["jorekai-dx:and-now<br/>stage, at most three open items, the next dated event"]
        W2["Rank by the priority ladder<br/>1. nothing is lost and nothing leaks<br/>2. the machine runs<br/>3. someone else is waiting"]
        W3["Act by risk class<br/>safe runs, confirm asks once,<br/>ask prints the command and stops"]
        W4["scaffold.py --append-row<br/>check id, class, one measure, verify date"]
        W5["jorekai-dx:grade<br/>won, no-change, or returned, written back into the log"]
        W1 --> W2 --> W3 --> W4
        W4 -. "verify date reached" .-> W5
        W5 -- "returned: the fix treated a symptom" --> W2
        W5 -. "next week" .-> W1
    end

    subgraph M["Monthly"]
        M1["jorekai-dx:friction<br/>shapes, pairs, failures, retries, slow totals;<br/>proposals, never a change to the machine"]
        M2["jorekai-dx:github<br/>red default branches, pull requests past the retention,<br/>reviews requested from the account, open alerts"]
        M3["jorekai-dx:report<br/>what the month cost and what it gave back,<br/>reports/dx/YYYY-MM.md"]
        M1 --> M3
    end

    subgraph H["Something hurts"]
        H1["The disk is full, or the machine crawls<br/>jorekai-dx:machine for the numbers,<br/>jorekai-dx:repos before removing anything"]
    end

    S4 --> W1
    W1 -- "no audit, or one that aged out" --> S2
    W1 -. "once a month" .-> M1
    M1 --> W4
    M2 --> W3
    H1 --> W3
```

## Skills

| Skill | Invoked by | What it does |
|---|---|---|
| [`jorekai-dx:dx`](dx/SKILL.md) | user | Router: workspace, flows, the priority ladder, the answer format per skill, the risk classes |
| [`jorekai-dx:setup`](setup/SKILL.md) | user | Creates the private workspace and the machine folder; appends a log row, lists what is due |
| [`jorekai-dx:and-now`](and-now/SKILL.md) | user | Stage, due rows, and open findings from the workspace files, no machine access and no network |
| [`jorekai-dx:repos`](repos/SKILL.md) | model | Every local repository in one pass: credential files, unpushed work, lock drift, missing checks |
| [`jorekai-dx:machine`](machine/SKILL.md) | model | Free space against the floor, caches, rebuildable trees, memory; measures only, removes nothing |
| [`jorekai-dx:github`](github/SKILL.md) | model | Failed runs on default branches, stale pull requests, requested reviews, alerts, open branches |
| [`jorekai-dx:agent-config`](agent-config/SKILL.md) | model | What a session finds when it opens each project: pointer file, permissions, hooks, servers |
| [`jorekai-dx:grade`](grade/SKILL.md) | model | One verdict per due log row, recomputed from the newest audit of the tool that found it |
| [`jorekai-dx:friction`](friction/SKILL.md) | user | Command shapes, pairs, failures, retries, slow totals; writes proposals, never a change |
| [`jorekai-dx:report`](report/SKILL.md) | user | The month from the audits and the log, `reports/dx/YYYY-MM.md` |

## Workspace and log

The workspace is a private repository per person, shared with the ops theme: one folder per machine under `machines/<hostname>/`, one log folder per theme (`decisions/0015`).

The log is `machines/<hostname>/log/dx/2026-W36.md`, one file per week. Every row carries a check id, the risk class it ran under, one measure with its unit, and a verify date. A commit that carries an action out ends with `DX-Log: <row id>`. Anything without a measure a script can recompute goes to `proposals/` instead.

## Read next

- [The router](dx/SKILL.md): flows, the priority ladder, and the answer format per skill.
- [Fixes](dx/references/fixes.md): what each check id means, its fix, its class, and its measure.
- [Risk classes](dx/references/risk-classes.md) and [sources](dx/references/sources.md).
- [Changelog](CHANGELOG.md).
