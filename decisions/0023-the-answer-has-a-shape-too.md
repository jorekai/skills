# 0023: What the agent writes back has a shape, like the report it read

Date: 2026-09-08

## Context

`decisions/0022` finished the deterministic half of the output. Every measuring script prints the same shape, the routers say how to read it, and a gate keeps colour from carrying anything a word does not already carry.

The other half was never written down. What a script prints is not what the person sees: the agent reads the report, ranks the findings, and writes an answer. Five skills say the same sentence about that answer, `Rank the findings, do not list them`, and then say nothing about its form. So the form is invented once per session. Two runs of `jorekai-dx:repos` a week apart produce two different answers over the same JSON, a reader cannot compare them, and a table that was going to become log rows has to be rewritten first because its columns are not the log's.

Two skills had already solved it in place. `jorekai-seo:tech-audit` names four columns and an order, `jorekai-seo:review` names two headings and one line per axis. Both read the same in every session. Nothing carried that from those two skills to the rest.

## Decision

A step that hands findings, picks, or drafts to a person names the shape of the answer: the columns of one table, the order of the rows, and the row cap. A skill whose answer is a file names the file instead, and writes no table.

Each theme's router carries the frame around it under `## Writing the answer`, beside `## Reading a report`: the line before the table, the row cap, the rule that a cost is one number and one unit copied from the finding's measure, and the line after. The router also lists the columns for every sub-skill of the theme, so the skills of one theme answer alike and a new skill cannot be added without deciding.

The columns are the log's columns wherever the answer becomes log rows. A table the reader has to transpose before it can be written down is a table with the wrong columns.

## Consequences

`scripts/check.sh` fails when a theme router has no `## Writing the answer`, when a sub-skill of that theme is missing from it, and when the column line the router gives a skill stands in no line of that skill's `SKILL.md`. The last check is a duplicate kept identical on purpose, the same way a plugin version is kept identical to the top of its changelog: the router is where the theme is read as a whole, the step is where the model reads it while working.

The gate cannot judge whether the columns are the right ones. It catches the omission, which is the failure that actually happened here, and leaves the choice to review.

Colour was checkable to the escape code; this is not. A rule about prose that only a person can judge is still worth writing, because the cost of leaving it unwritten was five skills saying `do not list them` and none of them saying what to write instead.
