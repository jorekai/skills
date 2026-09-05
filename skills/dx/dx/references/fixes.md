# Fixes

One row per check id: what a finding means, what closes it, the risk class the action runs under, and the measure the same script recomputes at the verify date. The check id is the join key between a script's output, a log row, and this file.

The classes are defined in [risk-classes.md](risk-classes.md). Above all of them: nothing destructive runs against a repository holding uncommitted or unpushed work.

## Repositories

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `git.dirty` | The working tree holds changes that exist nowhere else | Commit them, or stash them deliberately, or discard them after looking | `ask` | Changed paths in the repository |
| `git.unpushed` | Commits exist on this disk and on no remote | Push the branch, or create the branch upstream and push | `ask` | Commits reachable from no remote |
| `repo.no-remote` | The repository has no remote at all, so losing the disk loses the work | Create the remote and push, or record that the repository is deliberately local in `standards.md` | `ask` | Number of repositories with no remote |
| `git.no-upstream` | The current branch tracks nothing, so a plain push has no target | Push with an upstream set, or delete the branch if it was a scratch branch | `confirm` | Branches with no upstream |
| `git.detached` | HEAD points at a commit, not a branch, so the next commit is easy to lose | Create a branch at that commit, or return to the branch the work belongs on | `ask` | Repositories with a detached HEAD |
| `git.stash-old` | A stash entry older than the retention. A dropped stash is subject to pruning and may be impossible to recover | Apply it, or turn it into a branch, or drop it deliberately | `ask` | Age of the oldest stash in days |
| `git.stale-branch` | A local branch whose tip is reachable from the default branch, older than the retention | Delete the branch. Its commits stay in the default branch | `safe` when the repository is clean and pushed, `confirm` otherwise | Number of merged branches over the retention |
| `repo.lock-drift` | The lock file is older than the manifest beside it, so the installed tree and the declared one disagree | Reinstall so the lock is written again, then commit the lock | `confirm` | Repositories whose lock is older than its manifest |
| `repo.no-readme` | No README at the repository root | Write one, or record in `standards.md` that this kind of repository needs none | `safe` | Repositories without a README |
| `repo.no-ignore` | No ignore file, so build output and local settings are one `git add` away from being committed | Add one that matches the stack | `safe` | Repositories without an ignore file |
| `repo.no-ci` | Nothing runs checks when the repository is pushed | Add the smallest useful check, or record that the repository needs none | `confirm` | Repositories with no checks on push |

## Machine

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `disk.low` | Free space is below the floor in `standards.md` | Work through `disk.cache`, `disk.large-dir`, and `container.reclaimable`, biggest first | `ask` | Free bytes on the volume |
| `disk.cache` | Cache directories a tool refills on its next run | Empty the biggest ones. The next build or install is slower once, then back to normal | `safe` | Total bytes in the cache directories |
| `disk.large-dir` | A dependency or build tree that a manifest in the repository rebuilds | Remove it in repositories that are not being worked on. The repository must be clean and pushed first | `confirm` | Total bytes in the reported trees |
| `mem.pressure` | Little memory is available, so everything waits on swap | Find what holds it and close it. A machine that reaches this during ordinary work needs a decision, not a cleanup | `ask` | Available memory as a percentage |
| `container.reclaimable` | The runtime reports storage held by objects nothing uses. The figure is an upper bound, not a promise | Remove the classes one at a time, biggest first, and measure after each | See `container.*` below | Reclaimable bytes per object type |
| `container.dangling-images` | Image layers no tag points at | Remove them. A rebuild or a pull produces them again | `safe` | Bytes in dangling images |
| `container.build-cache` | Cached build layers | Remove them. The next build is slower once | `safe` | Bytes in the build cache |
| `container.stopped` | Containers that are not running | Remove the ones that hold no state worth keeping | `confirm` | Number of stopped containers |
| `container.old-images` | Tagged images unused for longer than the retention | Remove them. Each one is a pull or a build away | `confirm` | Bytes in images over the retention |
| `container.unused-volumes` | Volumes no container uses. A named volume holds data that nothing else holds | Anonymous volumes: remove. Named volumes: look first, always | `confirm` for anonymous, `ask` for named | Bytes in unused volumes |

## Forge

Every check here needs the network and an authenticated command line. An unreadable class is a stated gap, never an empty table.

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `ci.failing` | A workflow failed on the default branch, which is the state other people pull | Fix it or turn the workflow off. A check nobody trusts is worse than none | `ask` | Repositories red on the default branch |
| `pr.review-requested` | Someone asked this account for a review and is waiting | Review it, or say when. This is the only class where the cost falls on someone else | `ask` | Open review requests |
| `pr.stale` | A pull request has not moved for longer than the retention | Merge, close, or say what it waits on | `ask` | Pull requests over the retention |
| `alert.open` | The forge reports a security advisory against a dependency | Update the dependency, or record why the advisory does not apply | `ask` | Open alerts by severity |
| `branch.unprotected` | The default branch takes any push | Turn protection on, or record in `standards.md` that this repository is worked on alone | `confirm` | Repositories without protection |

## Agent configuration

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `agent.no-pointer` | The project carries no pointer file, so a session starts from nothing | Add the file `standards.md` names, with the paths that project actually has | `safe` | Projects without a pointer file |
| `agent.pointer-drift` | The pointer file names a path, a command, or a skill that no longer exists | Correct the lines that moved. A pointer that lies costs more than no pointer | `safe` | Projects whose pointer names something missing |
| `agent.permission-drift` | A project grants more than the standard | Narrow it to the standard, or record the exception | `confirm` | Projects over the standard |
| `agent.hook-broken` | A hook runs a command that is not on this machine, so it fails on every tool call | Fix the command or remove the hook | `confirm` | Projects with a failing hook |
| `agent.server-unreachable` | A configured server does not answer | Start it, fix its address, or remove it from the project | `confirm` | Configured servers that do not answer |

## Friction

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `friction.repeat-command` | One command shape carries a lot of the day | Only worth changing when it is also slow or fails. Frequency alone is a habit, not a cost | `safe` | Runs per shape in the window |
| `friction.repeat-sequence` | Two commands always run one after the other | Write the one command that does not exist yet | `safe` | Times the pair occurs |
| `friction.failed-command` | A shape fails often enough to be a pattern | Find the precondition it keeps missing and make it explicit | `safe` | Failures and total runs per shape |
| `friction.retry-prompt` | A shape gets run again within minutes of failing, which is a person guessing | Make the failure say what to do next | `safe` | Retries per shape |
| `friction.slow-command` | A shape costs more total time than any other | Make it faster, run it less, or run it in the background | `safe` | Total seconds per shape |

## Reading a finding

- `FAIL` means work is at risk or the machine cannot do its job. It outranks every `WARN` and `INFO`, whatever the totals say.
- One finding is one log row, listing the repositories or paths it covers. One row per path turns a weekly answer into a list nobody reads.
- A finding whose fix has no measure in this table is a proposal, not an action.
