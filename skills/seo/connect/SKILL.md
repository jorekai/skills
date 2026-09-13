---
name: connect
description: "Create a bash wizard for connecting a domain to Search Console, submitting its sitemap, and importing it into Bing Webmaster Tools. It also walks the owner through hosting an IndexNow key and records results in the SEO workspace."
disable-model-invocation: true
argument-hint: "[domain]"
---

# SEO connect

A **wizard** is a bash script that walks a human through the clicks only a human can make: it opens each URL, says what to click and copy, checks what it can check itself, and records every result in `docs/seo/<domain>/connections.md`. The library in [templates/wizard.sh](templates/wizard.sh) is fixed (stages, prompts, `record`, `http_status`); this skill only scopes the procedure and writes the stages.

Needs the workspace from `jorekai-seo:setup`: `config.md` with `canonical_host` and `sitemap`, plus `static_dir` and `publish` when the site is in this repository. Missing: run `jorekai-seo:setup` first.

## Steps

1. **Scope.** Read `config.md` and `connections.md` for the domain. Every key in `connections.md` that already holds a value is a stage to skip unless the user wants it redone. Present the ordered stage list from [references/stages.md](references/stages.md) with what each records, and confirm.
   Done when the user has approved the list and every stage names the key(s) it records.

2. **Do the agent's part before the wizard.** Nothing in the wizard may depend on the agent's work being unfinished:
   - Sitemap and robots reachable: `curl -sI <sitemap URL>` returns 200 with an XML content type; `robots.txt` lists the sitemap.
   - IndexNow: generate a key with `python3 -c "import secrets; print(secrets.token_hex(16))"`, write `<static_dir>/<key>.txt` containing exactly the key, deploy (or tell the user to). The key must be reachable at `https://<host>/<key>.txt`. Site not in this repository (`static_dir` blank): the agent writes no file, and the key file becomes a stage that prints the key, names where it goes on the server, and checks the URL before the test submission.
   - AI-search crawlers: `robots.txt` matches `ai_search_bots` in `config.md`; fix the file if it does not.
   Done when each check passed or is listed as a stage the human must finish.

3. **Author the wizard.** Copy `templates/wizard.sh` to `docs/seo/<domain>/connect.sh`, set `CONNECTIONS`, replace the example stage with one `stage` per approved step in the order of stages.md, and set `TOTAL_STAGES`. Use only the library helpers (`stage`, `say`, `step`, `note`, `open_url`, `pause`, `confirm`, `ask`, `record`, `skip`, `http_status`, `today`). Fork on `confirm` and derive the recorded values from the choice; `ask` only for a value the agent cannot derive, never two `ask` prompts in a row (people answer the wrong one). The library above the marker stays byte-identical.
   Done when `bash -n docs/seo/<domain>/connect.sh` passes and every key named in step 1 is recorded by exactly one stage.

4. **Hand over.** `chmod +x`, then tell the user to run it:

   ```bash
   bash docs/seo/<domain>/connect.sh
   ```

   The wizard opens browsers and blocks on input, so the agent never runs it. After the run: read `connections.md`, confirm the IndexNow test returned 200 or 202 and the sitemap shows `Success`, and append one `tech` row to the week's log (`scaffold.py <domain> --log` in `jorekai-seo:setup` gives the path and id). Keep `connect.sh` in the folder; it is re-runnable for a new property or a re-verification.

## After the setup

Changed URLs go to IndexNow through `scripts/indexnow.sh <domain> URL [URL ...]` (reads `INDEXNOW_KEY_FILE` from `connections.md`, checks the key file first, one POST for all URLs, prints the status code with its meaning). `jorekai-seo:gsc-review`, `jorekai-seo:content`, and `jorekai-seo:tech-audit` call it after a change is live; Google is not an IndexNow participant, so "Request indexing" in Search Console stays the owner's click.
