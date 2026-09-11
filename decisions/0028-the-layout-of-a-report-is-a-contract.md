# 0028: The layout of a report is part of the contract, and the eye reads columns before words

Date: 2026-09-11

## Context

`decisions/0022` fixed the zones of a console report and let colour hint at what a word already says. `decisions/0023` fixed the shape of the answer the agent writes back. Between the two, the layout inside a zone was never written down, and twenty scripts each chose one.

Four things came out of that. The counting line was a sentence, `2 findings to decide on, 2 notes, 0 checks passed`, so a reader had to parse it to learn there were two `FAIL` and no `WARN`. The cost of a finding stood in parentheses behind the id, `(costs 1 credential)`, where no column exists and no eye lands. The `and-now` script of one theme printed a Markdown heading and pipes while the other three printed the same facts as labelled lines. A monthly report printed five identical notes, one per tool nobody had run, where one line with a list would say the same. And a passed list ran past the width of every terminal as one line.

None of that was wrong. All of it cost the reader the seconds the report exists to save.

## Decision

Every console report keeps the four zones of `decisions/0022` and lays each one out the same way in every theme:

1. The head is two labelled lines: what ran and over what, then `measured against` and the bar. A label is a word, never a heading mark.
2. The counting line is a bar of four counts separated by a middle dot: `FAIL`, `WARN`, notes, passed, in that order. A zero count is dimmed, a count above zero carries the colour of its word.
3. A finding is one line of three columns: the level word, the check id padded to a fixed width, then the cost as one number and one unit. No parentheses, no `costs`. The message stands under it, then at most five targets, then `+N more` when the JSON holds more.
4. Identical notes fold into one line with the list that differs.
5. The passed list wraps at eighty columns and is dimmed.
6. The last zone is `next`: one line that starts with a verb, and under it, dimmed, the gate the action waits on when there is one.
7. The `and-now` report of every theme prints `stage`, then `now` as numbered lines whose first column is the skill name, then `then` as one line.

Colour stays what `decisions/0022` made it: a hint. Every rule above holds with every escape code removed, and the tests read the report through a pipe.

## Consequences

A reader finds the count of `FAIL` at the start of the bar, the cost of every finding in one column, and the next action in the last zone, without reading a sentence. That is the whole gain.

The layout is duplicated per script, like the paint helper before it, so a skill stays standalone. A test per script pins the bar and the cost column, which is what stops the next edit from drifting back into a sentence.

The routers' `## Reading a report` name the bar and the columns instead of a counting line, so the description the model reads matches what the script prints.
