---
name: ship
description: "Take finished work out: run the checks, commit, push, open or reuse a pull request, merge once checks are green, deploy the way the project documents, and prove the result is live."
disable-model-invocation: true
argument-hint: "[pull request] [--no-deploy]"
---

# Ship

The one command that grants push, merge, and deploy. It ships what is finished; it does not finish work. A red check that needs more than a small fix stops the run and hands back to `jorekai-flow:go`.

## Steps

1. **Find how this project ships.** Read the project's own instructions for its checks, its merge rule, and its deploy. A project that documents no deploy ships up to the merge and says so. `--no-deploy` stops after the merge as well.
   Done when the check command, the merge rule, and the deploy step are each named, or named as absent.

2. **Prove the tree before it leaves.** Run the project's checks locally. Commit what is uncommitted, with a message in the project's commit style. A red check gets one small fix inside the scope of the work; anything larger stops here.
   Done when the checks are green and the tree is clean.

3. **Push and open the pull request.** Reuse the pull request named in the argument or the one open for this branch. A new one carries a title in the project's style and a body that says what changed and why.
   Done when the branch is pushed and the pull request has a link.

4. **Wait for green, then merge.** Wait on the checks without asking in a loop; a background watch reports back. A red check gets the same one small fix as step 2, then a new wait. Merge with the method the project uses once every required check is green and every required review is in.
   Done when the pull request is merged, or the answer names the check or review it waits on.

5. **Deploy and prove it.** Run the documented deploy for the target the project names. Then prove the result: the deployed version answers, a health check returns, or the page shows the change.
   Done when the proof is in the `link` column, or the deploy is named as absent.

The answer is one table, `stage | result | link`, one row per stage that ran, then one line with the next action. The frame is the router's `## Writing the answer`.

## Rules

- Never force push, never merge on red, never skip a hook or a required review. A blocked merge is a stop with its reason.
- Deploy only what the project documents. A deploy invented from a guess is how production breaks.
- Production data is outside this grant. A migration that touches it stops and asks.
