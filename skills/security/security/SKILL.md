---
name: security
description: "Entry point for the security skill set: which sub-skill to reach for, the flows (new repository, weekly sweep, a credential is out), the priority ladder, the two gates in front of every fix, and the fixes table that carries a fix and a measure per check id."
disable-model-invocation: true
---

# Security

One loop drives everything: **measure the repository, fix what an attacker reaches first, prove it held, repeat**. A finding earns a log row when it earns a check that can be recomputed.

## Workspace

Every skill reads and writes one private repository, `~/sec` in the examples and recorded during setup: `config.md`, `standards.md`, `cache/` for the catalogues a pass downloads, and one folder per repository under `repos/<slug>/` holding `config.md` (the trust model), `audits/` (one JSON per run), `log/security/` (this theme's actions and their outcomes, one file per ISO week), `rules/` (the rules `jorekai-security:review` wrote), `proposals/` and `reports/security/`.

A repository is this theme's business when its `config.md` says `role: code`. No workspace yet, or no such repository: `jorekai-security:setup` first.

The workspace is separate from the one `jorekai-dx` and `jorekai-ops` share, because a repository is not a machine: it is worked on from several machines and outlives all of them. Reasons: `decisions/0025`.

## Flows

**New repository**, in this order. The order is the point, not a preference:

1. `jorekai-security:setup`: detect the ecosystem, write the trust model, record the secret store and the way a credential is rotated, choose the profile.
2. `jorekai-security:secrets`: what is already out. Nothing else is worth doing while a live credential sits in a history other people can read.
3. `jorekai-security:pipeline`: what the forge runs with this repository's own rights.
4. `jorekai-security:deps`: what is known-bad in the tree that gets installed.
5. `jorekai-security:review`: where attacker-controlled input reaches a dangerous sink.

**Weekly**, ten minutes: `jorekai-security:and-now` names the stage, the open items, and the next dated event. Each item that gets done leaves a log row with a measure and a verify date. A row whose verify date has passed goes to `jorekai-security:grade`, which recomputes the measure and writes the verdict, so the loop closes instead of collecting dates.

**Monthly**: `jorekai-security:report` writes what the month cost and what it gave back into `reports/security/YYYY-MM.md`, from the audits and the log alone, and names the three rows the next month starts with.

**A pull request is open**: `jorekai-security:review` against the diff. What it accepts becomes a rule, so the next pass measures it without asking the model again.

**A credential is out**: `jorekai-security:secrets`, then gate 1 in [references/risk-classes.md](references/risk-classes.md). The first action is the rotation, never the commit that removes the line.

**Lost the thread**: `jorekai-security:and-now`. It reads files, never the network, so it answers in a second and costs nothing.

## Sub-skills

| Need | Skill | Invoked by |
|---|---|---|
| Where does this repository stand, what comes next? | `jorekai-security:and-now` | you |
| Take a repository into the workspace, with a trust model and a profile | `jorekai-security:setup` | you |
| Is a credential in the files or in the history, and was it rotated? | `jorekai-security:secrets` | agent or you |
| What can take over the build, and what does the build token allow? | `jorekai-security:pipeline` | agent or you |
| Which installed dependency is known-bad, and which one is known to be exploited? | `jorekai-security:deps` | agent or you |
| Where does attacker-controlled input reach a dangerous sink? | `jorekai-security:review` | agent or you |
| Did the fix hold? Settle the rows past their verify date | `jorekai-security:grade` | agent or you |
| What did the month do to this repository? | `jorekai-security:report` | you |

## What this theme does not do

- It does not exploit anything and runs nothing against a live system. What a host answers on is `jorekai-ops:exposure`.
- It never tests a found credential against the provider's API. A key sent somewhere to see whether it still works has been sent.
- It reads a repository. Licences, an artefact inventory, and anything about hiding from a defender are outside it.
- The forge's own advisory list stays with `jorekai-dx:github` as `alert.open`, which says that something waits on a person. This theme computes the answer from the lock files instead, so the two never contradict each other by measuring the same thing twice.
- A credential file found by its name stays with `jorekai-dx:repos` as `repo.secret-exposed`, which never reads a file. `cred.*` reads contents and history, which is the half that check leaves open.

## Priority ladder

Each rung depends on the one before it. A finding on a lower rung waits.

1. **What is out is out.** `cred.history`, `cred.tracked`, `cred.unrotated`. A credential that reached a shared history cannot be taken back by an edit, so this rung is also a precondition: the fix is a rotation, and everything else waits for it.
2. **The build can be taken over.** `build.untrusted-checkout`, `build.script-injection`, `build.token-broad`, `build.action-unpinned`. Whoever runs code in the pipeline also owns the fix that is about to be pushed through it.
3. **A known-exploited hole is installed here.** `dep.known-exploited`, `dep.fix-available`. Exploitation is observed, and a version that closes it exists, so the fix is one line and the cost of waiting is somebody else's decision.
4. **Input reaches a dangerous sink.** `vuln.injection`, `vuln.authz`, `vuln.deserialize`, `vuln.ssrf`, `vuln.crypto`.
5. **Known-bad, not yet reachable.** `dep.vulnerable`, `vuln.exposure`.
6. **Tidiness.** `dep.unresolved`.

## Reading a report

Every measuring script prints the same shape without `--json`, so one reading order works everywhere:

1. The first two lines say what was measured and what it was measured against, so a number can be judged without opening `standards.md`.
2. The counting line says how many findings need a decision, how many notes carry no action, and how many checks passed.
3. Each finding names its level, its check id, and what it costs now in one unit. Findings come in level order, and the costliest first inside a level.
4. Under a finding stand at most five targets with their own share of the cost. The rest is in the JSON, which is what the workspace keeps.
5. The last line says what to do next, and every id is looked up in [references/fixes.md](references/fixes.md) for the fix, the risk class, and the gate.

The console report is for the decision, the JSON is for the record. Only the JSON is written to `audits/`.

A note without a measure is not a pass. A scanner that is not installed, a lock file nothing resolved, and a forge this theme does not read all carry no number on purpose, because a zero there would settle a log row with a figure nobody took.

A terminal gets the same report in colour: the level word, the verdict, the check id and the measure carry the colour their role already has. Nothing is coloured that a word does not already say, and a pipe, a redirect and a subagent see plain text. Reason: `decisions/0022`.

## Writing the answer

The report is for the terminal; the answer is for the person, and it has one shape everywhere in this theme:

1. One line first: what ran, what it was measured against, and the path of the JSON. The reader can open it, so nothing inside it is repeated in prose.
2. One table, in ladder order, at most five rows, one row per check id and never one per target. What the table drops is one sentence under it, never a second table.
3. Every cost is one number and one unit, copied from the finding's `measure` block. A cost written as prose cannot be graded later.
4. A finding is named by its location and its path from an entry point, never by a value. A secret, a token, and a personal detail are quoted as their position and their shape.
5. One line last: the single next action, and the gate it waits on when it touches a credential or a control.

The columns, per skill:

- `jorekai-security:deps`, `jorekai-security:secrets`, `jorekai-security:pipeline`, `jorekai-security:review`: `check id | cost | targets | fix | class`
- `jorekai-security:grade`: `row | then | now | verdict | next`
- `jorekai-security:and-now`: no table. The script's stage, at most three open items in ladder order, the next verify date.
- `jorekai-security:setup`: no table. The trust model it wrote, the scanners it found, and the profile that was chosen.
- `jorekai-security:report`: no table. The path of the report, its headline, and the four counts.

A skill whose answer is a file names the file and writes no table. Reason: `decisions/0023`.

## Principles

- A finding earns a log row when it earns a check. What a model found and no script recomputes is a proposal, not an action (`decisions/0026`).
- Findings are facts, fixes are decisions. A script reports what is, a person decides what happens.
- Attacker-controlled or not is read from the trust model, not guessed per run. An entry point nobody wrote down turns a pass into a list of patterns.
- Every measure counts a cost, as one number and one unit, so lower is better and zero means the finding is gone. An age is never a measure; what is past a floor is counted instead.
- A value is never printed, never logged, and never sent anywhere. A finding names a path, a line, and a shape.
- An accepted risk is data, not judgment. It is written once with its reason and its date, and it stops being a finding.
- The same finding gets one row, not one row per affected path.
- A measurement that needs the network says so, and works from the cache when it is not there.

## Reference

- The three risk classes and the two gates above them: [references/risk-classes.md](references/risk-classes.md)
- What every check id means, its fix, its class, and its measure: [references/fixes.md](references/fixes.md)
- Tools, what each is for, and what happens when it is missing: [references/tools.md](references/tools.md)
- Documented facts with source and check date, and the list of heuristics: [references/sources.md](references/sources.md)
