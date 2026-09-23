# 0039: Gate 2 also covers a port and a panel

Date: 2026-09-23

## Context

`decisions/0016` named gate 2's namespaces: `ssh.*`, `key.*`, `fw.*`, `sudo.*` and `user.*`. The
fixes table already went further on its own: the row for `port.world-open`, `port.unexpected` and
`panel.exposed` says "Gate 2 applies to every one of these, because a port that is closed by hand
is closed for the connection reading this report as well". Nothing else agreed with it. The
`GATE_PREFIXES` constant in `access.py`, `availability.py`, `exposure.py` and `recovery.py`, the
sentence in `AGENTS.md`, and step 3 of the exposure skill all stopped at the five namespaces of
`decisions/0016` and never read a port or a panel as a way in. A person or an agent who acted on the
fixes table did the right thing; the gate that should have stopped them and asked for two ways in
first never ran, because the check for its own namespace did not know to look.

The risk is the same one `decisions/0016` named: closing a port by hand, or restricting a panel to
one address by hand, can close the connection doing it, exactly as a firewall rule can. A dry run
does not help here either, for the same reason: the command is correct in isolation and still locks
the door when it is the one path the operator uses.

## Decision

Gate 2 covers `port.*` and `panel.*` in addition to the five namespaces `decisions/0016` named. The
rule itself does not change: two independent ways in, each proved from a connection opened after
the check began; a backup copy of every file or rule the change touches; a rollback timer armed
before the change runs and cancelled only after a fresh connection succeeds.

`port.unexpected` sits on the tidiness rung of the priority ladder, the lowest one, and still runs
under the gate: the fix is the same action, closing or rebinding a port, whatever rung ranks it, and
the connection it can take away does not wait for the ladder before it closes.

## Consequences

`GATE_PREFIXES` in `access.py`, `availability.py`, `exposure.py` and `recovery.py` reads
`("ssh.", "key.", "fw.", "sudo.", "user.", "port.", "panel.")`. `references/risk-classes.md`,
`AGENTS.md`, and the exposure skill's steps name the same seven namespaces, so a reader of any one
of them sees the same gate the others enforce. This replaces no rule of `decisions/0016`, which
stays as it was written; it widens the set of namespaces the gate it defined runs in front of.
