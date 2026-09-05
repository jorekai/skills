# Changelog

One entry per `jorekai-dx` version. The version at the top equals `version` in `skills/dx/.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

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
