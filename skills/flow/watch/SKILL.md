---
name: watch
description: "Check a condition in the background and send one notice when it holds or the watch gives up: a pull request merged, a release live, a job finished, a page answering."
disable-model-invocation: true
argument-hint: "<condition> [--every DURATION] [--for DURATION]"
---

# Watch

A person says "tell me when it is merged" and leaves. This command turns that sentence into a check that runs without the session asking in a loop, and one notice at the end.

## Steps

1. **Turn the condition into a check that can run.** One command or request whose answer is yes or no: a pull request state, a deployed version, a job status, a response code. A condition that cannot be checked from here is said so, and the watch does not start.
   Done when the check runs once by hand and prints its current answer.

2. **Set the pace and the end.** `--every` defaults to the time the condition usually takes to change, never shorter than a minute. `--for` defaults to two hours. A watch with no end is not started.
   Done when the interval and the end are named.

3. **Run it in the background and stay free.** The check runs outside the conversation, so the session can do other work. When it holds, when it fails for good, or when the end is reached, one notice goes out, by push notice where the session has one and in the conversation always.
   Done when the watch runs and its first check is logged.

The answer has no table: the condition, the check, the interval, and when the watch gives up, then one line with what the notice will say.

## Rules

- A watch reads. It never merges, retries, or fixes what it watches. Acting on the result is a separate grant.
- One notice per watch. A condition that flips back and forth reports its first change and ends.
- A failed check is not a no. Three failed checks in a row end the watch with the error.
