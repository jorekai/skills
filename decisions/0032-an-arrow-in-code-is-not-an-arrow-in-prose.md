# 0032: An arrow in code is not an arrow in prose

Date: 2026-09-14

## Context

`STYLE.md` forbids arrows in prose, because a sequence is a sentence or a numbered list, and `scripts/check.sh` fails on the two ASCII spellings and on the arrow character in every tracked file except those ending in `.py`, `.sh`, `.json`, `.yaml` and `.yml`. The exception list named the file kinds the collection held at the time.

The sixth theme, `jorekai-stack`, generates a monorepo, and its templates are TypeScript and JavaScript. An arrow function is one arrow per function, and the gate read it as prose. Verified, not assumed: a template with one arrow function failed the check before this decision.

## Decision

The arrow check skips files that are code: `.py`, `.sh`, `.json`, `.yaml`, `.yml`, and now `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`. The rule in `STYLE.md` stands unchanged: an arrow in prose is still an arrow, and a `.md` template in the same directory is still checked.

## Consequences

A template's comments are prose inside a code file, and the gate no longer reads them. The writing rule holds there by review alone, the same way it holds for a comment in a Python script today.

The exception list is by extension and not by directory, so a code file anywhere in the collection is exempt and a prose file anywhere is not. Adding a language means adding its extensions here and in `check.sh` in the same commit.
