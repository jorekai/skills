# Fixes

One row per check id: what a finding means, what closes it, the risk class the action runs under, and the measure the same script recomputes at the verify date. The check id is the join key between a script's output, a log row, and this file.

Every measure counts what the finding costs, so lower is better and zero means the check no longer fires. Two of them are inverted for that reason: free space is written as the bytes missing from the floor, available memory as the points missing from it. The unit in brackets is the unit the log row carries, and `jorekai-dx:grade` compares the number in the row to the number in the newest audit.

The classes are defined in [risk-classes.md](risk-classes.md). Above all of them: nothing destructive runs against a repository holding uncommitted or unpushed work.

## Repositories

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `git.dirty` | The working tree holds changes that exist nowhere else | Commit them, or stash them deliberately, or discard them after looking | `ask` | Changed paths in the target repository (`count`) |
| `git.unpushed` | Commits exist on this disk and on no remote | Push the branches the finding names, or create them upstream and push. Fetch once first, because the count is read from the remote refs on this disk | `ask` | Commits that exist on no remote (`count`) |
| `repo.no-remote` | The repository has no remote at all, so losing the disk loses the work | Create the remote and push, or record that the repository is deliberately local in `standards.md` | `ask` | Repositories with no remote (`count`) |
| `git.no-upstream` | The current branch tracks nothing, so a plain push has no target | Push with an upstream set, or delete the branch if it was a scratch branch | `confirm` | Branches with no upstream (`count`) |
| `git.detached` | HEAD points at a commit, not a branch, so the next commit is easy to lose | Create a branch at that commit, or return to the branch the work belongs on | `ask` | Repositories with a detached HEAD (`count`) |
| `git.identity` | The repository would commit under an address other than the one in `config.md` | Set the address for that repository, or correct the one in `config.md` | `safe` | Repositories whose effective address differs (`count`) |
| `git.stash-old` | A stash entry older than the retention. A dropped stash is subject to pruning and may be impossible to recover | Apply it, or turn it into a branch, or drop it deliberately | `ask` | Stash entries past the retention (`count`) |
| `git.stale-branch` | A local branch whose tip is reachable from the default branch, older than the retention | Delete the branch. Its commits stay in the default branch | `safe` when the repository is clean and pushed, `confirm` otherwise | Merged branches over the retention (`count`) |
| `repo.lock-drift` | The lock file is older than the manifest beside it, so the installed tree and the declared one disagree | Reinstall so the lock is written again, then commit the lock | `confirm` | Repositories whose lock is older than its manifest (`count`) |
| `repo.no-readme` | No README at the repository root | Write one, or record in `standards.md` that this kind of repository needs none | `safe` | Repositories without a README (`count`) |
| `repo.no-ignore` | No ignore file, so build output and local settings are one `git add` away from being committed | Add one that matches the stack | `safe` | Repositories without an ignore file (`count`) |
| `repo.no-ci` | Nothing runs checks when the repository is pushed | Add the smallest useful check, or record that the repository needs none | `confirm` | Repositories with no checks on push (`count`) |

## Machine

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `disk.low` | Free space is below the floor in `standards.md` | Work through `disk.cache`, `disk.large-dir`, and `container.reclaimable`, biggest first | `ask` | Bytes short of the floor, zero when the floor is met (`bytes`) |
| `disk.cache` | Cache directories a tool refills on its next run | Empty the biggest ones. The next build or install is slower once, then back to normal | `safe` | Total bytes in the cache directories (`bytes`) |
| `disk.large-dir` | A dependency or build tree that a manifest in the repository rebuilds | Remove it in repositories that are not being worked on. The repository must be clean and pushed first | `confirm` | Total bytes in the reported trees (`bytes`) |
| `mem.pressure` | Little memory is available, so everything waits on swap | Find what holds it and close it. A machine that reaches this during ordinary work needs a decision, not a cleanup | `ask` | Percentage points below the memory floor, zero when it is met (`percent`) |
| `container.reclaimable` | The runtime reports storage held by objects nothing uses. The figure is an upper bound, not a promise | Remove one class at a time, biggest first, and measure again after each | Per class, see below | Reclaimable bytes over all object types (`bytes`) |

