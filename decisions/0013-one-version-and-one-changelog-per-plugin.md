# 0013: One version and one changelog per plugin

Date: 2026-09-05

## Context

`decisions/0001` made the repository a marketplace with one plugin per theme, but only one theme existed. So `version` lived in the single `.claude-plugin/plugin.json` at the root, `CHANGELOG.md` sat next to it, and `scripts/check.sh` compared the two. With a second theme that shape breaks: a release of one theme would bump a version the other theme's users also receive, and the changelog would mix two products under one number.

## Decision

Each plugin owns its manifest, its version, and its changelog, and they sit together. `jorekai-seo` keeps `.claude-plugin/plugin.json` and `CHANGELOG.md` at the repository root, because its plugin source is the root. `jorekai-dx` has `skills/dx/.claude-plugin/plugin.json` and `skills/dx/CHANGELOG.md`.

`scripts/check.sh` finds every manifest and compares its version to the top entry of the changelog beside it. A release touches one plugin.

## Consequences

The version in a commit says which plugin was released. A change to a shared file, such as `README.md` or `STYLE.md`, belongs to no plugin and bumps nothing.

The marketplace's own `metadata.version` tracks the list of plugins, not their contents, so it moves when a plugin is added or removed.

Adding a third theme costs a directory, a manifest, a changelog, and a marketplace entry. Nothing at the root has to change.

Codex has no plugin namespace, so `scripts/link.sh` now names a link `<theme>-<skill>` instead of `<skill>`. Two themes carry a `setup` and an `and-now`, and a bare name let the second link overwrite the first without saying so. `decisions/0001` describes the old bare form; this is the correction.
