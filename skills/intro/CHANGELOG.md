# Changelog

One entry per `jorekai-intro` version. The version at the top equals `version` in `skills/intro/.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

## 0.1.1 (2026-09-08)

- Changed: the snapshot knows `jorekai-ops:recovery`, which shipped in `jorekai-ops` 0.4.0 and left the planned table.

## 0.1.0 (2026-09-08)

- Added: the theme itself. Three themes, three loops and 29 skills had no entry point that says what is here and which part a person needs. `jorekai-intro:intro` answers that one question and nothing else: it measures nothing, keeps no workspace, and writes no log row.
- Added: `scripts/catalog.py` builds the map from the collection itself: every theme with its plugin and version, every skill with who may start it, when to reach for it and what it hands back, and the skills a router calls planned. `--json` for the object, `--check` for the gate, `--theme` for one theme.
- Added: `references/catalog.json`, the generated snapshot that ships inside the plugin, so the map answers with no checkout on disk and with no other plugin installed.
- Added: `scripts/check.sh` runs `catalog.py --check` before every commit, so a skill added, renamed, or removed anywhere fails the gate until the map knows it. The map is generated, never typed, for the same reason a router may not lie.
- Added: `templates/page.html`, the page skeleton the skill fills when the session can publish one. It carries the same rows as the answer in the terminal, so nothing is lost by reading the plain one.
