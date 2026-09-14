# 0035: The stack workspace is its own repository, and the declaration is not in it

Date: 2026-09-14

## Context

`decisions/0025` gave `jorekai-security` a private workspace of its own because a repository is not a machine, and named the price: a person who runs two loops keeps two repositories and answers two `and-now` questions a week. It also left the shape open for a second theme that measures a repository: the log folder carries the theme name, so such a theme could write beside the security one rather than into a third tree.

`jorekai-stack` measures a repository. The obvious move was to take that offer and put `repos/<slug>/log/stack/` under `~/sec`. Two things spoke against it.

The state of this theme is split by nature. The declaration, `stack.yaml`, lives in the measured repository because the project's own tooling reads it: the boundary rule, the waiver check, the bars in the linter and the unit runner. The findings live in a workspace. Under `~/sec` that split is invisible, because every other file there describes a repository from outside.

`~/sec` is built to be shared with the people who work on a repository. Somebody allowed to see a repository's holes does not need to see its provider decisions, its accounts, or which target it deploys to.

## Decision

`jorekai-stack` keeps its own private repository, `~/stack` in the examples and recorded during setup: `config.md`, `standards.md`, and one folder per repository under `repos/<slug>/` holding `config.md`, a snapshot of that repository's `stack.yaml`, `audits/`, `log/stack/`, `proposals/` and `reports/stack/`.

The declaration stays in the measured repository. It is project configuration like `tsconfig.json`, not a finding. The workspace holds a snapshot of it, written by `jorekai-stack:setup --snapshot`, and `jorekai-stack:drift` notes when the two differ.

## Consequences

The price is the one `decisions/0025` describes, paid again: a repository in two trees, two `config.md`, two `and-now` a week for somebody who runs both loops. It is not talked away here; it is what keeping the accounts apart from the holes costs.

The check id namespaces stay globally unique across the collection. `jorekai-stack` owns `decl`, `boundary`, `adapter`, `lock`, `escape`, `guard` and `dead`, and `scripts/check.sh` now fails when two themes claim one namespace, which no gate checked before this theme.
