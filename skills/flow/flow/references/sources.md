# Sources

Every claim about how a platform, a product, or a tool behaves has a row here with the primary source and the date it was checked. A claim with no row is labelled a heuristic in the skill that makes it, or it is left out. `python3 scripts/sources_age.py` lists rows older than 180 days.

| Claim | Where it is used | Source | Checked |
|---|---|---|---|

## Heuristics, deliberately unsourced

These are judgements this collection makes, not documented behaviour. They are named here so nobody mistakes them for facts.

- Where Claude Code stores session transcripts is an observation from this machine, not a documented interface. It can move without notice, which is why `references/tools.md` prefers a session tool over the files.
- Two failed attempts at the same fix as the point to stop is a judgement about cost, not a measured threshold.
- Seven rows as the table cap is a judgement for this theme. A status is read at a glance; a longer table is read as a list and skimmed.
- Two hours as the default end of a watch covers a pipeline and a deploy on the projects this theme was written for. A slower condition names its own end.
