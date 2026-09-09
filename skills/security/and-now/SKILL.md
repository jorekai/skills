---
name: and-now
description: "Where a repository stands in the security loop and what comes next, read from the workspace files alone via scripts/status.py: rows past their verify date, open findings from the newest audit, rows naming an id this theme does not own, a review that wrote no rule, proposals without a decision, and unfinished setup."
disable-model-invocation: true
argument-hint: "[repository]"
---

# Security and now?

Answers "we just did that, and now?" from the workspace, without reading a repository and without the network. The script reads the files; you add what only the conversation knows.

## Steps

1. **Run the status script.**

   ```bash
   python3 scripts/status.py --root <workspace path> [slug]
   ```

   The script path is relative to this skill's directory. Without an argument it reports every folder whose config says `role: code`. Exit code 2 means there is no such repository: the answer is `jorekai-security:setup`, stop here.
   Done when the report names a stage and a numbered list.

2. **Read the list as an order, not as a menu.** The list is already in ladder order: a verdict that is due first, then rows nobody can measure, then failing checks by rung. Take the first item. Taking the third one first is how a loop stops settling its rows.
   Done when one item is chosen and the reason the ones above it were skipped is said out loud.

3. **Add what the files cannot know.** A repository that is being rewritten, a workflow that is meant to run that way, a credential somebody rotated yesterday without writing it down. Say which item that removes and why.
   Done when the list the user acts on is at most three items long.

## Interpretation

- **Stage `setup`** means no pass can run yet: no checkout path, no entry point, no profile, or no secret store. Unfinished setup is an item, never a gate: a repository that already has a log or an audit is in the loop, and hiding its open work behind the interview is how a workspace stalls unseen.
- **Stage `measure`** means the newest audit still holds a `FAIL`, or there is no audit at all. The first thing to run is `jorekai-security:secrets`, because a credential that is out is the one finding an edit cannot undo.
- **Stage `loop`** means the open items are rows, not findings.
- A row naming an id **this theme does not own** is the one to correct rather than to work on: nothing here will ever recompute its measure. `secret.*` belongs to the ops theme and describes a credential on a host; `repo.*` and `alert.*` belong to dx.
- A **review audit with no rule beside it** means a pass found things and left nothing a script can count. Either the findings became rules, or they belong in `proposals/` with their evidence.
- The `then` line names the first verify date that has not arrived. It is the only dated event this skill produces, and it is what makes the loop weekly rather than occasional.
- The report says how old each audit is. An audit older than the window in `standards.md` describes a repository that has moved on, and acting on it means acting on last month's code.
