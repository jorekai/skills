# jorekai-ops

One host that serves: who can reach it, what runs on it, what may change, and whether the change held. Part of the [jorekai skills](../../README.md) collection.

```bash
claude plugin install jorekai-ops@jorekai
```

Start with `/jorekai-ops:setup` on a new host, or with `/jorekai-ops:and-now` on a host that has a folder in the workspace.

## The loop

Setup once per host, then a short weekly pass. The order inside setup is not a preference: the connection that would repair a mistake in ssh, the firewall, or sudo is the connection the mistake closes, so the second way in exists before anything hardens the first.

```mermaid
flowchart TD
    subgraph E["Setup, once per host"]
        S1["/jorekai-ops:setup<br/>detect the control plane, write role and access"]
        S2["Two accounts<br/>ops-scan reads without privilege,<br/>ops-admin changes with named sudo"]
        S3["Prove both from a fresh connection<br/>this is also what gate 2 requires"]
        S4["Profile and services<br/>the bar in standards.md, the units in config.md"]
        S1 --> S2 --> S3 --> S4
    end

    subgraph W["Weekly, ten minutes"]
        W1["jorekai-ops:and-now<br/>stage, open items in ladder order, next verify date"]
        W2["jorekai-ops:access<br/>root login, passwords, keys, sudo, ways in"]
        W3["jorekai-ops:availability<br/>units, timers, hardening, the commit it runs"]
        W3b["jorekai-ops:recovery<br/>copies, secrets, what the journal keeps"]
        W3c["jorekai-ops:exposure<br/>open ports, the firewall, certificates, watchers"]
        W4["Rank by the priority ladder<br/>1. a way in survives, nothing leaks<br/>2. the host is not standing open<br/>3. someone waits on a service"]
        W5["Gate 2, then act by class<br/>two proved ways in, a backup copy,<br/>a rollback timer that is cancelled last"]
        W6["scaffold.py --append-row<br/>check id, class, one measure, verify date"]
        W7["jorekai-ops:grade<br/>recompute the measure of every due row,<br/>write won, no-change, or returned"]
        W8["jorekai-ops:report<br/>the month from the audits and the log,<br/>reports/ops/YYYY-MM.md"]
        W1 --> W2 --> W3 --> W3b --> W3c --> W4 --> W5 --> W6 --> W7
        W7 -. "next week" .-> W1
        W7 -. "once a month" .-> W8
    end

    S4 --> W2
    W1 -- "no audit, or one that aged out" --> W2
```

## Skills

| Skill | Invoked by | What it does |
|---|---|---|
| [`jorekai-ops:ops`](ops/SKILL.md) | user | Router: workspace, flows, the priority ladder, a fix per control plane, the two gates |
| [`jorekai-ops:setup`](setup/SKILL.md) | user | Creates the host folder and the two accounts; `remote.sh` runs a reading script over ssh |
| [`jorekai-ops:and-now`](and-now/SKILL.md) | user | Stage, due rows, and open items from the workspace files, no host access and no network |
| [`jorekai-ops:access`](access/SKILL.md) | model | Root login, passwords, weak algorithms, keys, sudo, and how many independent ways in exist |
| [`jorekai-ops:availability`](availability/SKILL.md) | model | Units down or failed, timers, required options, and the commit a deploy path runs |
| [`jorekai-ops:exposure`](exposure/SKILL.md) | model | Ports open to anywhere, the firewall, certificates, and the units that watch failed attempts |
| [`jorekai-ops:recovery`](recovery/SKILL.md) | model | Backup copies, secret files, credentials passed to a unit, and the two bounds on the journal |
| [`jorekai-ops:grade`](grade/SKILL.md) | model | One verdict per due log row, recomputed from the newest audit of the tool that found it |
| [`jorekai-ops:report`](report/SKILL.md) | user | The month from the audits and the log, `reports/ops/YYYY-MM.md` |

## Workspace and log

The workspace is the one the dx theme keeps: one folder per host under `machines/<hostname>/`, one log folder per theme (`decisions/0015`).

The log is `machines/<hostname>/log/ops/2026-W36.md`; the trailer is `Ops-Log: <row id>`. Above the three risk classes sit two gates:

1. Nothing destructive runs against a repository holding uncommitted or unpushed work.
2. Every change under `ssh.*`, `key.*`, `fw.*`, `sudo.*`, or `user.*` first proves two independent ways in from fresh connections, writes a backup copy, and arms a rollback timer that is cancelled only after a new connection succeeds (`decisions/0016`).

## Read next

- [The router](ops/SKILL.md): flows, the priority ladder, and a fix per control plane.
- [Fixes](ops/references/fixes.md): what each check id means, its fix, its class, and its measure.
- [Risk classes and the two gates](ops/references/risk-classes.md), and [sources](ops/references/sources.md).
- [Changelog](CHANGELOG.md).
