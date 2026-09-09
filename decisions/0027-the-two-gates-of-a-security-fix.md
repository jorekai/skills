# 0027: A credential is rotated first, and a control changes only with a test that proves it

Date: 2026-09-09

## Context

`decisions/0012` gives every destructive action one of three classes, decided by who has to rebuild what was removed. `decisions/0016` put a second gate above them for ops, because a change to a way in can close the connection that would repair it.

A code repository has neither failure mode. Nothing here deletes work, and a wrong edit is one revert away. Two other things can still go wrong, and both are worse than a bad revert.

The first is a credential. Removing the line and pushing looks like a fix, reads like a fix in a diff, and changes nothing about a value that every clone, every fork and every mirror still holds. The finding disappears from the next pass while the value keeps working, which is the worst possible combination.

The second is a control. A change to authentication, authorization, a session, or cryptography can remove the check and leave code that still reads like a check. Nothing fails, no test goes red, and the next review sees a function whose name says it authorises.

## Decision

Two gates stand above the three classes in this theme.

Gate 1 covers every finding under `cred.*`. The value is rotated at the provider before anything in the repository is touched. The rotation is recorded with its date in the repository's `config.md`, and that record is what settles `cred.unrotated`. Only then is the tree cleaned. Rewriting the history is a separate action with its own row, agreed with everyone holding a clone.

Gate 2 covers every change to authentication, authorization, sessions, cryptography, or the rights a token carries. A test exists that fails against the code as it stands, the change makes it pass, and both are in the same commit.

## Consequences

A credential finding costs a rotation, which is work outside the repository and usually work for somebody else. That is the honest price, and the class of every `cred.*` check is `ask` for that reason.

A fix under gate 2 that nobody can write a failing test for does not run. It becomes a proposal with what is known, which is the correct outcome: a change to a control that cannot be demonstrated is a change nobody can review either.

The three classes stay as they are. The gates do not replace them, they stand in front of them, the same way the ops gate does.
