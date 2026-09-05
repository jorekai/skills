---
name: setup
description: Set up the SEO workspace for a repository: one folder per domain under docs/seo (config, connections, strategy, glossary, log, briefs, drafts, exports, audits) plus the pointer block in AGENTS.md and CLAUDE.md. Run once per repo, again when a domain is added.
disable-model-invocation: true
argument-hint: "[domain ...]"
---

# SEO setup

Scaffold the workspace every other `jorekai-seo:*` skill reads and writes. Prompt-driven: explore, present, confirm, write. The layout and log format live in [templates/workspace-README.md](templates/workspace-README.md); read it once before step 2 so the questions make sense.

## Steps

1. **Explore the repo before asking anything.**
   - Domains: `git remote -v`, existing `docs/seo/*/`, hosting and framework config (`vercel.json`, `netlify.toml`, `wrangler.toml`, `CNAME`, `site` in `astro.config.*`, `baseURL` in `hugo.toml`, `url` in `_config.yml`, `next.config.*`, `nuxt.config.*`), `Sitemap:` lines in `robots.txt`. Arguments name the domains when given; outside a repository `git remote -v` fails and the arguments or the user are the only source.
   - Content directory: where pages or posts live (`content/`, `src/content/`, `posts/`, `pages/`, `app/`).
   - Head template: grep `<title`, `rel="canonical"`, `og:title`; the file that emits them for content pages.
   - Sitemap and robots: static files, or a generator plugin and how it sets `lastmod`.
   - Static dir served at the site root (`public/`, `static/`).
   - `AGENTS.md` and `CLAUDE.md` at the root: which exist, whether either already carries an `## SEO` block.
   Done when every key in [templates/config.md](templates/config.md) has a value from the repo or is marked unknown.

2. **Present and ask, one section per message**, recommended answer first so the user can accept in a word:
   - Domains and canonical host (`https://`, `www` or bare). Several domains: one folder and one `config.md` each.
   - The unknown keys from step 1.
   - Search Console calibration: `brand_regex` (brand plus misspellings), `expected_ctr_1` (0.11 until an export says otherwise), `min_impressions`.
   - Crawler policy: recommend allowing every bot on the `ai_search_bots` line of [templates/config.md](templates/config.md); training bots are the owner's call.
   - Pointer file. `CLAUDE.md` is only `@AGENTS.md` (plus blank lines): edit `AGENTS.md` alone, the import carries the block. Both exist with own content: edit both. Only `AGENTS.md`: propose a `CLAUDE.md` containing `@AGENTS.md` (Claude Code reads `CLAUDE.md`, not `AGENTS.md`; the import shares one file). Neither: create `AGENTS.md` with the block and `CLAUDE.md` with `@AGENTS.md`.
   - `exports/` is git-ignored by the scaffold; ask only if the repo tracks `docs/` with a custom ignore scheme.
   Done when every value is confirmed or explicitly left blank.

3. **Write.**

   ```bash
   python3 scripts/scaffold.py --root docs/seo example.com [second.example]
   ```

   Path relative to this skill's directory. The script creates folders, copies templates without overwriting, regenerates the domain table in `docs/seo/README.md`, and adds `exports/.gitignore`. Then fill each `config.md` with the confirmed values and add the pointer block to the chosen root file(s), replacing an existing `## SEO` block in place:

   ```markdown
   ## SEO

   SEO workspace: `docs/seo/README.md` (layout, log format). Domains: example.com. Read `docs/seo/<domain>/config.md` before running any `jorekai-seo:*` skill; every change to the site gets a row in `docs/seo/<domain>/log/`, and the commit that makes the change ends with the trailer `SEO-Log: <row id>`.
   ```

   Claude Code reaches the skills through the installed plugin and needs no links. Codex reads `<repo>/.agents/skills/`: run `../../../scripts/link.sh <repo> seo` from this skill's directory to link every skill of this theme there, each as `seo-<name>`.
   Done when `python3 scripts/scaffold.py --root docs/seo --check` prints `ok`, every `config.md` has no unconfirmed placeholder, and the block is in place.

4. **Hand off.** Two skills finish the setup: `jorekai-seo:connect` (Search Console, sitemap, Bing, IndexNow; a wizard for the clicks only a human can make) and `jorekai-seo:grill` (niche, audience, competitors, keywords, evidence, glossary). Live site: `jorekai-seo:connect` first. Site not live yet: `jorekai-seo:grill` first.
