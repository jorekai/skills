---
name: resume
description: "Read the previous session of this project and state its goal, where it stopped, and what is open, checked against the repository as it is now. With go, continue under the grant of jorekai-flow:go."
disable-model-invocation: true
argument-hint: "[go]"
---

# Resume

Context, not motion: this command answers where the work stands. It changes nothing unless the argument is `go`, and then the run follows `jorekai-flow:go` with the goal found here.

## Steps

1. **Find the previous session of this project.** Take the most recent session whose working directory is this project, other than the current one. Where the session store lives is in [../flow/references/tools.md](../flow/references/tools.md). Send the reading to one subagent. It returns four lines, `goal`, `last state`, `open`, `last request`, under 200 words, and the transcript stays in its context.
   Done when the four lines exist, or the answer says no previous session was found and stops.

2. **Check the claims against the repository.** A transcript says what was meant; the repository says what happened. Compare the branch, uncommitted changes, unpushed commits, and the state of the pull request the session named. A claim the repository contradicts is marked, never repeated.
   Done when every line of step 1 is confirmed or marked.

3. **Answer, then stop or go.** The answer is one table, `goal | state | open | next`, one row, then the next action. Without `go`, stop here. With `go`, take the goal and continue as `jorekai-flow:go` does.
   Done when the table stands, and with `go`, when the run has started under that grant.

## Rules

- The previous session's grants do not carry over. A push or deploy it was allowed is asked again or granted by `jorekai-flow:ship`.
- A previous session that ended on a question gets that question first, before anything else is proposed.
