---
name: and-now
description: "Where a repository stands in the stack loop and what comes next, read from the workspace files alone via scripts/status.py: rows past their verify date, open findings from the newest audit, rows naming an id this theme does not own, human steps and open decisions from the snapshot of the declaration, and unfinished setup."
disable-model-invocation: true
argument-hint: "[repository]"
---

# Stack and now?

Answers "we just did that, and now?" from the workspace, without reading a repository and without the network. The script reads the files; you add what only the conversation knows.

## Steps

1. **Run the status script.**

   ```bash
   python3 scripts/status.py --root <workspace path> [slug]
   ```

   The script path is relative to this skill's directory. Without an argument it reports every folder whose config says `role: stack`. Exit code 2 means there is no such repository: the answer is `jorekai-stack:setup`, stop here.
   Done when the report names a stage and a numbered list.

2. **Read the list as an order, not as a menu.** The list is already in ladder order: a verdict that is due first, then rows nobody can measure, then failing checks by rung, then what the snapshot of the declaration leaves open. Take the first item. Taking the third one first is how a loop stops settling its rows.
   Done when one item is chosen and the reason the ones above it were skipped is said out loud.

3. **Add what the files cannot know.** A repository that is being regenerated, a waiver a person agreed to yesterday and nobody wrote down, a branch protection set in the forge that the declaration does not date yet. Say which item that removes and why.
   Done when the list the user acts on is at most three items long.

## Interpretation

- **Stage `setup`** means no pass can run yet: no checkout path, no profile, or no `state` saying whether the tree is generated or adopted. Unfinished setup is an item, never a gate: a repository that already has a log or an audit is in the loop, and hiding its open work behind the interview is how a workspace stalls unseen.
- **Stage `measure`** means the newest audit still holds a `FAIL`, or there is no audit at all. The first thing to run is `jorekai-stack:guards`, because a suppression nobody named is the one finding that hides every other one: a guard that was switched off reports nothing about what it was guarding.
- **Stage `loop`** means the open items are rows, not findings.
- A row naming an id **this theme does not own** is the one to correct rather than to work on: nothing here will ever recompute its measure. `escape.*`, `guard.*` and `dead.*` belong to `jorekai-stack:guards`; `decl.*`, `boundary.*`, `adapter.*` and `lock.*` to `jorekai-stack:drift`. `cred.*`, `build.*` and `dep.*` belong to the security theme, `repo.*` and `agent.*` to dx, `secret.*` to ops.
- An **unreadable** row is one the script cannot parse at all: a malformed table row, or an applied row whose `Verify after` cell is not a `YYYY-MM-DD` date. Neither vanishes silently (decisions/0030); the first one names its file and line so it can be repaired by hand.
- The **snapshot** is the copy of the repository's `stack.yaml` that `jorekai-stack:setup` keeps in the workspace. A human step without a date and a decision past its date are read from it, so they become items without reading the repository. No snapshot means the script cannot see them and says so; an unread snapshot means the copy is older than the reader or was edited by hand.
- The `then` line names the first verify date that has not arrived. It is the only dated event this skill produces, and it is what makes the loop weekly rather than occasional.
- The report says how old each audit is. An audit older than the window in `standards.md` describes a repository that has moved on, and acting on it means acting on last month's tree.
