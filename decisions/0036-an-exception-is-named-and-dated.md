# 0036: An exception is named and dated, and whoever enters it is not whoever needs it

Date: 2026-09-14

## Context

Every guard in a generated repository has a back door, and every agent finds it in a minute: `@ts-ignore`, `as any`, `eslint-disable`, `it.skip`, `it.only`. A guard that allows some number of these is a guard with a budget, and a budget is spent by whoever gets there first. A guard that allows none is walked around by deleting the test.

Two designs were on the table. A ratchet: the count may fall and never rise, so an old repository keeps its stock and a new one starts at zero. A list: every suppression that stays is named, with its file, its line, a reason, and a date it expires.

The ratchet is what most tools offer, and it has one hole. It answers how many, and never which. A suppression can move from one file to another without the number changing, and the person reading the number learns nothing.

## Decision

A suppression is red unless a waiver in `stack.yaml` names it: `kind`, `file`, `line`, `reason`, `until`, `owner`. A missing field voids the entry. A date that has passed voids it, whatever the reason was. `escape.type`, `escape.lint` and `escape.test` count the unnamed ones, `escape.expired` counts the ones past their date.

`stack.yaml` stands under `CODEOWNERS`, so entering a waiver is a review by a person. The agent that needs the exception is not the one that grants it. That is the whole mechanism, and it is why a soft bar stays hard.

Dead code is the one exception to the exception. Its stock in an old repository is too large for a list of names, so it has three bars instead, and an adopted repository starts with the bars at the measured count. The bars stand in the same file under the same owners, so raising one is the same review.

## Consequences

`jorekai-stack:new --adopt` proposes one waiver per suppression it finds, with the reason left blank, and an entry without a reason does not count. So an adopted repository is red on the escapes until a person has written a reason for each, and green on everything else. That is on purpose: the person writing the reason is the person who decides whether the suppression stays.

The waiver check runs before the typecheck in the gate, because it is cheap and the typecheck is not, and a suppression is found before the expensive step runs for it.
