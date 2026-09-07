---
name: ops
description: "Entry point for the server skill set: which sub-skill to reach for, the flows (new host, weekly sweep, something is down), the priority ladder, the two gates in front of every change to access, and the fixes table that carries a fix per control plane."
disable-model-invocation: true
---

# Ops

One loop drives everything: **measure the host, fix what costs the most for the least risk, prove it held, repeat**. Nothing changes access unless a second way in already works.

## Workspace

Every skill reads and writes the same private repository the `jorekai-dx` skills use, `~/dx` in the examples and recorded during setup: `config.md`, `standards.md`, and one folder per host under `machines/<hostname>/` holding `config.md` (role, control plane, access, services), `audits/` (one JSON per run), `log/ops/` (this theme's actions and their outcomes, one file per ISO week), and `proposals/`. One folder per host, one log folder per theme, so both themes can measure the same box without writing into one file. Reasons: `decisions/0015`.

A host is this theme's business when its `config.md` says `role: server`. No workspace yet, or no such host: `jorekai-ops:setup` first.

## Flows

**New host**, in this order. The order is the point, not a preference:

1. `jorekai-ops:setup`: detect the control plane, create the reading account and the changing account, prove both from a fresh connection, choose the profile, list the services.
2. `jorekai-ops:access`: who can reach the host today. Nothing under `ssh.*`, `key.*`, `fw.*`, `sudo.*` or `user.*` may change before this has run and `access.single-path` reads zero.
3. `jorekai-ops:availability`: whether what should run is running, current, and hardened.

**Weekly**, ten minutes: `jorekai-ops:and-now` names the stage, the open items, and the next dated event. Each item that gets done leaves a log row with a measure and a verify date. A row whose verify date has passed goes to `jorekai-ops:grade`, which recomputes the measure and writes the verdict, so the loop closes instead of collecting dates.

**Something is down, or a timer did not fire**: `jorekai-ops:availability` for the numbers, then the fixes table for the fix on this control plane.

**Locked out, or about to be**: read [references/risk-classes.md](references/risk-classes.md) before touching anything. The gate is there because the connection that would repair the mistake is the one the mistake closes.

**Lost the thread**: `jorekai-ops:and-now`. It reads files, never a host, so it answers in a second and costs nothing.

## Sub-skills

| Need | Skill | Invoked by |
|---|---|---|
| Where does this host stand, what comes next? | `jorekai-ops:and-now` | you |
| Take a host into the workspace, with two accounts and a profile | `jorekai-ops:setup` | you |
| Who can reach this host, with which keys and sudo rules? | `jorekai-ops:access` | agent or you |
| Do the services run, fire, and match the commit they should? | `jorekai-ops:availability` | agent or you |
| Did the fix hold? Settle the rows past their verify date | `jorekai-ops:grade` | agent or you |

## Priority ladder

Each rung depends on the one before it. A finding on a lower rung waits.

1. **A way in survives, and no credential leaks.** `access.single-path`, `secret.*`, `key.orphan`, `key.duplicate`, `backup.missing`. A host with one way in cannot be hardened at all, so this rung is also a precondition and not only a priority.
2. **The host is not standing open.** `ssh.root-login`, `ssh.password-auth`, `port.world-open`, `panel.exposed`, `fw.disabled`, `tls.expired`.
3. **Someone is waiting on a service.** `service.down`, `service.failed`, `timer.disabled`, `timer.missed`, `deploy.absent`. The cost of these falls on other people.
4. **What is known-bad but not yet used against you.** `pkg.security`, `boot.pending`, `tls.expiring`, `os.eol`, `intrusion.off`, `key.weak`, `sudo.nopasswd`.
5. **What costs later.** `service.restarts`, `code.behind`, `unit.unhardened`, `pkg.pending`, `backup.untested`.
6. **Tidiness.** `port.unexpected`, `fw.rule-orphan`, `user.unlisted`, `log.*`, `plane.outdated`.

## Reading a report

Every measuring script prints the same shape without `--json`, so one reading order works everywhere:

1. The first two lines say what was measured and what it was measured against, so a number can be judged without opening `standards.md`.
2. The counting line says how many findings need a decision, how many notes carry no action, and how many checks passed.
3. Each finding names its level, its check id, and what it costs now in one unit. Findings come in level order, and the costliest first inside a level.
4. Under a finding stand at most five targets with their own share of the cost. The rest is in the JSON, which is what the workspace keeps.
5. The last line says what to do next, and every id is looked up in [references/fixes.md](references/fixes.md) for the fix on this host's control plane and the risk class.

The console report is for the decision, the JSON is for the record. Only the JSON is written to `audits/`.

## Principles

- Measuring and changing are different accounts. The pass that measures has no privilege, so it can run as often as anyone likes without widening anything.
- A change is logged only with a measure the same script recomputes later, and `jorekai-ops:grade` is what recomputes it. Without a measure it is a proposal, not an action.
- Every measure counts a cost, as one number and one unit, so lower is better and zero means the finding is gone. A measure that drifts on its own, such as an age, is written as a count of targets past a floor instead.
- The bar is chosen once per host as a profile; the fix offers variants per control plane. The bar does not move when a fix is inconvenient.
- An exception is data, not judgment. A unit option that breaks a service is recorded once with its reason, so it stops being a finding.
- Findings are facts, fixes are decisions. A script reports what is, a person decides what happens.
- The same finding gets one row, not one row per affected path.
- A measurement that needs the network says so. Everything else works from what the host already holds.

## Reference

- The three risk classes and the two gates above them: [references/risk-classes.md](references/risk-classes.md)
- What every check id means, its fix per control plane, its class, and its measure: [references/fixes.md](references/fixes.md)
- Tools and what each is for: [references/tools.md](references/tools.md)
- Documented facts with source and check date, and the list of heuristics: [references/sources.md](references/sources.md)
