# 0038: The root README is an entry point, and every theme has a page of its own

Date: 2026-09-23

## Context

`README.md` held one loop diagram and one skill table per theme. With six themes it grew to 342 lines, and a reader who came for one theme scrolled past five others to find it. The first question a reader has, which theme fits what is in front of them, had no answer before the first diagram. And the shared loop, the part that makes the themes cheap to learn, stood nowhere as one picture: it had to be read out of five diagrams that differ in their details.

`scripts/check.sh` grepped the root file for every `jorekai-<theme>:<name>`, so the gate itself kept every table on one page.

## Decision

The root `README.md` is the entry point and stays short. It carries:

1. A diagram that picks a theme from what is in front of the reader, and a table that links each theme page.
2. The install lines.
3. One diagram of the loop every measuring theme shares, with a numbered list below it.
4. A table of where state lives, per theme: workspace, log file, and commit trailer.
5. The layout, use in a project, and maintenance.

Every theme has a page at `skills/<theme>/README.md` with a fixed order of sections: one line on the subject, install and start, the theme's loop diagram, the skill table, workspace and log, and read next. Each skill name in the table links to its `SKILL.md`, and each page links back to the root.

The gate follows the tables. `check.sh` looks for every sub-skill in `skills/<theme>/README.md`, fails when a theme with a router has no page, and fails when the root does not link a theme page.

## Consequences

A new theme now owes a page and a row in the root table in the same commit, and the gate says so. A new sub-skill owes a row in its theme page, not in the root.

A theme page lives inside the plugin directory, so it ships with the plugin. It is documentation, not a skill, and changing it bumps no version.

The sentence of a theme's subject appears twice, once in the root table and once as the first line of its page. That duplication is accepted, because the root table is what a reader scans and the page is what they land on.
