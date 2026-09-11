---
name: and-now
description: Where a domain stands in the SEO loop (setup, audit, weekly loop) and the next step, read from the workspace files alone via scripts/status.py: open log rows, verify dates due, export age, briefs without drafts, drafts not shipped, last month without a report.
disable-model-invocation: true
argument-hint: "[domain]"
---

# SEO and now?

Answers "we just did X, and now?" from `docs/seo/<domain>/` without touching the site or the network. The script reads the files; you add what only the conversation knows.

## Steps

1. **Run the status script.**

   ```bash
   python3 scripts/status.py --root docs/seo [domain]
   ```

   Path relative to this skill's directory. Without a domain it reports every folder under `docs/seo/`. Exit code 2 means no workspace: the answer is `jorekai-seo:setup`, stop here.
   Done when the report prints `stage` and a numbered `now` list.

2. **Correct the list with what the files cannot show.** Three cases, nothing else:
   - The user reports a drop in clicks, impressions, or position: `jorekai-seo:diagnose` goes to the top of the list, before any content step.
   - The user says a listed item is already done: update that log row now (Status, Applied, Verify after per `docs/seo/README.md`), or the audit or export file it points to, so the next run stops listing it. Do not carry it in your head.
   - Stage is `loop, not started` and the launch checklist in the `seo` skill's references was never walked for this domain: it comes before the first export.
   Done when every item in the list is either still open or written back to the workspace.

3. **Answer** in three parts and no more: `stage` in one line, `now` as at most three items in the script's order, each with the skill to invoke (`/jorekai-seo:<name>` in Claude Code, `$seo-<name>` in Codex) or the file to edit, and `then` with the next date-bound event. The script puts rows past their verify date first: a verdict is what makes the log learn. Invoke the next skill only when the user asks.
   Done when the user can act on item 1 without opening another file.
