# 0030: An unmeasured rule stays open

Date: 2026-09-13

## Context

Decision 0026 said a rule whose file disappeared needed a person. The review script also counted that rule as zero. The grader took the number, ignored the note, and wrote `won`. The monthly report then showed a fall nobody measured.

## Decision

Record each review rule's result in `measure.by`:

| Value | Meaning |
|---|---|
| `1` | The problem pattern still matches and the mitigation pattern does not. |
| `0` | The problem pattern is gone, the mitigation pattern matches, or the owner recorded the risk as accepted. |
| `null` | The rule could not be checked. |

To close a rule through a code change, read at least one matching file and every other file its path matches. A confirmed open rule stays open even when another matching file cannot be read.

A rule that cannot be checked makes its class total unknown. An unusable rule file blocks all class totals until repaired. Keep results for other rules that were checked. Rerun review when an audit lacks the rule's result. Monthly reports explain missing measurements instead of claiming a change.

## Consequences

This replaces the zero for missing paths in decision 0026. Existing audit files remain readable, but unclear rows stay open until measured again. Workflow tests run setup, review, logging, grading, and reporting together, including a moved file and a measured fix.
