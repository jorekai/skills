---
name: github
description: Work waiting on the forge across every repository with a remote: workflow runs that failed on the default branch, pull requests that have sat too long, reviews requested from you, open security alerts, and default branches with no protection. Use when asked what is red, which pull requests are stuck, whether anything waits on a review, or before a release.
---

# Forge

What is waiting on the other side of the remote. Reads the repository list from the newest `audits/*-repos.json`, or from `machines/<hostname>/config.md` when none is fresh, and `config.md` for `forge` and `forge_user`, whose review requests are the ones that count. No workspace: ask for the repository list and skip the log steps.

This skill needs the network and an authenticated command line for the forge; both are named in [../dx/references/tools.md](../dx/references/tools.md). Without them, say so and stop rather than guessing.

## Steps

1. **Take the repository list from what already ran.** A repository with no remote has nothing here. Reuse the newest repository audit when it is younger than the retention; run `jorekai-dx:repos` first when it is not, because the same list drives both.
   Done when the list holds only repositories with a remote on the forge, and its length is stated.

2. **Ask once per class, across all repositories, not once per repository.** Send the reading to subagents, one per class: failed runs on the default branch, pull requests open longer than the retention, reviews requested from the account, open security alerts, default branches without protection. Each returns one table with the columns `repository | id | age in days | title | link` and nothing else, under 200 words.
   Done when every class has a table or a stated reason it could not be read, and no repository page text reached this context.

3. **Rank by what blocks other people, then by age.** A review someone is waiting on outranks a red pipeline on a repository nobody is releasing. An open alert on a repository with a remote that others pull outranks both. Look each id up in [../dx/references/fixes.md](../dx/references/fixes.md).
   Done when the answer is at most five rows and every row names the next action and its owner.

4. **Write the findings as an audit and log only what was done.** Save the tables as `audits/YYYY-MM-DD-github.json` in the same shape the other passes use: `tool`, `target`, `counts`, and `items` with a check id, a level, a message, and the list under `data`. Then one log row per check id that was acted on, with the count as the measure.
   Done when the JSON parses and `jorekai-dx:and-now` reports its counts.

The check ids this skill produces are `ci.failing`, `pr.review-requested`, `pr.stale`, `alert.open`, and `branch.unprotected`. Each has a row in [../dx/references/fixes.md](../dx/references/fixes.md).

## Rules

- Nothing here changes a repository. Merging, closing, and rerunning are decisions with owners; this skill names them and stops.
- A finding is per check id across all repositories, not per repository. Twenty red pipelines are one row that lists twenty.
- An unauthenticated or rate-limited forge is a stated gap, never an empty table. An empty table means the class was read and held nothing.

## Interpretation

- A workflow that failed once on a branch nobody merged is noise. The check is failures on the default branch, because that is the state other people pull.
- A pull request's age counts from its last update, not from when it opened. A long-running one that moves every week is not stuck.
- A review requested from the account is the only class where someone else is waiting. It goes first even when its numbers are small.
- Branch protection missing on a repository worked on alone is a preference, not a finding. Record that in `standards.md` and it stops being reported.
