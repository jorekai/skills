# Changelog

One entry per `jorekai-stack` version. The version at the top equals `version` in `skills/stack/.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

## 0.1.1 (2026-09-22)

- Fixed: `jorekai-stack:new` now declares `@types/pg` beside `pg` and `@types/nodemailer` beside `nodemailer`, as dev dependencies of `packages/ports`. Neither vendor module ships a type declaration of its own, so the typecheck read it as `any` and every strict rule above it reported the adapter: the first gate was red on a tree nobody had touched, for every pair whose `db` port resolves to `pool` or `hyperdrive`, and for all five `full` pairs, which carry `mail=smtp`. Proved by hand on six axis pairs that together cover all twenty-four adapters, two of them under the `strict` profile.
- Fixed: eleven functions of the generated tooling stood over the bars of the `strict` profile and under those of `standard`, so a repository declared `strict` met a red gate it had not caused. `rules/run.mjs`, `scripts/stack-yaml.mjs`, `scripts/drift.mjs`, the `s3` adapter and the `systemd-timer` adapter each carry one helper more and no function over complexity 8 or three parameters. The bracket scan of the rule engine moved into `rules/span.mjs`, which keeps `rules/run.mjs` under the file bar.
- Changed: `apply` in the rule engine takes `(rule, source, ctx)` with `source` of `text` and `path`, because four parameters stand over the bar the same engine enforces. The six generated rule tests call it the new way.

## 0.1.0 (2026-09-14)

- Added: the sixth theme, and the first that creates something. `jorekai-stack:setup` writes a private workspace of its own (`decisions/0035`), `jorekai-stack:choose` interviews for two axes and writes `stack.yaml`, `jorekai-stack:new` lays the guards over the official generator's tree, wires one adapter per port, checks the generated files it owns (`decisions/0034`), and adopts a repository that exists. `jorekai-stack:guards` measures seventeen ids over the escapes, the guards and the dead-code bars; `jorekai-stack:drift` measures thirteen over the declaration, the lock, the boundaries and the adapters. `jorekai-stack:grade`, `jorekai-stack:report` and `jorekai-stack:and-now` close the loop the way the other measuring themes do.
- Added: a suppression is red unless a waiver names it with file, line, reason, owner and a date, and `stack.yaml` stands under `CODEOWNERS` so the waiver is a review (`decisions/0036`). A rule in the generated `rules/` directory is not run without a test beside it (`decisions/0037`). An adapter is named by its file, and no reference carries a price (`decisions/0033`).
- Changed in the collection: `scripts/check.sh` exempts code files from the arrow rule (`decisions/0032`) and fails on a check id namespace two themes claim.
