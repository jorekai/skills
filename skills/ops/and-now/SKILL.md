---
name: and-now
description: "Where a host stands in the ops loop and what comes next, read from the workspace files alone via scripts/status.py: rows past their verify date, open findings from the newest audit, rows waiting for a tool that has not shipped, rows naming an id this theme does not own, proposals without a decision, and unfinished setup."
disable-model-invocation: true
argument-hint: "[host]"
---

# Ops and now?

Answers "we just did that, and now?" from the workspace, without touching a host and without the network. The script reads the files; you add what only the conversation knows.

## Steps

1. **Run the status script.**

   ```bash
   python3 scripts/status.py --root <workspace path> [host]
   ```

   The script path is relative to this skill's directory. Without a host argument it reports every folder whose config says `role: server`. Exit code 2 means there is no such host: the answer is `jorekai-ops:setup`, stop here.
   Done when the report names a stage and a numbered list.

2. **Read the list as an order, not as a menu.** The list is already in ladder order: a verdict that is due first, then rows nobody can measure, then failing checks by rung. Take the first item. Taking the third one first is how a loop stops settling its rows.
   Done when one item is chosen and the reason the ones above it were skipped is said out loud.

3. **Add what the files cannot know.** A host that is being rebuilt, a service that is meant to be off, a change someone else made yesterday. Say which item that removes and why.
   Done when the list the user acts on is at most three items long.

## Interpretation

- **Stage `setup`** means no pass can run yet: no access recorded, no control plane detected, no profile chosen, or no second way in. Unfinished setup is an item, never a gate: a host that already has a log or an audit is in the loop, and hiding its open work behind the interview is how a workspace stalls unseen.
- **Stage `measure`** means the newest audit still holds a `FAIL`, or there is no audit at all. The first thing to run is `jorekai-ops:access`, because every other fix here needs a second way in first.
- **Stage `loop`** means the open items are rows, not findings.
- A row **waiting for a tool** carries an id this theme owns whose script has not shipped. It is not broken. Leave its status at `todo` and its verify date empty until the release named in the report, because a date nobody can measure at is a verdict nobody can give.
- A row naming an id **this theme does not own** is different: nothing will ever recompute its measure. Correct the id or drop the row.
- The `then` line names the first verify date that has not arrived. It is the only dated event this skill produces, and it is what makes the loop weekly rather than occasional.
