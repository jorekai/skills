# Security workspace

One private repository for what is measured about code repositories. Nothing here is public: a
finding names a path, a line and a shape, and the repositories it describes are not always yours
alone. The skills that read and write it are `jorekai-security:*`.

## Layout

- `config.md`: what holds across repositories.
- `standards.md`: what good looks like here. Every check measures a repository against this file, so a blank value turns its check off instead of guessing.
- `cache/`: the catalogues a pass downloads, each with the date it was fetched, so a pass runs without the network and says how old its answer is.
- `repos/<slug>/config.md`: what that repository is, where its checkout lives, and the trust model every pass reads. `role: code` makes it this theme's business.
- `repos/<slug>/audits/YYYY-MM-DD-<tool>.json`: one file per run of a measuring skill. Log rows point here instead of repeating paths.
- `repos/<slug>/log/security/YYYY-Www.md`: one file per ISO week. The only place actions and their outcomes are recorded.
- `repos/<slug>/rules/<check-id>-<n>.json`: one file per finding `jorekai-security:review` accepted, so the same measure is recomputed later without asking the model again.
- `repos/<slug>/reports/security/YYYY-MM.md`: one file per month, written by `jorekai-security:report` from the audits and the log. Nothing is measured for it.
- `repos/<slug>/proposals/<slug>.md`: something worth doing that has no measure yet, so it is not an action.

One folder per repository, and the log folder carries the theme name, so a second theme could
write beside this one without two writers landing in one file.

## Log format

File `repos/<slug>/log/security/YYYY-Www.md`; `scaffold.py --log` (in the `jorekai-security:setup`
skill) creates the current week's file and prints the next free id. Ids are `YYYY-Www-nn`.

```markdown
# 2026-W37 (2026-09-07 to 2026-09-13)

Repository: example-repo

## Outcomes of earlier actions

| id | Check | Target | Applied | Then | Now | Verdict |
|---|---|---|---|---|---|---|
| 2026-W35-01 | build.action-unpinned | .github/workflows/build.yml | 2026-08-27 | 4 count | 0 count | won |

## Actions

| id | Check | Target | Action | Class | Then | Status | Applied | Verify after | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| 2026-W37-01 | cred.tracked | config/settings.py | rotate the key at the provider, then remove the line | ask | 1 count | applied | 2026-09-09 | 2026-09-23 | |
```

Status, in order: `todo`, then `applied` (date set), then `verify` (verify-after date reached,
outcome pending), then one of `won`, `no-change`, `returned`, `dropped`. `returned` means the
finding came back within the verify window, which is the interesting case: the fix treated a
symptom.

`Then` holds the measure at the moment the action was applied, as one number and one unit from
`bytes`, `count`, `percent`, `seconds`. Every measure counts a cost, so lower is better and zero
means the finding is gone. A row without a measure the same script can recompute belongs in
`proposals/`, not here.

A row about a credential is written for the rotation, not for the commit that removed the line.
The value is never written down here, only its fingerprint, its provider and where it was found.

A commit that carries out an action in a project repository ends with the trailer
`Security-Log: <id>`; `scaffold.py --log` prints the line to paste.
`git log --grep="Security-Log: 2026-W37-01"` then shows the change behind that row.

`scaffold.py --due` lists the rows whose verify-after date has passed.