## Forge

Every check here needs the network and an authenticated command line. An unreadable class is a stated gap, never an empty table.

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `ci.failing` | A workflow failed on the default branch, which is the state other people pull | Fix it or turn the workflow off. A check nobody trusts is worse than none | `ask` | Repositories red on the default branch (`count`) |
| `pr.review-requested` | Someone asked this account for a review and is waiting | Review it, or say when. This is the only class where the cost falls on someone else | `ask` | Open review requests (`count`) |
| `pr.stale` | A pull request has not moved for longer than the retention | Merge, close, or say what it waits on | `ask` | Pull requests over the retention (`count`) |
| `alert.open` | The forge reports a security advisory against a dependency | Update the dependency, or record why the advisory does not apply | `ask` | Open alerts (`count`) |
| `branch.unprotected` | The default branch takes any push | Turn protection on, or record in `standards.md` that this repository is worked on alone | `confirm` | Repositories without protection (`count`) |

## Agent configuration

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `agent.no-pointer` | The project carries no pointer file, so a session starts from nothing | Add the file `standards.md` names, with the paths that project actually has | `safe` | Projects without a pointer file (`count`) |
| `agent.pointer-drift` | The pointer file names a path, a command, or a skill that no longer exists | Correct the lines that moved. A pointer that lies costs more than no pointer | `safe` | Projects whose pointer names something missing (`count`) |
| `agent.permission-drift` | A project grants more than the standard | Narrow it to the standard, or record the exception | `confirm` | Projects over the standard (`count`) |
| `agent.hook-broken` | A hook runs a command that is not on this machine, so it fails on every tool call | Fix the command or remove the hook | `confirm` | Projects with a failing hook (`count`) |
| `agent.server-unreachable` | A configured server does not answer | Start it, fix its address, or remove it from the project | `confirm` | Configured servers that do not answer (`count`) |

## Friction

| Check | What it means | Fix | Class | Measure |
|---|---|---|---|---|
| `friction.repeat-command` | One command shape carries a lot of the day | Only worth changing when it is also slow or fails. Frequency alone is a habit, not a cost | `safe` | Runs of the reported shapes in the window (`count`) |
| `friction.repeat-sequence` | Two commands always run one after the other | Write the one command that does not exist yet | `safe` | Times the reported pairs occur (`count`) |
| `friction.failed-command` | A shape fails often enough to be a pattern | Find the precondition it keeps missing and make it explicit | `safe` | Failed runs of the reported shapes (`count`) |
| `friction.retry-prompt` | A shape gets run again within minutes of failing, which is a person guessing | Make the failure say what to do next | `safe` | Retries of the reported shapes (`count`) |
| `friction.slow-command` | A shape costs more total time than any other | Make it faster, run it less, or run it in the background | `safe` | Total seconds the reported shapes cost (`seconds`) |
| `friction.agent-sessions` | How many agent sessions each project needed, counted from the session files without opening one | Nothing to fix. A project far above the rest is worth asking about: it is either the busiest or the hardest to work in | `safe` | Sessions in the window (`count`) |

### The classes inside `container.reclaimable`

The runtime reports one total per object type, so there is one check id. The removal is per class, and each class has its own risk:

- Dangling image layers and the build cache are `safe`: a rebuild or a pull produces them again.
- Stopped containers and images past the retention are `confirm`: each one is a pull or a build away, and the dry run shows which.
- Anonymous volumes are `confirm`. Named volumes are `ask`, always: a named volume holds data that nothing else holds, which is why the runtime's own default removal leaves unused volumes alone.

## Reading a finding

- `FAIL` means work is at risk or the machine cannot do its job. It outranks every `WARN` and `INFO`, whatever the totals say.
- One finding is one log row, listing the repositories or paths it covers. One row per path turns a weekly answer into a list nobody reads.
- A finding whose fix has no measure in this table is a proposal, not an action.
- A row is graded by recomputing its measure with the same script and the same flags. The cost fell or reached zero: `won`. It stayed inside the tolerance: `no-change`. It rose past it: `returned`. Nobody carried the action out: `dropped`, which only a person can decide.
