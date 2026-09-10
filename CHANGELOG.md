# Changelog

One entry per plugin version. The version at the top equals `version` in `.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

## 1.11.1 (2026-09-10)

- Fixed: `jorekai-seo:tech-audit` checked the scheme of a redirect target and not of the request it made first. `_OPENER` comes from `build_opener()`, so urllib's file and ftp handlers were installed, and the audited site chose the protocol through the `Sitemap:` line of its robots.txt and through the `<loc>` values of a sitemap index. A `file://` target was opened and read; an `ftp://` target opened a connection to a host and port the site named. `fetch()` now refuses anything but http and https before it builds the request.
- Fixed: a sitemap could aim the audit at the network it runs in. The report printed whether a private address answered and with what status, which turns a public audit into a scan of the operator's own network. An address a fetched document names is now refused when it resolves to a private, loopback, link-local or reserved address; the start URL is the operator's own argument and its host stays allowed.

## 1.11.0 (2026-09-08)

- Added: what a skill hands back has a shape, beside the shape of the report it read. `jorekai-seo:seo` carries `## Writing the answer`: one line of context, one table ordered by what it costs or earns, one line with the next action, and the columns for every sub-skill of the theme. `jorekai-seo:diagnose` and `jorekai-seo:distribution` answered in no fixed form at all and now carry one; `jorekai-seo:gsc-review` and `jorekai-seo:tech-audit` name their columns as one line instead of as prose. `decisions/0023`.
- Added: `scripts/check.sh` fails when a theme router has no `## Writing the answer`, when a sub-skill of that theme is missing from it, and when the column line the router gives a skill stands in no line of that skill's `SKILL.md`. The gate catches the omission; whether the columns are the right ones stays with review.
## 1.10.0 (2026-09-07)

- Added: every script that prints a report colours it, and only when the output is a terminal. `NO_COLOR` turns it off, `FORCE_COLOR` turns it on, and removing every escape leaves the same report, so a pipe, a redirect, a captured test and a subagent read what they always read. A level word, a verdict, a check id and a measure carry the colour their role already has; nothing is coloured for its looks. `decisions/0022`.

## 1.9.1 (2026-09-04)

- Fixed: `status.py` no longer returns early when the connect wizard or the grill has not run. Unfinished setup is an item in the `now` list and the stage comes from the whole folder, so open `tech` rows, rows due for a verdict, drafts and the missing monthly report stay visible. `decisions/0010` records the rule.
- Fixed: `scaffold.py --check` names a heading a template has gained and a workspace file lacks. A `strategy.md` scaffolded before 1.8.0 has no `## Assistant prompts`, which `jorekai-seo:report` reads.
- Fixed: `scaffold.py --due` prints the row's `Then` value, the one column the verdict is measured from, and `create` prints the directories it makes.
- Fixed: `status.py` counts a review saved as `briefs/<slug>.review.md` as a review, not as a brief without a draft. `jorekai-seo:review` and the workspace README name that path.
- Changed: `jorekai-seo:connect` requires `static_dir` and `publish` only for a site inside the repository, and the IndexNow key file becomes a wizard stage when it is not.
- Changed: `jorekai-seo:migrate` step 1 names the sources for a move already made; `jorekai-seo:links` step 1 names the crawl and the export for a site outside the repository; hypothesis 5 of `jorekai-seo:diagnose` gains a check that needs no git history.
- Changed: `jorekai-seo:report` counts a log week by where most of its days fall and names the week that went to the neighbouring month; `jorekai-seo:content` re-checks dated third-party claims before a refresh moves the date.
- Changed: `audit.py` says `unique URLs` in the sitemap count, `status.py` says `1 day old`, and the `data` field of an audit item is described as per item.

## 1.9.0 (2026-09-04)

- Added: `decisions/0009` records why a verdict is measured against the median of all pages and why a row under the impression threshold gets no verdict.
- Added: `AGENTS.md` and `README.md` name the quarterly job of settling every source row older than 180 days.

- Added: `jorekai-seo:migrate`, model-invoked, for a domain, host, or URL move: inventory of what earns clicks, a redirect map, the owner's console steps, then verification until zero FAIL. The riskiest event in search had no coverage at all.
- Added: `audit.py --redirects FILE` fetches every row of a redirect map once and reports `redirects.missing`, `redirects.temporary`, `redirects.chain`, `redirects.broken`, `redirects.wrong-target`, and `redirects.error`, with a fix per id in `fixes.md`.
- Changed: the site-move source row carries the address-change scope, the "all URLs at once" guidance, and how long new URLs take to show, all checked 2026-09-04.

