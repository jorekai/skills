# 0017: The profile sets the bar, the fix offers the variants

## Context

A hardening rule is not true everywhere. A host behind a control plane closes a port differently
than a bare one, and a unit option that is correct in general breaks a service that needs it. A
collection that ships one opinion is either too soft to be worth running or too hard to survive
first contact with a working machine.

Two ways to hold that open both fail. Asking at every finding gives no bar, so no measure reaches
zero and nothing can be graded. Deciding everything up front gives a bar but no room, so the first
service that needs an exception turns its finding into permanent noise.

## Decision

The bar and the fix are separate.

The bar is chosen once per host, as a named profile at setup: `baseline`, `hardened` or `paranoid`.
The profile writes values into that host's section of `standards.md`, and a blank value turns its
check off, the rule the DX workspace already follows. The bar is what every measure counts against.

The fix offers variants. A row in `references/fixes.md` carries the check id, its meaning, its risk
class and its measure. Where the fix differs between control planes, a section below the table holds
one block per plane. The person picks; the bar does not move.

Exceptions are data, not judgment: `standards.md` holds them per target with a reason, so a unit
option that breaks a service is recorded once and stops being a finding.

## Consequences

Two places to maintain, the bar and the fix, and they can drift. `scripts/check.sh` already compares
the unit a script measures in against the unit the fixes table names, which catches the drift that
matters.

`safe` is off until a host turns it on. `standards.md` carries `allow_safe: no` by default, and a
row classed `safe` falls back to `confirm` while the switch is off. A host that serves other people
changes nothing without a sentence saying so.
