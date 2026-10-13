---
name: handoff
description: "Write a prompt a new session can start from with nothing else: goal, state, decisions with reasons, files, open items, the next step, and the limits. Places it on the clipboard."
disable-model-invocation: true
argument-hint: "[focus]"
---

# Handoff

The new session knows nothing this one knows. The prompt carries what it needs to start the next step without asking, and nothing it would read anyway from the repository.

## Steps

1. **Collect what only this session knows.** The goal, the decisions made and why, what was tried and failed, what is open, and the grants the person gave. With a focus argument, keep only what serves that focus.
   Done when every item is one line, and nothing in it can be read from the repository alone.

2. **Write the prompt.** In this order: the goal in one sentence; the project path and branch; the state; the decisions with reasons; what failed; the open items; the next step; the limits, including what the new session may not do without asking. Name files by path, never by pasting them. Under 400 words. Same language as the person writes in.
   Done when a reader with only the repository and this prompt can name the next step.

3. **Place it on the clipboard.** Where the session has no clipboard, write it to a file in the scratch area and name the path.
   Done when the clipboard holds the prompt, read back once.

The answer has no table: the word count, where the prompt sits, and its first line.

## Rules

- A grant does not travel. The prompt lists what was granted here as context, and says the new session asks again.
- No secret, token, or password goes into the prompt. Name where it lives instead.
