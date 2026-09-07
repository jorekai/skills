# 0016: Two proved ways in, and a timer that undoes the change

## Context

Every other finding in this collection can be repaired from a second attempt. A change to ssh, to
the firewall, to a key file or to sudo cannot: when it is wrong, the connection that would repair it
is the connection it closed. The cost is a trip to a console at the hosting provider, and on a host
that serves other people it is an outage while nobody can log in.

A dry run does not help here. The command is correct in isolation and still locks the door, because
what breaks is the combination of the change and the one path the operator actually uses.

## Decision

A second gate sits above the three risk classes, in front of every change under `ssh.*`, `key.*`,
`fw.*`, `sudo.*` and `user.*`.

1. Two independent ways in must answer, each from a connection opened after the check began.
2. The change writes a backup copy of every file it touches.
3. The change arms a timer on the host that restores those copies after ten minutes.
4. The timer is cancelled only after a connection opened after the change succeeds.

A change that cannot arm the timer does not run. Two ways in count as independent when they share no
account and no key. A console at the hosting provider counts only when `config.md` records it and
someone has opened it at least once, because an untested console is a belief and not a path.

## Consequences

Setup creates the second way before anything hardens the first, so the two accounts come before the
first pass. Hardening on a host with one key and no console is refused, which is the correct answer:
the finding to fix first is `access.single-path`.

Every access fix costs a backup copy, a timer and one more connection. On a host that serves, that
is cheap against one hour without a way in.
