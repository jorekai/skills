# Changelog

One entry per `jorekai-dx` version. The version at the top equals `version` in `skills/dx/.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

## 1.1.0 (2026-09-05)

- Fixed: `status.py` reads the newest audit per kind instead of the newest file overall. A `disk.low` failure went silent the moment a repository pass ran after it, so `jorekai-dx:and-now` answered "nothing open" on a machine with two gigabytes free. Failing ids from every kind are now ranked by the router's ladder, and each one names the skill that owns it.
- Fixed: `and-now` reports when no repository pass exists, because every destructive action depends on one, and when an audit is older than `audit_max_age_days` rather than a constant in the script.
- Added: `scaffold.py --flags` prints the arguments each measuring script takes, built from `config.md`, `standards.md`, and the machine's config. A step that retypes a retention gets it wrong or leaves it out, and then the script measures against its own defaults instead of the standard.
- Added: `repos.py` takes `--stash-days` and `--expect-email`, and reports `git.identity` for a repository that would commit under another address. `machine.py` takes `--runtime` so a machine's recorded runtime is used instead of a guess.
- Changed: thirteen keys in the templates were read by nothing. `git_email`, `scan_max_depth`, `stash_stale_days`, `slow_command_seconds`, `container_runtime`, `shell_history_db`, and `extra_history` now reach a script through `--flags`; `ignore_file`, `pointer_file`, `readme`, `ci`, `remote`, and `default_branch` are named by the step that reads them; `name`, `shell`, and a duplicated `pointer_file` are gone, and `audit_retention_months` became `audit_max_age_days`, which something reads.
- Changed: `references/fixes.md` drops five container ids no script produced. Their guidance moved into the `container.reclaimable` row, where the removal actually happens, and `friction.agent-sessions` gained the row it was missing.
- Changed: `scripts/check.sh` fails when a check id a script emits has no row in its theme's fixes table.

## 1.0.0 (2026-09-05)

- Added: `jorekai-dx:friction`, user-invoked, reduces months of command history to shapes that repeat, pairs run one after the other, shapes that fail, retry loops, and the slowest totals. `friction.py` redacts every line before it is counted and again before it is written, prints no command line at all, and counts agent sessions without opening one.
- Added: `jorekai-dx:github`, model-invoked, for what waits on the forge: failed runs on default branches, pull requests past the retention, reviews requested from the account, open alerts, unprotected branches. One subagent per class, each returning one table under a word limit, so no repository page reaches the caller's context.
- Added: `jorekai-dx:agent-config`, model-invoked, compares each project's pointer file, permissions, hooks, and servers against `standards.md`.
- Added: `references/fixes.md` covers all 36 check ids across the five sources, each with its fix, class, and measure.
- Changed: the priority ladder has six rungs and puts what other people wait on above what only costs you.

## 0.2.0 (2026-09-05)

- Added: `jorekai-dx:repos`, model-invoked, reports every local repository in one pass: uncommitted changes, commits reachable from no remote, branches with no upstream, a detached HEAD, stashes past the retention, merged branches, lock files older than their manifest, and missing README, ignore file, or checks. `repos.py` runs git locally only, never fetches, and emits one item per check id with the full list under `data`.
- Added: `jorekai-dx:machine`, model-invoked, measures free space against the floor, cache directories, rebuildable dependency and build trees under the project roots, available memory, and the storage a container runtime reports as reclaimable. `machine.py` removes nothing.
- Added: `references/fixes.md` gives every check id its meaning, its fix, its risk class, and the measure the same script recomputes at the verify date. `references/tools.md` names what the skills reach for and what they do without.
- Added: `references/sources.md` carries five rows checked against the primary source: what a container prune removes with and without its flags, what the reclaimable column prints, what `git branch --merged` lists, and that a dropped stash may be unrecoverable.

## 0.1.0 (2026-09-05)

- Added: the `dx` theme and the plugin `jorekai-dx`. Router, `jorekai-dx:setup` with `scaffold.py`, and `jorekai-dx:and-now` with `status.py`. The workspace lives outside every project repository because the work is machine wide.
- Added: `references/risk-classes.md`. Three classes and one gate above them decide the flow of a destructive action, so no step judges in the moment whether a removal is safe.
- Added: `decisions/0011`, `decisions/0012`, and `decisions/0013` record the workspace location, the three risk classes, and one version per plugin.
- Changed: `scripts/link.sh` names a Codex link `<theme>-<skill>`. Both themes carry a `setup` and an `and-now`, and the bare name let the second link overwrite the first without saying so. Existing links are replaced by rerunning the script.
- Changed: `scripts/check.sh` compares every plugin manifest to the changelog beside it, and rejects an absolute home path in a tracked file.
