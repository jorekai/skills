# 0021: A named skill exists, or the router says it is planned

Date: 2026-09-07

## Context

`scripts/check.sh` refuses a `jorekai-<theme>:<name>` that names no skill directory, because a router that points at nothing wastes the reader's next move. The gate read `*.md` files only. `skills/ops/and-now/scripts/status.py` named `jorekai-ops:grade` twice as the immediate next step, and that skill did not exist: the ops loop wrote rows with a verify date and had nothing that settled them. Three further names in the same file, `exposure`, `currency` and `recovery`, were deliberate: they are designed, not shipped, and the report parks a row that waits for one.

So the gate had a blind spot for scripts, and it also had no way to tell a promise from a mistake. Both had to be answered at once: widening the gate without a place to record a planned skill would have failed on the three deliberate names.

The version numbers the code carried for those releases (`0.2.0`, `0.3.0`) were a second promise nobody had committed to, and shipping any other skill first would have made them false.

## Decision

A `jorekai-<theme>:<name>` written in any tracked file names a skill directory, or that theme's router names it in a `## Planned` table. `CHANGELOG.md` and `decisions/` are history and stay exempt.

The router's table is the one place a planned skill is recorded, with the check id namespaces it will own and no release number. A report that parks a row names the skill it waits for, which is what the reader can act on, rather than a version.

## Consequences

`jorekai-ops:grade` shipped rather than being written out of the report, because the loop was the thing that was missing, not the sentence.

A theme that designs a skill before building it now has somewhere to say so, and the same table tells a reader of the router what is coming. Deleting a planned skill from the table breaks every reference to it in the same commit, which is the intended cost.
