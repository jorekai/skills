---
name: choose
description: "Interview the owner about the shape of the product, the OSS level, the target, the bars, the open decisions and the owner, then write stack.yaml with the eight adapters the two axes resolve to."
disable-model-invocation: true
argument-hint: "[directory]"
---

# Stack choose

Interview the user until `stack.yaml` holds everything `jorekai-stack:new` needs to generate the tree without asking. Needs the workspace from `jorekai-stack:setup`; missing: run that first.

## Rules

- **Design tree.** The questions hang off each other; [references/question-bank.md](references/question-bank.md) is the tree. The **frontier** is every question whose prerequisites are settled. Ask the whole frontier in one round, numbered, each with your recommended answer. Wait. Recompute the frontier from the answers. A question that depends on an answer still open in this round belongs to the next round.
- **Facts are the agent's job, decisions are the user's.** Before asking, read what exists: an earlier `stack.yaml`, the manifests and the lock file, the workflows, the profile and the owner in the workspace. Ask the user only what the tree cannot tell you: who runs it, how much they want to operate, where the users are, when the postponed things are decided.
- **Write as decisions land**, not at the end. The two axes and the profile go into the script's arguments in the round they are settled; the rest is edited into the file after it is written. A session cut short still leaves a usable file.
- **A bar moved by hand is a review later.** Recommend the profile, and record a single bar moved away from it with its reason on the line beside it.

Question format, one per question:

```
Q3. <title>: <question, with the options where there are options>
Recommended: <answer and the one-line reason>
```

## Steps

1. **Load.** Read the existing `stack.yaml` when there is one (a re-run starts from what is there and asks only what is blank or contradicted), the manifests, the lock file and the workflows when a tree exists, and `standards.md` and `config.md` in the workspace for the profile, the owner and the forge.
   Done when the frontier for round 1 is the tree's roots minus what these files already answer.

2. **Rounds** until the frontier is empty: the shape, then the OSS level and the target, then the bars from the profile, the dates of the seven open decisions, the owner, and the accounts that exist. Every branch of the tree visited; nothing silently assumed. When the level is `full` and the target runs no server, say so in the round where it comes up, because the declaration will record it as a caveat.
   Done when both axes, the profile, the owner and the decision date are settled, and every bar moved away from the profile has a reason.

3. **Write the file.**

   ```bash
   python3 scripts/declare.py --root <directory> --oss <level> --target <target> \
     [--profile <p>] [--name <n>] [--owner <@x>] [--decide-by YYYY-MM-DD]
   ```

   The script path is relative to this skill's directory. It writes `stack.yaml` from [templates/stack.yaml](templates/stack.yaml) with every placeholder substituted and refuses to overwrite a file that exists. A bar moved away from the profile, an open decision already taken, and an account that exists are edited into the file afterwards, by hand, in the sections the tree names.
   Done when the file exists, no placeholder is left in it, and `declare.py --root <directory> --show` prints the same eight adapters the file carries.

4. **Close.** Show the resolution once: the path, the two axes, the eight adapters, the caveat when there is one. No table. Name `jorekai-stack:new` as the next command, and `scaffold.py --snapshot` in `jorekai-stack:setup` as the step after it. No log row: nothing was measured.
   Done when the user holds the path and the next command.

## Interpretation

- The file is a contract from the moment it exists. Once `jorekai-stack:new` has written `CODEOWNERS`, every later change to it is a review by the owner it names, which is why the interview settles the bars now and not after the first red gate.
- A port that is not the one the axes resolve to is not a wrong answer. It is a port exception, recorded under `port_exceptions` with the reason, and `jorekai-stack:drift` reads the entry as the exception instead of as drift.
- The memory adapter is never chosen here. Every port runs on it until its two keys are set, which is why no account has to exist before the first gate is green.
- The seven open decisions cost nothing until their date. `jorekai-stack:drift` counts a line past its date, so a date far out is a decision to decide later, and a date nobody meant is a finding in ninety days.
