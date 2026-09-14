# Stack workspace

One private repository for what is measured about repositories this theme generated or adopted. Nothing here is public: a finding names a path, a line and a suppression, and the repositories it describes are not always yours alone. The skills that read and write it are `jorekai-stack:*`.

The declaration a repository carries, `stack.yaml`, lives in that repository, because the project's own tooling reads it. This workspace keeps a snapshot of it and every finding about it (`decisions/0035`).

## Layout

- `config.md`: what holds across repositories.
- `standards.md`: the profile the next declaration starts from, and the windows every log row obeys.
- `repos/<slug>/config.md`: what that repository is, where its checkout lives, and whether it exists yet. `role: stack` makes it this theme's business.
- `repos/<slug>/stack.yaml`: the snapshot of the repository's declaration, written by `scaffold.py --snapshot`. The passes note when the repository's file has moved away from it.
- `repos/<slug>/audits/YYYY-MM-DD-<tool>.json`: one file per run of `jorekai-stack:guards` or `jorekai-stack:drift`. Log rows point here instead of repeating paths.
- `repos/<slug>/log/stack/YYYY-Www.md`: one file per ISO week. The only place actions and their outcomes are recorded.
- `repos/<slug>/reports/stack/YYYY-MM.md`: one file per month, written by `jorekai-stack:report` from the audits and the log. Nothing is measured for it.
- `repos/<slug>/proposals/<slug>.md`: something worth doing that has no measure yet, so it is not an action.

One folder per repository, and the log folder carries the theme name, so a second theme could write beside this one without two writers landing in one file.

## Log format

File `repos/<slug>/log/stack/YYYY-Www.md`; `scaffold.py --log` (in the `jorekai-stack:setup` skill) creates the current week's file and prints the next free id. Ids are `YYYY-Www-nn`.

```markdown
# 2026-W37 (2026-09-07 to 2026-09-13)

Repository: example-app

## Outcomes of earlier actions

| id | Check | Target | Applied | Then | Now | Verdict |
|---|---|---|---|---|---|---|
| 2026-W35-01 | escape.type | packages/ports/src/db/pool.adapter.ts:84 | 2026-08-27 | 1 count | 0 count | won |

## Actions

| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| 2026-W37-01 | escape.unenforced | gate | make the gate a required check on the default branch, record the date | ask | 1 count | applied | 2026-09-09 | 2026-09-23 | |
```

Status, in order: `todo`, then `applied` (date set), then `verify` (verify-after date reached, outcome pending), then one of `won`, `no-change`, `returned`, `dropped`. `returned` means the finding came back within the verify window, which is the interesting case: the fix treated a symptom.

`Then` holds the measure at the moment the action was applied, as one number and one unit from `bytes`, `count`, `percent`, `seconds`. Every measure counts a cost, so lower is better and zero means the finding is gone. A row without a measure the same script can recompute belongs in `proposals/`, not here.

A commit that carries out an action in a project repository ends with the trailer `Stack-Log: <id>`; `scaffold.py --log` prints the line to paste. `git log --grep="Stack-Log: 2026-W37-01"` then shows the change behind that row.

`scaffold.py --due` lists the rows whose verify-after date has passed.
