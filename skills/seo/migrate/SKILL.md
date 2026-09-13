---
name: migrate
description: "Plan and verify a domain, host, or URL migration. Inventory old URLs, map redirects, provide the owner's console steps, check every redirect, and audit the new site. Use for domain or subdomain changes, HTTPS moves, new hosts, renamed or restructured URLs, CMS replacements, or site mergers."
---

# Migration

The riskiest event in search: every URL that earns clicks either survives as a redirect or the ranking behind it is gone. Order is fixed: inventory, map, move, verify. A move measured only by "the site is up" is not measured.

Reads `docs/seo/<domain>/config.md` for the canonical host and the sitemap; writes the inventory to `audits/`, the map next to it, and rows to the log. No workspace: `jorekai-seo:setup` first, or work from the two files this skill produces.

## Steps

1. **Inventory what has to survive.** Crawl the old site into `audits/YYYY-MM-DD-premigration.json` (`jorekai-seo:tech-audit`, `--crawl` above the sitemap count), and put the pages table of a fresh export into `exports/`. The URLs with clicks or impressions are the ones a lost redirect costs; the rest follow the same rules but carry no history.
   Move already made: the old host answers a redirect on every path and the new property holds no row for it, so neither source exists. Build the inventory from the commit that changed the URLs, the old sitemap in the repository's history, internal links that still name the old host, and an export of the old property while it still has one.
   Done when the inventory exists, the report names how many URLs it holds and how many carry clicks, and, for a move already made, which of those sources it came from.

2. **Write the map.** One row per old URL in [templates/redirect-map.csv](templates/redirect-map.csv) (`old,new,note`): every URL with clicks or impressions by hand, the rest by a rule that the note names. Each target answers the same intent as its source. A target that no longer exists is not the home page: it is the nearest page that answers the same question, or a `410` when nothing does.
   Done when every URL from step 1 with clicks or impressions has a row, no row points at the home page as a fallback, and the number of rows is written down.

3. **The owner's part.** The new host needs its own property, its sitemap, the key file, and, when the domain or subdomain changes, the address change in the console. `jorekai-seo:connect` walks those clicks and writes `connections.md`.
   Done when `connections.md` names the new property and the sitemap, and the address change is either submitted or noted as not applicable with the reason.

4. **Verify the move.** After go-live, on the new host:

   ```bash
   python3 <tech-audit>/scripts/audit.py https://new.example.com/ --redirects map.csv --json > audits/YYYY-MM-DD-move.json
   ```

   Path relative to the `jorekai-seo:tech-audit` skill. Every row is fetched once: `redirects.missing`, `redirects.broken`, `redirects.wrong-target`, and `redirects.error` are FAIL, `redirects.temporary` and `redirects.chain` are WARN. Fix and rerun until zero FAIL. Then the full audit of the new site (`--crawl` above the new sitemap count) for the checks the map cannot see: internal links that still point at old URLs, the old sitemap still being served, canonicals left on the old host.
   Done when both runs show zero FAIL, and every WARN is either fixed or accepted with a reason in the report.

5. **Log and watch.** One `tech` row per fix with `verify after` 28 days, and one `tech` row for the move itself that names the two audit files. In the weekly review, read the new host's numbers against the old host's last full window, not against the week after the move.
   Done when the log holds the move row, the fix rows, and the date the move is judged on.

## Rules

- Redirects stay: Google's site-move guidance says to keep them "for as long as possible, generally at least 1 year". Removing them a month later throws away the signals the move was meant to carry.
- The address-change tool in Search Console covers a move from one domain or subdomain to another. It does not cover HTTP to HTTPS, www to non-www on the same domain, or a path change inside one domain; those need the redirects and nothing else.
- Small and medium sites move every URL at once, which is also what the guidance recommends; a large site may move in sections to keep the monitoring readable.
- Google shows the new URLs "over a few weeks or more" on a medium site and longer on a big one. A drop in the first weeks is the move being processed, not a ranking loss, and `jorekai-seo:diagnose` says the same under hypothesis 5.
- One change at a time. A domain move, a redesign, and a CMS change in one weekend cannot be told apart afterwards, and the log then learns nothing.
- 301 or 308, never 302, 303, or 307: only a permanent redirect moves the signals.
