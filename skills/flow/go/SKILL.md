---
name: go
description: "Grant the agent to work on alone until the current goal is met and proved, or for exactly one step with 1. Commits on the current branch; stops before push, merge, deploy, and anything outside the work tree."
disable-model-invocation: true
argument-hint: "[1] [goal]"
---

# Go

A grant, not a task: the goal is the one this session already holds, or the text after the command. The grant ends when the goal is met and proved, at a stop the router's `## Grants` table names, or after one step when the first argument is `1`.

## Steps

1. **Name the goal and the finish line.** Write the goal in one sentence and the proof that ends it: a test that passes, a check that prints clean, a response that returns the right value. A goal with no proof that can be run gets one before work starts.
   Done when the goal and its proof stand in one line each.

2. **Work in the smallest steps that can each be checked.** After each step, run the check that covers it. A red check is fixed before the next step starts. Commit at each point where the tree is green and the step is whole, with a message in the project's commit style.
   Done when every step so far ends on a green check and a commit.

3. **Stop only where the grant ends.** A step that needs push, merge, deploy, production data, a deletion outside the work tree, a message to another person, or money stops here. So does a real blocker: missing access, a decision only the person can make, or two attempts at the same fix that failed. Collect what is open and ask it once, numbered, each item with a reason and a recommendation.
   Done when the goal is proved, or the stop names exactly what it needs.

4. **With `1`, stop after the first whole step.** Answer with that step and the next one proposed.
   Done when one step is committed and the next is named.

The answer is one table, `step | result | proof`, one row per step, at most seven rows, then one line with the next action. The frame is the router's `## Writing the answer`.

## Rules

- Never weaken a check to make it pass: no skipped test, no loosened assertion, no hook bypass. A check that is wrong is fixed in its own commit, with the reason.
- The goal does not grow. Work found on the way that is outside the goal is listed at the end, not done.
- Two failed attempts at the same fix stop the run. A third guess costs more than the question.
