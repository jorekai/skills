# 0022: Colour is a hint on a report that reads the same without it

Date: 2026-09-07

## Context

Every measuring script prints the same shape: what was measured, what it was measured against, a counting line, then the findings in level order with the costliest first inside a level. The shape is the contract, and it worked. What it did not do is help the eye. A pass over a host prints eight findings, three of which are `FAIL`, and the reader has to read every level word to find them. In a terminal that is the one thing colour does better than layout.

The risk of colour in a tool like this is that it becomes the information. A report whose severity is only visible in red is unreadable in a pipe, in a log file, in a pull request, and to anyone who does not see red. The reports here are also read by an agent, which sees escape codes as noise.

## Decision

Every script that prints a report to the console colours it, and the colour carries only what a word already carries. A level word stays a level word, an id stays an id, a cost stays a cost. Removing every escape code leaves the same report.

Colour is on only when the output is a terminal. `NO_COLOR` in the environment turns it off, `FORCE_COLOR` turns it on, and a `TERM` of `dumb` turns it off. So a pipe, a redirect, a captured test and a subagent all see plain text without asking.

The palette is closed and means the same thing in every theme: `FAIL` red, `WARN` yellow, `PASS` green, a note cyan, a heading and a check id bold, a measure and a passed list dim. Nothing else is coloured, and no colour is chosen for its looks.

## Consequences

A reader finds the three `FAIL` lines without reading the other five. That is the whole gain, and it is worth one helper of ten lines per script.

The helper is duplicated per script, like `plural` and `split_cells` before it. Each skill stays standalone, which is what lets one be copied into another collection without carrying a package.

`scripts/check.sh` runs every script through a pipe, which is not a terminal, and fails when an escape code reaches the output. The gate is the reason the rule holds: a report that colours unconditionally breaks every grep in this repository, starting with the gate itself.
