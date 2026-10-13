# 0040: A theme may steer a session, and then it measures nothing

Date: 2026-10-13

## Context

Two months of session transcripts show the same short requests again and again: go on alone, continue from the last session, push and deploy, merge when green, tell me when it is done, where do we stand, write a handoff. Each one is typed with its limits every time: "autonomous", "clean and tested", "you may push".

`decisions/0024` exempts a theme from the measuring shapes only when its subject is the collection itself. A theme that steers a session has a different subject, the session in front of it, but the same property: nothing it does leaves state on disk that a later run could measure. A findings JSON, a log row, and a `grade` skill would count nothing.

Short requests also split into two kinds. Some only change how a session behaves, always: test before saying done, ask questions once and numbered. Those belong in the person's own agent instructions, not in a skill. The others are triggered and carry a procedure or a grant for one occasion. Only those become commands.

## Decision

`jorekai-flow` is a theme whose subject is the working session. It carries no findings JSON, no log folder, no verify date, no `grade` skill, and no `and-now`, for the same reason `decisions/0024` gives: there is nothing to count between two runs.

Every command answers one of two questions, never both: where the context comes from (`resume`), or how far the agent may run (`go`, `ship`). Each command grants exactly what the router's `## Grants` table names. Push, merge, and deploy sit in `ship` alone, so no session gains them by accident.

A behaviour that should hold in every session is not a command. It stays in the person's own instructions, outside this public collection.

## Consequences

The exemption grows from one subject to two, and stays tied to the subject: a theme that changes a machine, a host, or a repository and could measure the change still writes the row.

The router carries a `## Grants` table in place of a priority ladder. A change to what a command may do is a change to that table, and it bumps the plugin version like any skill change.
