# 0020: An en dash is allowed in a numeric range, and the gate checks it

Date: 2026-09-07

## Context

`STYLE.md` said an en dash appears "only inside a product string quoted verbatim", with `Crawled – currently not indexed` as the example. The tracked files held 43 en dashes: 5 of them that product string, and 33 numeric ranges written the way a typesetter writes them (`position 8–20`, `120–160 characters`, `3–6 words`). `scripts/check.sh` checked em dashes and never looked at en dashes, so the rule had never been true and nothing said so.

A rule the corpus contradicts is worse than no rule. It teaches a reader that the rules here are aspirations, which is the opposite of what `decisions/` exists for. Two ways out: rewrite 33 ranges as hyphens, or say what everyone was already doing and enforce that.

A hyphen in a range is ambiguous next to a hyphenated compound (`3-6 words` beside `on-page checklist`), and the range is the case an en dash is actually for.

## Decision

An en dash is allowed in exactly two places: between two numbers as a range, and inside a product string quoted verbatim. Anywhere else it is a hit, the same as an em dash.

`scripts/check.sh` strips both allowed uses from a line and reports the line when an en dash survives. The product strings are named one by one in the gate, because "any quoted string" would allow every en dash a pair of quotes fits around. Two are named today, both Search Console index states. The rule and the gate ship together, because the rule that failed here failed by not having one.

## Consequences

The 33 existing ranges stay as they are, and a new one needs no thought. An en dash used as a pause, which is the way it drifts into prose, is caught before the commit.

A range endpoint is a number or the placeholder that holds one, because a report builds its ranges in a format string. The gate reads a line at a time, so an en dash that sits on the same line as a legitimate range is still reported: the stripping removes the range, not the line. That is the safe direction to be wrong in.

Every other rule in `STYLE.md` that no script checks is a candidate for the same failure. The list of what `check.sh` covers stands in its own header, so the gap is visible rather than assumed away.
