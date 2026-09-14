# 0037: A rule without a test is not run

Date: 2026-09-14

## Context

A standard linter knows the language and not the repository. The boundary between `packages/ui` and `packages/ports`, the rule that a vendor module is imported by its adapter and nowhere else, the rule that a network call carries a timeout: none of these is a rule any linter ships, and each is the kind of thing an agent learns once per session and forgets.

`jorekai-stack` gives a generated repository a `rules/` directory for that, and the gate runs it. The risk of a rule engine in a project is a rule that looks like a lock and catches nothing: a pattern with a typo, a glob that matches no file, a message that names the wrong place. Everybody believes the branch is defended, and it is not. That is worse than no rule, because no rule makes nobody believe anything.

## Decision

Every rule is one file with four required parts: an id, a pattern, a message that names the place and the allowed state, and a test beside it holding two fixtures, one that must match and one that must not. The runner refuses a rule whose test is missing or fails, and it runs the tests before the rules on every gate.

`guard.rulegap` in `jorekai-stack:guards` counts the same gap statically: an id the declaration names with no rule file or no test file. So the gap is found by the pass even when the gate was skipped.

The message is part of the rule and not decoration. `boundary violation in packages/ui` makes an agent guess; `packages/ui/src/index.ts:3 imports @app/ports, allowed from packages/ui: @app/config` makes it correct the line. A rule whose message does not name the allowed state is a rule an agent works around instead of obeying.

## Consequences

Adding a rule costs two files and a line in `stack.yaml`, which is a review. That cost is the point: a rule is a contract, and a contract nobody proved is a proposal.

The starting set of six rules is generated with its tests and follows from the declaration; nothing in it is invented for the sake of having rules. The two text rules among them, for a floating promise and for a test without an assertion, are heuristics with a type-aware or runtime twin elsewhere in the gate, and `sources.md` says so.
