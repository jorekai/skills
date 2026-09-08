# Developer experience workspace

Working files for the machines this person works on. One folder per machine under `machines/`. Agents read `config.md`, `standards.md`, and `machines/<hostname>/config.md` before running any `jorekai-dx:*` skill. Unsure where things stand: `jorekai-dx:and-now` reads this folder and names the stage and the next step.

This repository is private. It names project paths, hostnames, and command history, none of which belong in a public place.

## Machines

<!-- machines:start -->
| Machine | Folder | Config |
|---|---|---|
<!-- machines:end -->

## Layout

- `config.md`: what holds across machines (identity, defaults a new machine inherits). Written by `jorekai-dx:setup`.
- `standards.md`: what good looks like here. Every check measures the machine against this file, so a blank value turns its check off instead of guessing.
- `machines/<hostname>/config.md`: where projects and history live on that machine, and the limits that override the standard.
- `machines/<hostname>/audits/YYYY-MM-DD-<kind>.json`: one file per run of a measuring skill. Log rows point here instead of repeating paths.
- `machines/<hostname>/log/<theme>/YYYY-Www.md`: one file per ISO week, one folder per theme. The only place actions and their outcomes are recorded.
- `machines/<hostname>/reports/<theme>/YYYY-MM.md`: one file per month, written by `jorekai-dx:report` from the audits and the log. Nothing is measured for it.
- `machines/<hostname>/proposals/<slug>.md`: something worth doing that has no measure yet, so it is not an action.

## Log format

File `machines/<hostname>/log/dx/YYYY-Www.md`; `scaffold.py --log` (in the `jorekai-dx:setup` skill) creates the current week's file and prints the next free id. Ids are `YYYY-Www-nn`.

```markdown
# 2026-W36 (2026-08-31 to 2026-09-06)

Machine: example-machine

## Outcomes of earlier actions

| id | Check | Target | Applied | Then | Now | Verdict |
|---|---|---|---|---|---|---|
| 2026-W34-01 | disk.cache | ~/Library/Caches | 2026-08-20 | 41 GB free | 63 GB free | won |

## Actions

| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| 2026-W36-01 | git.unpushed | example-app | push the four commits on the feature branch | ask | 4 commits ahead | applied | 2026-09-02 | 2026-09-16 | |
```

Status, in order: `todo`, then `applied` (date set), then `verify` (verify-after date reached, outcome pending), then one of `won`, `no-change`, `returned`, `dropped`. A `won` row names the number that moved in Outcome. `returned` means the finding came back within the verify window, which is the interesting case: the fix treated a symptom. `no-change` after two verify windows becomes `dropped` with the reason in Outcome.

`Check` is the check id that found the target, so the row joins to the audit JSON and to the fix that was chosen. `Class` is the risk class the action ran under. `Then` holds the measure at the moment the action was applied, and `Now` holds the same measure recomputed at the verify date. A row without a measure the same script can recompute belongs in `proposals/`, not here.

A commit that carries out an action in a project repository ends with the trailer `DX-Log: <id>`; `scaffold.py --log` prints the line to paste. `git log --grep="DX-Log: 2026-W36-01"` then shows the change behind that row. Without the trailer the diff and the reason live in different places and neither finds the other.

Every skill that changes the machine appends a row to the current week's file. `scaffold.py --due` lists the rows whose verify-after date has passed.
