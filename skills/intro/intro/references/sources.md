# Sources

Every claim about how a platform, a product, or a tool behaves has a row here with the primary source and the date it was checked. A claim with no row is labelled a heuristic in the skill that makes it, or it is left out. `python3 scripts/sources_age.py` lists rows older than 180 days.

| Claim | Where it is used | Source | Checked |
|---|---|---|---|
| A marketplace is added with `claude plugin marketplace add <owner>/<repo>`, and a plugin in it is installed with `claude plugin install <plugin>@<marketplace>` | `catalog.py` builds both lines per theme, and the page prints them | https://code.claude.com/docs/en/plugin-marketplaces | 2026-09-08 |
| `claude plugin marketplace update <name>` refreshes a marketplace that was already added | The answer names it beside the install line after a release | https://code.claude.com/docs/en/plugin-marketplaces | 2026-09-08 |
| Codex reads skills from `.agents/skills/<name>/SKILL.md` under the working directory, its parent, or the repository root | `references/tools.md`, the link this collection writes for Codex | https://learn.chatgpt.com/docs/build-skills | 2026-09-08 |

## Heuristics, deliberately unsourced

These are judgements this collection makes, not documented behaviour. They are named here so nobody mistakes them for facts.

- That a session keeps the skill set it started with until it restarts is this collection's own observation, not a documented rule. It is why the answer names the install line beside the start command instead of promising the command works at once.
- The map cannot see which plugins are installed on this machine. Reading that would mean reading another product's install directory, which changes without notice, so the map names what exists and leaves the install to the reader.
- One table per theme and no row cap is a choice for this skill alone. Every other theme caps its table at five rows, because a finding list is read to decide something; a map is read to find something.
