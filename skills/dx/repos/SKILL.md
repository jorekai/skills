---
name: repos
description: State of every local repository on this machine in one pass via scripts/repos.py: uncommitted changes, commits that exist on no remote, branches with no upstream, a detached HEAD, old stashes, merged branches past the retention, lock files older than their manifest, and missing README, ignore file, or checks. Use when asked which repositories hold unsaved work, before removing anything on the machine, when a repository will not push, or for a sweep across all projects.
---

# Repositories

One pass over every local repository, unsaved work first. Reads `machines/<hostname>/config.md` for the project roots and the projects index, and `standards.md` for the retention and what a repository must carry. No workspace: ask for the roots and skip the log steps.

Every check is local. Nothing fetches, nothing pushes, nothing is written into a repository by this skill.

## Steps

1. **Take the roots and the standards from the workspace, then run the pass once.** `scaffold.py --flags` in the `jorekai-dx:setup` skill prints both: the `paths` line holds `project_roots`, and the `repos` line holds the arguments built from `standards.md` and `config.md`. When the `index` line names a generated project list, read that list and pass the paths it holds instead of the roots.

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags
   python3 scripts/repos.py <paths from that output> <repos flags from that output> --json > <workspace>/machines/<hostname>/audits/YYYY-MM-DD-repos.json
   ```

   The script paths are relative to this skill's directory. A flag the workspace left blank is absent on purpose: that check does not run on this machine. Every item carries its full list under `data`; the text report shows the first few. Run without `--json` first when you only need to look.
   Done when the JSON holds a `counts` block and the repository count matches what the roots actually contain. A count of zero means the roots are wrong, not that the machine is clean.

2. **Rank the findings, do not list them.** Order by the priority ladder in the router, not by how many repositories a check touched: work at risk first, then what blocks a push, then hygiene. Look each id up in [../dx/references/fixes.md](../dx/references/fixes.md) for the fix, the class, and the measure.

   The script reports what a repository has; `standards.md` decides what counts. `repo.no-readme`, `repo.no-ignore`, `repo.no-ci`, and `repo.no-remote` are findings only where `readme`, `ignore_file`, `ci`, and `remote` ask for them, and `git.no-upstream` is read against `default_branch`. A blank standard means the script's line is information, not a gap.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Act by class, never by judgment.** `safe` runs and reports. `confirm` shows the exact list and the total first, asks once, then runs. `ask` prints the command and the reason and stops. A repository that holds uncommitted or unpushed work is `ask` for every check, whatever the check's own class says.
   Done when every action taken has a class recorded, and every refused one has a reason.

4. **Log what was done, not what was found.** One row per check id, written by the scaffold so no column is miscounted and no measure is prose:

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <repository> --action "<what happened>" --class <class> --then "<number> count" --status applied
   ```

   The number comes from the finding's `measure` block in the JSON: the target's own entry under `by` for a row about one repository, `value` for a row about all of them. A finding nobody acted on is not a row.
   Done when each row names the check id, the class, a measure the same script recomputes, and a verify date.

## Interpretation

- `git.unpushed` counts commits reachable from no remote, so a branch with no upstream still counts. The question the check asks is whether the work survives losing this disk.
- The finding names the branches that hold those commits, because the work is rarely on the checked out branch. A repository can be level with its upstream and still hold months of work on a branch beside it.
- The count is read from the remote refs on this disk, because nothing fetches. Fetch once before pushing: a push can be rejected by a remote that moved, and then the number was a lower bound.
- A repository with no remote reports `repo.no-remote` and no unpushed count. Counting every commit there would drown the repositories that do have a remote and are behind it.
- `git.stale-branch` uses reachability from the default branch, so a branch listed there is contained in it and deleting the branch loses no commit. Rebased or squashed work is not reachable and is not listed, which is the safe direction to be wrong in.
- `repo.lock-drift` compares modification times. It is a fast test, not a proof: touching a manifest without changing a dependency produces the same signal.
- A first pass on a machine that has never been swept reports a lot. Fix the `FAIL` ids, record the rest in `standards.md` as accepted, and the second pass is short.
