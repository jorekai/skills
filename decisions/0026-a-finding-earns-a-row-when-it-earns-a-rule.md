# 0026: A finding earns a log row when it earns a check that recomputes it

Date: 2026-09-09

## Context

Every theme here promises the same loop: an action gets a measure and a verify date, and at that date the same script recomputes the measure and writes a verdict. Three themes could keep that promise because every finding came from a script in the first place.

A security review does not. The findings that matter most in a code repository, an authorization check that is missing, a value that reaches a query unbound, a deserializer fed from a request, are found by reading code and reasoning about it. A model finds them. A model asked the same question three weeks later gives an answer that is close but not the same, and a verdict computed from two answers that are close is a verdict nobody can defend. Grading a review by re-running the review makes the log a record of two opinions.

The alternatives were to leave the review out of the loop, which drops the most valuable half of the theme, or to let those rows carry a verdict a person types, which is the free-text measure `decisions/0014` was written to remove.

## Decision

A finding from `jorekai-security:review` earns a log row when it earns a rule. Every accepted finding is written into the workspace as `repos/<slug>/rules/<check id>-<n>.json`: the check id, a path glob, the text of the sink as a regular expression, optionally the text that would mean it is handled, plus the reason, the date, and the commit it was written against.

`scripts/review.py` reads those rules and counts the ones that are still open, per class. That count is the measure, so the model answers the strong question once and the script answers a weaker question twice: is the sink still written the way it was written when somebody looked.

A verified finding that cannot be written as a rule keeps its evidence and goes to `proposals/`. It is not a log row, because nothing would settle it.

## Consequences

The review becomes part of the loop instead of a report beside it, and the workspace accumulates a rule set that describes this repository and no other.

The measure is weaker than the finding, and the theme says so in the open. A rule can be satisfied by a rename that leaves the flaw in place, and a rule whose path matches no file reads zero although the file may only have moved. Both cases are reported as needing a person rather than being scored.

A finding nobody can turn into a check is visible as exactly that. That is a useful signal in itself: it usually means the finding is about a design and not about a line, and a design is not settled at a verify date.
