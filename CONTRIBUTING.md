# Contributing

Read `STYLE.md` first; it is the rulebook for every file. Then `AGENTS.md` for the editing rules and `decisions/` for the reasons behind them.

## Before a pull request

1. `bash scripts/check.sh` prints `ok`: style, private data, gitleaks, every offline test.
2. A changed or new sub-skill is reflected in the theme's router `SKILL.md` and that theme's tables in `README.md`.
3. Every new platform claim has a row in `references/sources.md` with URL and check date, verified against the primary source.
4. A new script has an offline test next to it and a line in `check.sh`.
5. The changed plugin's `version` is bumped and the changelog beside its manifest has the entry at the top.

## What a pull request needs

The template asks for the skill, the behaviour that changes, and the run that showed the need. A skill line that does not change behaviour is removed, not defended.

## What is not accepted

Customer data of any kind, tool marketing in steps, unsourced platform claims, prose that breaks `STYLE.md`, and scripts outside Python stdlib or bash.
