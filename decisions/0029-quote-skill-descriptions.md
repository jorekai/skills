# 0029: Quote skill descriptions

Date: 2026-09-13

## Context

The gate passed 22 skill headers that a YAML parser rejected. Each had an unquoted description containing a colon followed by a space. The catalog reader split fields at the first colon and hid the error.

## Decision

Use four fields in the skill header: `name`, `description`, `disable-model-invocation`, and `argument-hint`. Set the name to the folder name. Put descriptions and argument hints in double quotes, using JSON syntax for quotes and backslashes inside them. Write `true` or `false` without quotes. Use one field per line.

`scripts/check_frontmatter.py` checks this format before the rest of the gate. It also checks required fields, duplicate keys, and closing fences. The catalog decodes quoted text before displaying it.

## Consequences

Authors can copy the example in `STYLE.md`. A new field requires a change to the checker. The checker uses Python stdlib and validates this limited format. Quotes inside a description survive the catalog read.
