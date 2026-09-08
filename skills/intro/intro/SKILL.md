---
name: intro
description: "What this collection holds and which part of it a person needs: every theme with its loop, every skill with who starts it and what it hands back, read from a generated map. Renders as a page when the session can publish one, as tables when it cannot."
disable-model-invocation: true
argument-hint: "[theme]"
---

# Intro

One question comes before every other one here: **what do you have in front of you, a site, the machine you work on, or a host that serves**. The answer names one theme, and the theme names the command that starts its loop.

## The map

[references/catalog.json](references/catalog.json) holds every theme with its plugin and version, every skill with who may start it, when to reach for it and what it hands back, and the skills a router calls designed and not built. It is generated from the collection itself and never typed, so it cannot describe a skill set that is gone. `scripts/catalog.py --check` proves it, and it runs in the gate before every commit.

The map says what exists. It cannot say what is installed on this machine, so the install line and the start command are always handed over together.

## Which theme

| What you have in front of you | Theme |
|---|---|
| A site that should be found in search | `jorekai-seo:seo` |
| The machine you work on | `jorekai-dx:dx` |
| A host that serves | `jorekai-ops:ops` |

## Steps

1. **Read the map.**

   ```bash
   python3 scripts/catalog.py [--theme NAME]
   ```

   The script path is relative to this skill's directory. `--json` returns the same map as an object, which is what a page is filled from. Exit code 2 means the map is missing: say so and stop, because every step below reads it.
   Done when every theme, its version, and its skill count stand in the report.

2. **Name the branch.** One subject from the table above, or all of them. Take it from what the user has already said; ask once when nothing in the conversation says it.
   Done when one branch is named, or all three are.

3. **Render the map.** A published page when this session can publish one, filled from [templates/page.html](templates/page.html); the tables in the answer when it cannot. Both carry the same rows in the same order, so the plain one loses nothing: `Theme | Skill | Invoked by | Hands back | Reach for it when`.
   Done when the user holds a link, or the tables.

4. **Hand over one next command.** The `entry` of the chosen theme, with the `install` line above it, because a command from a plugin nobody installed answers with nothing.
   Done when exactly one start command stands at the end of the answer.

## Writing the answer

The map is for the person, so the branch they named comes first and everything else stays behind it:

1. One line first: how many themes exist, how many skills they hold, and which branch this answer leads with.
2. One table per theme, the chosen theme first. One row per skill, in the order the map returns them, which is the order each theme chose for itself.
3. A skill a router calls planned keeps its own row, marked `planned`, and never stands among the ones that exist (`decisions/0021`).
4. One line last: the install line and the start command of the chosen theme, nothing else.

The columns, per skill:

- `jorekai-intro:intro`: `Theme | Skill | Invoked by | Hands back | Reach for it when`, one table per theme, no row cap: this is a map, not a finding list.

## Rules

- The map is generated and gated. A skill added, renamed, or removed anywhere fails the gate until the snapshot knows it, which is the rule every router already lives under.
- Nothing here measures, changes, or remembers anything. There is no workspace, no log row, no verify date, and no network call (`decisions/0024`).
- What repeats across the themes is worth more than any single skill: a findings JSON with dotted check ids, a weekly log row carrying one measure and a verify date, and a verdict that settles it. A rendering that drops that part shows a list of commands instead of a loop.
- A page carries no colour that its words do not already carry, and it names no tool.

## Reference

- The map itself: [references/catalog.json](references/catalog.json)
- What has to be true to publish a page, and what to do when nothing can: [references/tools.md](references/tools.md)
- Documented facts with source and check date: [references/sources.md](references/sources.md)
