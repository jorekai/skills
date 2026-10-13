---
name: status
description: "State where this session stands: the goal, what is done, what runs in the background, the branch and its pull request and checks, and what blocks. Reads only, changes nothing."
disable-model-invocation: true
---

# Status

One look instead of five questions: "how does it look", "what is still open", "what is running", "is it merged", "what is next". Everything here is read now; nothing is answered from memory of an earlier turn.

## Steps

1. **Read the session.** The goal it works on, the steps it finished, and the work still running in the background with its state.
   Done when each background job is named with running, finished, or failed.

2. **Read the repository.** Branch, uncommitted changes, unpushed commits, the pull request for this branch, and the state of its checks and reviews.
   Done when each is read, or named as unreadable with the reason.

3. **Name what blocks.** A check that is red, a review someone waits on, a question the person has not answered, a grant the next step needs.
   Done when every blocker names who removes it.

The answer is one table, `item | state | next`, at most seven rows, blockers first, then one line with the next action. The frame is the router's `## Writing the answer`.

## Rules

- Read, never fix. A status that starts fixing is a run nobody granted.
- A state read from the repository beats a state remembered from the conversation. When they differ, the row says so.
