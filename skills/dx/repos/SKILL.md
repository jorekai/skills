---
name: repos
description: State of every local repository on this machine in one pass via scripts/repos.py: uncommitted changes, commits that exist on no remote, branches with no upstream, a detached HEAD, old stashes, merged branches past the retention, lock files older than their manifest, and missing README, ignore file, or checks. Use when asked which repositories hold unsaved work, before removing anything on the machine, when a repository will not push, or for a sweep across all projects.
---

# Repositories

One pass over every local repository, unsaved work first. Reads `machines/<hostname>/config.md` for the project roots and the projects index, and `standards.md` for the retention and what a repository must carry. No workspace: ask for the roots and skip the log steps.

Every check is local. Nothing fetches, nothing pushes, nothing is written into a repository by this skill.

## Steps

1. **Collect the roots, then run the pass once.** The machine config names `project_roots`, and `projects_index` names a generated list if one exists. Read that list and pass the paths it holds; otherwise pass the roots and let the script walk them.

   ```bash
   python3 scripts/repos.py <root or path> [more ...] --stale-days <retention> --json > <workspace>/machines/<hostname>/audits/YYYY-MM-DD-repos.json
   ```

   The script path is relative to this skill's directory. Every item carries its full list under `data`; the text report shows the first few. Run without `--json` first when you only need to look.
   Done when the JSON holds a `counts` block and the repository count matches what the roots actually contain. A count of zero means the roots are wrong, not that the machine is clean.

2. **Rank the findings, do not list them.** Order by the priority ladder in the router, not by how many repositories a check touched: work at risk first, then what blocks a push, then hygiene. Look each id up in [../dx/references/fixes.md](../dx/references/fixes.md) for the fix, the class, and the measure.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Act by class, never by judgment.** `safe` runs and reports. `confirm` shows the exact list and the total first, asks once, then runs. `ask` prints the command and the reason and stops. A repository that holds uncommitted or unpushed work is `ask` for every check, whatever the check's own class says.
   Done when every action taken has a class recorded, and every refused one has a reason.

4. **Log what was done, not what was found.** One row per check id in the current week's log file, with the measure from the JSON as `Then` and a verify date from `verify_window_days`. A finding nobody acted on is not a row.
   Done when each row names the check id, the class, and a measure the same script recomputes.

## Interpretation

- `git.unpushed` counts commits reachable from no remote, so a branch with no upstream still counts. The question the check asks is whether the work survives losing this disk.
- A repository with no remote reports `repo.no-remote` and no unpushed count. Counting every commit there would drown the repositories that do have a remote and are behind it.
- `git.stale-branch` uses reachability from the default branch, so a branch listed there is contained in it and deleting the branch loses no commit. Rebased or squashed work is not reachable and is not listed, which is the safe direction to be wrong in.
- `repo.lock-drift` compares modification times. It is a fast test, not a proof: touching a manifest without changing a dependency produces the same signal.
- A first pass on a machine that has never been swept reports a lot. Fix the `FAIL` ids, record the rest in `standards.md` as accepted, and the second pass is short.
