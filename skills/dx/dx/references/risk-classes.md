# Risk classes

Every destructive action in this skill set carries exactly one class. The class is decided once, written down next to the check that finds the thing, and looked up at run time. A step never asks the model to judge in the moment whether a removal is safe.

The question that decides the class is not how much a command removes. It is who has to rebuild what was removed.

## The gate above all three

Nothing destructive runs against a repository that holds uncommitted changes or commits that are not pushed anywhere. That is `ask`, whatever the check's own class says.

Unsaved work outranks disk space, tidiness, and every other finding. A machine full of dirty repositories therefore reports a lot and removes almost nothing, which is the correct outcome.

## safe

Runs immediately. Reports afterwards what was removed and how much came back.

A finding is `safe` when a documented command rebuilds the removed thing without a person deciding anything, and when the rebuild needs no input that only that person has. Derived output, caches, and artifacts that are regenerated on the next run belong here.

## confirm

Prints a dry run first: the exact paths, the count, and the total size. Asks once. Then runs.

A finding is `confirm` when the removed thing is rebuildable but the rebuild costs real time, network, or both. The dry run exists so the answer is given against a list, not against a category.

One question covers one dry run. Splitting a confirmed list into per-item questions defeats the point.

## ask

Never runs. Prints the command and the reason a person has to look.

A finding is `ask` when the removal is irreversible, when the thing holds state that nothing else holds, or when the script cannot prove that a safer class applies. Not being able to prove the class is itself a reason for this class.

## Rules that hold across the three

- A script may move a finding to a stricter class when it cannot prove the safer one. It may never move a finding to a looser class.
- A class belongs to a check id, not to a command. The same command can be `safe` in one context and `ask` in another; the check that found the target decides.
- An action that ran leaves a log row with the measure it changed. An action that was refused leaves nothing.
