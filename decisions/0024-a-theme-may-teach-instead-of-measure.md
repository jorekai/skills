# 0024: A theme may teach instead of measure, and then it owes a map nobody types

Date: 2026-09-08

## Context

Three themes shared one set of shapes, and that is what made the third one cheap: a findings JSON with dotted check ids, a weekly log row with one measure and a verify date, a `grade` skill that settles the row, an `and-now` that reads the workspace, and a router that says how to read the report and how to write the answer.

None of that fits the question a person asks first. Twenty-nine skills, three plugins, three loops, and nothing in the collection says out loud what is here and which part someone needs. `README.md` says it, but it lives on a forge, opens with the writing rules, and answers nothing about the session the reader is sitting in.

A skill that answers that question measures nothing. It has no subject on disk to audit, no cost to count, no fix to apply, and so no row to write and no date to come back to. Written under the existing shapes it would have to invent a measure for a question that has none.

The second risk is worse than the first. An overview is the one document that ages without anyone noticing: every other file in a theme is read while the work happens, so a wrong line gets caught. A map is read once, by the person who knows the least, and a map that names a skill that was renamed last month teaches the wrong thing to exactly the reader who cannot tell.

## Decision

A theme whose subject is the collection itself carries no findings JSON, no log folder, no verify date, no `grade` skill, and no `and-now`. It is not a loop, so it borrows none of the parts that exist to close one.

What it owes instead is that its content is generated and gated. `skills/intro/intro/scripts/catalog.py` builds the map from files the repository already keeps: the frontmatter of every `SKILL.md`, each router's sub-skill, planned, and answer tables, the plugin manifests, and the marketplace file. The result ships as `references/catalog.json`, so the plugin answers with no checkout on disk and with no other plugin installed. `catalog.py --check` compares that snapshot to the checkout and runs in `scripts/check.sh`.

The shapes it does keep are the ones that have nothing to do with measuring: a `SKILL.md` of a thesis line, `## Steps` ending on `Done when`, then `## Rules`; a script that is stdlib only, prints its docstring as `--help`, offers `--json`, exits 0, and paints only a terminal; a router section that says what the answer looks like.

## Consequences

`scripts/check.sh` gains `catalog.py --check`. Adding, renaming, or removing a skill anywhere now fails the gate until the snapshot is regenerated in the same commit, which is the rule the routers and `README.md` already live under, applied to a fourth place.

The gate is stricter than the ones before it, because this one compares generated output and not a mention. A rename that a router and this file both survive still stops the commit, and the fix is one command, not an edit.

This decision does not open the door to a theme that measures something and skips the log. The exemption is tied to the subject: the collection has no state that can move between two runs, so there is nothing a measure could count.
