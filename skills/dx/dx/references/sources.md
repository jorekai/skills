# Sources

Claims in this skill set that rest on a documented fact, with the source and the date it was last checked. Re-check these when refreshing the skills; everything not listed here is a heuristic or the author's practice.

| Claim | Source | Checked |
|---|---|---|
| `docker system prune` removes stopped containers, unused networks, dangling images, and unused build cache; unused volumes only with `--volumes`, and then only anonymous ones | https://docs.docker.com/reference/cli/docker/system/prune/ | 2026-09-05 |
| `docker system prune -a` widens image removal to every image with no container associated to it | https://docs.docker.com/reference/cli/docker/system/prune/ | 2026-09-05 |
| `docker system df` prints a reclaimable size and a percentage per object type; the reference does not define the column further | https://docs.docker.com/reference/cli/docker/system/df/ | 2026-09-05 |
| `git branch --merged <commit>` lists only branches whose tips are reachable from that commit, `HEAD` when none is given | https://git-scm.com/docs/git-branch | 2026-09-05 |
| A dropped stash entry is subject to pruning and may be impossible to recover; the newest stash lives in `refs/stash`, older ones in that reference's reflog | https://git-scm.com/docs/git-stash | 2026-09-05 |

## Heuristics, not facts

These carry no source because none exists. They are the author's practice and are open to being wrong.

- Ranking friction by the time it costs beats ranking it by how annoying it feels.
- A verify window of fourteen days is long enough for a maintenance change to show and short enough to still remember the change.
- A weekly answer capped at three items gets acted on. A list of twenty gets skimmed.
- The reclaimable figure a container runtime prints is an upper bound of what a prune frees, not a promise.
- A lock file older than its manifest means the installed tree and the declared one disagree. It is a fast test, not a proof: a manifest can be touched without changing a dependency.
- Ninety days for a merged branch and twenty gigabytes of free space are starting values, not findings. They live in `standards.md` so a machine can disagree with them.
