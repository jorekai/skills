# jorekai-flow

Short commands that steer a working session: how far the agent may run, where its context comes from, how work ships, and how a person hears back. Part of the [jorekai skills](../../README.md) collection.

```bash
claude plugin install jorekai-flow@jorekai
```

Start with `/jorekai-flow:flow`, or type the command you need.

## What it does

The same sentences come back in every session: "go on alone", "continue from yesterday", "push, merge when green, deploy", "tell me when it is merged", "where do we stand", "write me a handoff". Each one is a command here, and each command carries its limits, so they are not typed again.

Two questions stay apart. `jorekai-flow:resume` decides where the context comes from. `jorekai-flow:go` and `jorekai-flow:ship` decide how far the agent may run. They combine: `/jorekai-flow:resume go`.

It measures nothing, keeps no workspace, and writes no log row (`decisions/0040`).

## Skills

| Skill | Invoked by | What it does |
|---|---|---|
| [`jorekai-flow:go`](go/SKILL.md) | user | Work on alone until the goal is proved, or one step with `1`; commits, never pushes |
| [`jorekai-flow:resume`](resume/SKILL.md) | user | The last session of this project as goal, state, open items, checked against the repository |
| [`jorekai-flow:ship`](ship/SKILL.md) | user | Checks, commit, push, pull request, merge on green, documented deploy, proof it is live |
| [`jorekai-flow:watch`](watch/SKILL.md) | user | A condition checked in the background, one notice when it holds or the watch ends |
| [`jorekai-flow:status`](status/SKILL.md) | user | Goal, background work, branch, pull request, checks, and blockers in one table |
| [`jorekai-flow:handoff`](handoff/SKILL.md) | user | A prompt a new session can start from, on the clipboard |

## What each command may do

| Command | Granted | Still stops before |
|---|---|---|
| `go` | edit, run, test, commit | push, merge, deploy, production data, messages, money |
| `ship` | the above, plus push, merge on green, documented deploy | force push, merge on red, skipped hooks, undocumented deploy, production data |
| `watch` | read on a schedule, one notice | any change |
| `resume`, `status`, `handoff` | read | any change |

The router keeps the full table in [flow/SKILL.md](flow/SKILL.md).

## Read next

- [The router](flow/SKILL.md), [tools](flow/references/tools.md), [sources and heuristics](flow/references/sources.md).
- [Changelog](CHANGELOG.md).
