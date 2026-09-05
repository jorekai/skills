---
name: and-now
description: Where a machine stands in the developer experience loop and what comes next, read from the workspace files alone via scripts/status.py: rows past their verify date, open findings from the newest audit, open log rows, proposals without a decision, and unfinished setup.
disable-model-invocation: true
argument-hint: "[machine]"
---

# DX and now?

Answers "we just did that, and now?" from the workspace without touching the machine and without the network. The script reads the files; you add what only the conversation knows.

## Steps

1. **Run the status script.**

   ```bash
   python3 scripts/status.py --root <workspace path> [machine]
   ```

   The script path is relative to this skill's directory. Without a machine argument it reports every folder under `machines/`. Exit code 2 means there is no workspace: the answer is `jorekai-dx:setup`, stop here.
   Done when the report prints `stage:` and a numbered `now:` list.

2. **Correct the list with what the files cannot show.** Three cases, nothing else:
   - The user reports something broken right now: no space, a machine that crawls, a repository that will not push. That goes to the top of the list, before any hygiene item.
   - The user says a listed item is already done: write it back now, into the log row or the audit it points to, so the next run stops listing it. Do not carry it in your head.
   - A row is due for a verdict and its measure cannot be recomputed. The row was written without one. Move it to `proposals/` and say so, rather than inventing a number.
   Done when every item is either still open or written back to the workspace.

3. **Answer** in three parts and no more: `stage` in one line, `now` as at most three items in the script's order, each naming what to run or which file to edit, and `then` with the next dated event. The script puts rows past their verify date first, because a verdict is what makes the log learn. Invoke the next skill only when the user asks for it.
   Done when the user can act on item 1 without opening another file.

## Interpretation

- `stage: setup` with one item means nothing has run on this machine yet. Any other stage means the loop is running, and unfinished setup appears as a ranked item instead of a wall.
- `stage: measure` means the newest audit still reports failures, or no audit exists. Fixing them comes before anything further down the priority ladder.
- An audit older than a month is reported as stale. Acting on a month-old measurement is how a fix lands on a machine that already moved on.
- `due for verdict` counts rows whose verify date has passed. A row that never gets graded costs more than it saved, because the next decision has no evidence behind it.
