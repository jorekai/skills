# Changelog

One entry per `jorekai-dx` version. The version at the top equals `version` in `skills/dx/.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

## 2.2.0 (2026-09-07)

- Added: every script that prints a report colours it, and only when the output is a terminal. `NO_COLOR` turns it off, `FORCE_COLOR` turns it on, and removing every escape leaves the same report, so a pipe, a redirect, a captured test and a subagent read what they always read. A level word, a verdict, a check id and a measure carry the colour their role already has; nothing is coloured for its looks. `decisions/0022`.

## 2.1.1 (2026-09-07)

- Fixed: a count and the verb after it disagreed in seven report lines, so a single finding read "1 week file sit at the old flat log path" and "1 need a person". Where the sentence carried a pronoun for the counted thing it was rewritten instead, because "moves them" and "holds them" have no singular that reads well.

## 2.1.0 (2026-09-07)

- Added: `grade.py --namespaces` prints which tool owns which check id namespace. `scripts/check.sh` compares it to the ids the theme's fixes table names, so a namespace that no tool grades cannot reach the log unnoticed.

## 2.0.0 (2026-09-07)

- Changed: the week log moved from `machines/<host>/log/` to `machines/<host>/log/dx/`. A second theme measures the same host now, and a flat folder put two appenders into one week file and left every reader deciding whether an unknown check id was its own gap or another theme's business. `decisions/0015` records the rule and the id namespaces each theme owns.
- Added: `scaffold.py --migrate-log` moves existing week files down one level. It never overwrites: a week that already exists below is left where it is and both files are named, because two files of the same week are two records.
- Added: `scaffold.py --check` and `jorekai-dx:and-now` report a week file still sitting at the old flat path. Such a file is read by nobody, so it has to be named rather than silently skipped.

## 1.3.0 (2026-09-05)

- Added: `repo.secret-exposed`, a `FAIL` on the first rung of the ladder: an untracked file whose name says credential and that no ignore rule covers, which is the single state where one `git add` writes a credential into a history. `repo.no-ignore` never caught it, because an ignore file with one line passes that check. It reads names and coverage, never contents, and an ignored or already committed file is a different problem with a different fix.
- Added: `and-now` reports log rows whose check id no tool measures. Such a row is refused by `jorekai-dx:grade` at its verify date, weeks after anyone could still say what its number meant. The ladder in `status.py` now names every id the tools emit, so it answers both where an id ranks and whether it exists.
- Changed: every measuring script prints one console shape: two header lines saying what was measured and what it was measured against, one counting line, then each finding with its check id, its cost in one unit, and at most five targets with their own share. Findings run in level order and by cost inside a level, so the report is already in the order the work should happen. The old report opened with four level totals and left the reader to rank the ids by hand.
- Changed: passing checks are listed once by id instead of being dropped, and a check whose source is missing on this machine is printed as a note. A check that leaves no trace reads the same as a check that never ran.
- Changed: every report ends on a next step: the largest cost first for `machine`, unsaved work first for `repos`, and slow or failing shapes before frequent ones for `friction`. `grade` names `--write` when there are verdicts to keep.
- Changed: counts carry the word they count. A row under `git.dirty` says "25 changed paths", one under `friction.slow-command` says "3 hours over 420 runs", and a home path is written as `~`. A bare number left the reader guessing what it measured.
- Added: `skills/dx/dx/SKILL.md` documents the report shape in one place, so a new script has a contract to follow and a reader has one reading order.

## 1.2.0 (2026-09-05)

- Added: `jorekai-dx:grade`, model-invoked, settles every log row past its verify date. `grade.py` reads the newest audit of the tool that found the check, recomputes the measure for that row's target, and proposes `won`, `no-change`, or `returned`; `--write` appends the outcome row and closes the action row. A row it cannot grade says why: no audit of that tool, an audit older than the action, a check id the pass did not produce, a measure the row never carried.
- Added: every finding carries `measure` beside `id`, `level`, `message`, and `data`: a `value`, its `unit`, and `by` with the same measure per target. A passing check measures zero, which is what turns "the finding is gone" into a fact instead of an absence.
- Added: `scaffold.py --append-row` writes one action row from named fields, computes the id and the verify date, and refuses a check id, a risk class, or a measure the loop cannot use. A row written by hand with the wrong number of columns was skipped in silence by every reader.
- Added: `repos.py`, `machine.py`, and `friction.py` answer `--measures` with the unit of every check id they emit, and `scripts/check.sh` fails when that unit is missing from the fixes table.
- Changed: a measure counts a cost, so lower is better and zero means the check no longer fires (`decisions/0014`). `disk.low` measures the bytes missing from the floor instead of the free bytes, `mem.pressure` the percentage points missing from it, and `git.stash-old` counts stash entries past the retention instead of the age of the oldest, because an age drifts on its own and can never be graded.
- Added: `git.unpushed` names the branches that hold the commits and how many each holds, read from one call that attributes every commit to a source ref. A repository can be level with its upstream and still hold months of work on a branch beside it, and the count alone sent the reader looking for it by hand.
- Changed: `references/fixes.md` and the `repos` interpretation say to fetch before pushing. The count is read from the remote refs on this disk, so a push can be rejected by a remote that moved, which is what happened on the first machine this ran against.
- Changed: `references/fixes.md` names the unit of every check id, and the steps that write a log row in `repos`, `machine`, `github`, and `agent-config` call the scaffold instead of formatting a table row.

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