## 1.8.0 (2026-09-04)

- Added: `jorekai-seo:report`, user-invoked, writes `reports/YYYY-MM.md` for the site's owner from files that already exist: the month's totals and median page, every action with its verdict, visibility in AI answers, three next steps with log ids. No script of its own.
- Added: `gsc_opportunities.py` prints the site totals of both exports, so no report adds up a 1,000-row table by hand.
- Added: `references/ai-visibility.md` holds the two console reports and the rules that keep a fixed prompt set comparable; `strategy.md` and the grill question bank carry the prompt set itself.
- Added: `scaffold.py` creates `reports/`, and `status.py` names the missing report for last month.

## 1.7.0 (2026-09-04)

- Added: `audit.py` reads the JSON-LD on the page. `head.json-ld` lists the types; `head.schema-invalid` names a block that does not parse, which Google then reads none of; `head.schema-no-rich-result` names `FAQPage`, `HowTo`, and the sitelinks `SearchAction`; `head.schema-review` names a rating on a node outside the types stars are shown for, the shape a site rating itself takes.
- Added: fixes for the three new check ids, and the on-page checklist asks for markup that matches what stands on the page.
- Added: source rows for self-serving reviews, the structured-data content rules, and the feature gallery.

## 1.6.0 (2026-09-04)

- Added: `gsc_opportunities.py` prints the site baseline, the median position, CTR, and click change of every page in both exports. A verdict is the row's change minus that median, so seasonality and site-wide drift stay out of the log.
- Added: the report suggests `expected_ctr_1` from the site's own non-brand queries at position 1, with the number of queries behind it; under five queries it says so instead of suggesting.
- Added: verdict `too-small` for a row that stays under `min_impressions` in both exports. The change was never testable, and forcing `won` or `no-change` onto that data taught the log noise.
- Added: the log's `Actions` table carries `Then`, the bucket's metric and impressions at the moment the row was applied, and the `Outcomes` table carries `Baseline`. Without both the verdict was a guess.
- Changed: `gsc-review` runs the script before it grades, because grading now reads the baseline; step 5 reads the page back with `snippets.py`, so a change a cache swallowed is not logged as applied.
- Changed: `diagnose` step 2 and hypothesis 1 read the same baseline: a page that fell no further than the median page did not drop, the site did.

## 1.5.0 (2026-09-04)

- Fixed: `render.bot-html` counts the text outside `header`, `nav`, `footer`, and `aside` and looks for an empty framework mount point. A shell with a menu, a footer, and six internal links cleared every earlier rule with 364 characters of chrome; it now fails, and the message names the signals that fired.
- Fixed: `audit.py --crawl` obeys `robots.txt` and lists what it skipped under `crawl.robots-disallowed`; the URL on the command line is still fetched, because a block on it is the finding (`decisions/0007`).
- Fixed: `audit.py` and `snippets.py` follow a redirect only to `http://` or `https://`. `build_opener` installs a `FileHandler`, so a `Location: file:///...` was read into the report.
- Fixed: the crawl reads `noindex` from meta robots, meta googlebot, and the `X-Robots-Tag` header, as the page check does; a page excluded by the header no longer shows up in the duplicate and canonical findings.
- Fixed: `site.hsts` reads the header from the page's own response, not from the `robots.txt` response; an unreachable `robots.txt` reported a missing header that the site does send.
- Fixed: `snippets.py` compares content words for `title-no-query` and names the missing ones, so a natural title no longer trips the flag on `how`, `to`, and `the`.
- Fixed: `status.py` says when the log names an export that `exports/` does not hold in this checkout, and rejects a domain argument that carries a path separator.
- Fixed: `indexnow.sh` refuses a URL with a quote, a backslash, or whitespace before it builds the JSON payload.
- Added: `render.consent-wall` names the consent platform found on a page that is already thin.
- Added: `check.sh` fails when a skill directory is missing from its theme's router or from `README.md`, and when a `jorekai-<theme>:<name>` written in any tracked file names no directory.
- Added: `scaffold.py --log` prints the commit trailer `SEO-Log: <id>`; the workspace README documents it and `diagnose` hypothesis 5 reads it with `git log --grep`.
- Added: `STYLE.md` rule for steps that fan out: one named table, one word limit, the reading stays in the subagent (`decisions/0008`).
- Changed: the repository is `jorekai/skills`, so the install reads `claude plugin marketplace add jorekai/skills`; GitHub redirects the old path.
- Changed: `seo/references/remote-session.md` split into `references/session-contract.md` (the protocol, every stack) and `references/stacks/wordpress.md` (the recipes).

