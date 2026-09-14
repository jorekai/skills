# Risk classes and the gate above them

Every action in this theme carries exactly one class, decided once per check id in [fixes.md](fixes.md) and looked up at run time. A step never asks the model to judge in the moment whether a change is safe. The question that decides the class is who has to notice when the change is wrong.

## The gate: a contract file changes through review

Above every class, for every change to a file in [contracts.md](contracts.md): `stack.yaml`, `CODEOWNERS`, the rules, the gate script, the hooks, the workflows, and the configurations that carry a bar.

1. The change is a commit on a branch, never on the default branch.
2. A person who is not the agent reviews and merges it. `CODEOWNERS` is what makes the forge ask.
3. The gate is green on the branch before the merge, with the change in it.

The reason is the same as for a control in `jorekai-security`: the failure mode is not a loud break, it is a bar that quietly moved. A waiver added, a coverage number lowered, a rule removed, each reads like an ordinary commit. The gate turns each into a question a person answers.

An agent that cannot open a review because nobody owns the file has found `escape.unowned`, which is the first thing to fix.

## safe

Runs immediately. Reports afterwards what changed.

A finding is `safe` when the change is confined to a file the project owns, when a failing test or a red gate would show it at once, and when no contract file moves. Nothing in this theme is `safe` today, because every fix either touches code the gate then judges, or a contract file the gate guards.

## confirm

Prints the exact edit first: the files, the lines, and what the measure will read afterwards. Asks once. Then runs.

A finding is `confirm` when the change is reversible with one revert and the cost of getting it wrong is a red gate rather than a bar that moved. Regenerating an owned file, rewriting a lock, deleting a dead export, renaming an import to the entry point.

One question covers one list. Splitting a confirmed list into per-item questions defeats the point.

## ask

Never runs on its own. Prints what has to happen and the reason a person has to look.

A finding is `ask` when the fix is a contract file, when something outside the repository has to move (a branch protection, an account, an owner), or when the script cannot prove that a safer class applies. Every `escape.*` finding is `ask`, because the fix is either code a person decided to suppress, or a waiver, which is a review.

## Rules that hold across the three

- A script may move a finding to a stricter class when it cannot prove the safer one. It may never move a finding to a looser class.
- A class belongs to a check id, not to a command. The same edit can be `confirm` in one repository and `ask` in another; the check that found the target decides.
- An action that ran leaves a log row with the measure it changed. An action that was refused leaves nothing.
- Nothing in this theme changes a file in a repository that holds uncommitted work. The finding is reported, and the change waits for a clean tree, so a revert stays one command.
