# Machines workspace

Working files for the machines this person keeps: the ones worked on and the ones that serve. One folder per machine under `machines/`, shared by every theme that measures a machine. Agents read `config.md`, `standards.md`, and `machines/<hostname>/config.md` before running any `jorekai-ops:*` or `jorekai-dx:*` skill. Unsure where things stand: `jorekai-ops:and-now` for a host that serves, `jorekai-dx:and-now` for a machine worked on.

This repository is private. It names project paths, hostnames, ssh targets, and command history, none of which belong in a public place.

## Machines

<!-- machines:start -->
<!-- machines:end -->

## Layout

- `config.md`: what holds across machines. One section per theme, because both read this file.
- `standards.md`: what good looks like here. Every check measures a machine against this file, so a blank value turns its check off instead of guessing.
- `machines/<hostname>/config.md`: what that machine is, where its things live, and the limits that override the standard. `role: server` makes it the ops theme's business.
- `machines/<hostname>/audits/YYYY-MM-DD-<tool>.json`: one file per run of a measuring skill. Log rows point here instead of repeating paths.
- `machines/<hostname>/log/<theme>/YYYY-Www.md`: one file per ISO week, one folder per theme. The only place actions and their outcomes are recorded.
- `machines/<hostname>/proposals/<slug>.md`: something worth doing that has no measure yet, so it is not an action.

One log folder per theme, not one file per machine: two themes append rows to the same machine, and a flat folder would put two writers into one file and leave each reader deciding whether an unknown check id is its own gap or the other theme's business.

## Log format

File `machines/<hostname>/log/ops/YYYY-Www.md`; `scaffold.py --log` (in the `jorekai-ops:setup` skill) creates the current week's file and prints the next free id. Ids are `YYYY-Www-nn`.

```markdown
# 2026-W36 (2026-08-31 to 2026-09-06)

Host: example-host

## Outcomes of earlier actions

| id | Check | Target | Applied | Then | Now | Verdict |
|---|---|---|---|---|---|---|
| 2026-W34-01 | timer.disabled | example.timer | 2026-08-20 | 2 count | 0 count | won |

## Actions

| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| 2026-W36-01 | ssh.root-login | sshd | close direct root login, both accounts proved first | ask | 1 count | applied | 2026-09-02 | 2026-09-16 | |
```

Status, in order: `todo`, then `applied` (date set), then `verify` (verify-after date reached, outcome pending), then one of `won`, `no-change`, `returned`, `dropped`. `returned` means the finding came back within the verify window, which is the interesting case: the fix treated a symptom.

`Then` holds the measure at the moment the action was applied, as one number and one unit from `bytes`, `count`, `percent`, `seconds`. Every measure counts a cost, so lower is better and zero means the finding is gone. A row without a measure the same script can recompute belongs in `proposals/`, not here.

A row whose check id belongs to this theme but whose script has not shipped yet keeps its applied date and has no verify date, with the release that will measure it in Outcome. A date nobody can measure at is a verdict nobody can give.

A commit that carries out an action in a project repository ends with the trailer `Ops-Log: <id>`; `scaffold.py --log` prints the line to paste. `git log --grep="Ops-Log: 2026-W36-01"` then shows the change behind that row.

`scaffold.py --due` lists the rows whose verify-after date has passed.