## 1.4.0 (2026-09-04)

- Fixed: `render.bot-html` also fires when the raw HTML holds no internal `<a href>`. Measured on 28 live URLs on 2026-09-04, a single-page app passed the character threshold with 386 characters of boilerplate and zero links; three shells now fail and eight content pages still pass.
- Added: `audit.py --rendered FILE` compares a saved rendered DOM of the audited URL against the raw fetch and names what exists only after JavaScript (`render.js-only`, `render.raw-only`), by fields, not by text.
- Added: `Page.script_srcs` counts `<script src>`, so an external bundle counts as JavaScript evidence; `script_bytes` measures inline code only.
- Changed: `content` step 2 drops the tool name and ends on a dated SERP observation with market, device, and the blocks above the organic results, or on the note that none was taken; `diagnose` hypothesis 2 leaves itself open without an earlier observation.

## 1.3.1 (2026-09-04)

- Fixed: `audit.py` no longer overwrites the request delay with the meta-refresh match, which made `time.sleep` raise on a thin page carrying a meta refresh.
- Fixed: `gsc_opportunities.py` reads a single-column CSV, so `--not-indexed` works with the URL export from the Pages report.
- Fixed: `status.py` reads the log's `id` column through `get`, like every other column, so a table without it still reports.
- Fixed: `snippets.py` reports a URL that is not `http://` or `https://` as a fetch error instead of raising on the missing status code.
- Fixed: `scaffold.py` accepts a host name only, so `..` never becomes a folder outside `--root`.
- Fixed: `link.sh` reaches "nothing matched" when a filter selects nothing, under bash 3.2 as well.
- Added: `skills/seo/setup/scripts/test_scaffold.py`; `check.sh` runs it and checks the `link.sh` empty-selection path.

## 1.3.0 (2026-09-03)

- Added: `decisions/0006-sourced-facts-outside-the-steps.md`, which supersedes the placement half of 0004: a sourced fact may stand in a `SKILL.md` outside `## Steps`, a step carries none.
- Changed: `STYLE.md`, `AGENTS.md`, and `README.md` carry one wording for that rule; `content`, `links`, `gsc-review`, and `setup` moved years, tool names, and platform facts out of their steps into `## Rules`, `## Interpretation`, or a pointer.
- Changed: `README.md` names `scripts/check.sh` and the router as `jorekai-seo:seo`; `setup` says `link.sh` writes `.agents/skills/` only; `and-now` prints `/jorekai-seo:<name>`.

## 1.2.0 (2026-09-03)

- Added: `CHANGELOG.md`, decision records under `decisions/`, `CONTRIBUTING.md`, issue and pull request templates, Dependabot for GitHub Actions.
- Added: `scripts/sources_age.py` lists rows in `references/sources.md` whose check date is older than a limit; `check.sh` warns at 180 days.
- Changed: `check.sh` verifies that the top changelog version equals the plugin version.

## 1.1.0 (2026-09-03)

- Added: `STYLE.md`, the rulebook for prose, code, commits, and private data, read by every agent through `AGENTS.md` and `CLAUDE.md`.
- Added: `scripts/check.sh` runs style, private data, gitleaks over the history, then every offline test; CI runs it on every push.
- Added: MIT license, plugin metadata (repository, homepage, license), marketplace owner.
- Changed: arrows left the prose; sequences are sentences, menu paths use `>`.

## 1.0.1 (2026-09-03)

- Changed: customer patterns for the private-data gate moved to the gitignored `.check_public.local`.
- Removed: the site workspace under `docs/`; it lives in a private repository per site. History rewritten to drop it.

## 1.0.0 (2026-09-03)

- Added: plugin `jorekai-seo` with the skills `seo` (router), `setup`, `connect`, `grill`, `tech-audit`, `gsc-review`, `content`, `review`, `links`, `distribution`, `diagnose`, `and-now`. Invocation `/jorekai-seo:<name>`.
