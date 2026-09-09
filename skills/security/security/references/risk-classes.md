# Risk classes and the two gates

Every action in this skill set carries exactly one class. The class is decided once, written down next to the check that finds the thing, and looked up at run time. A step never asks the model to judge in the moment whether a change is safe.

The question that decides the class is not how much the change touches. It is who has to notice when the change is wrong.

## Gate 1: a credential that is out

Above every class, for every finding under `cred.*`. A value that reached a history, a log, a build output, or a shared machine is treated as known to somebody else.

1. Rotate at the provider first. The new value goes into the secret store before the old one is removed anywhere.
2. Record the rotation with its date. Until that line exists, `cred.unrotated` keeps counting, whatever else was done.
3. Only then change the files.
4. Rewriting a history is a separate action with its own row, agreed with everyone holding a clone, because a fork and a mirror keep the old objects either way.

Removing the line and pushing is not a fix. It is the fix's fourth step performed alone, and it hides the finding from the next pass while the value keeps working.

## Gate 2: a control that can disappear quietly

Above every class, for every change to authentication, authorization, sessions, cryptography, or the rights a token carries.

1. A test exists that fails against the code as it stands.
2. The change makes that test pass, in the same commit.
3. The path that used the control is exercised once by hand, or by an existing end-to-end test.

The reason is the same one that puts a gate in front of a change to a way in on a host: the failure mode here is not something breaking loudly. It is a check that stops checking and still reads like a check. A fix nobody can prove is a proposal, and it belongs in `proposals/`.

## safe

Runs immediately. Reports afterwards what changed.

A finding is `safe` when the change is confined to a file the repository already owns, when a failing test would show it at once, and when nothing outside the repository has to move. Adding a `permissions` block and pinning an action are the two that qualify today.

## confirm

Prints the exact edit first: the files, the lines, and what the measure will read afterwards. Asks once. Then runs.

A finding is `confirm` when the change is reversible with one revert, and when the cost of getting it wrong is a broken build rather than an open door. A version bump and a lock file belong here.

One question covers one list. Splitting a confirmed list into per-item questions defeats the point.

## ask

Never runs on its own. Prints what has to happen and the reason a person has to look.

A finding is `ask` when something outside the repository has to move as well, when the change touches a control under gate 2, or when the script cannot prove that a safer class applies. Not being able to prove the class is itself a reason for this class.

## Rules that hold across the three

- A script may move a finding to a stricter class when it cannot prove the safer one. It may never move a finding to a looser class.
- A class belongs to a check id, not to a command. The same edit can be `confirm` in one repository and `ask` in another; the check that found the target decides.
- An action that ran leaves a log row with the measure it changed. An action that was refused leaves nothing.
- Nothing in this theme changes a file in a repository that holds uncommitted work. The finding is reported, and the change waits for a clean tree, so a revert stays one command.
