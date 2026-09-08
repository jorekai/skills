# Style

Rules for every file in this repository and for every agent or person who edits it. Codex, Cursor, and Gemini read `AGENTS.md`; Claude Code reads `CLAUDE.md`, which imports it; both point here. `scripts/check.sh` enforces what a script can check and must print `ok` before a commit.

## Language

- English only: skill prose, references, templates, scripts, comments, commit messages, this file. German appears only as matching data for German-language sites (stopwords, soft-404 phrases, names of legal documents), inside a sentence that is English.
- Simplified technical English: one idea per sentence, active voice, present tense, the verb early. Around 20 words per sentence; split anything longer.
- Plain words. Say "use", not "leverage"; "big", not "extensive"; "fix", not "implement a solution for".

## Forbidden

- Em dashes. Use a comma, a colon, or a new sentence. An en dash appears in a numeric range (`8–20`, `120–160`) and inside a product string quoted verbatim ("Crawled – currently not indexed", "Discovered – currently not indexed"), nowhere else; a hyphen in a compound word is fine (`decisions/0020`).
- Arrows in prose (`→`, `->`, `=>`). Sequences are sentences ("first X, then Y") or numbered lists. Menu paths use `>`: `Performance > Compare`. Diagram edges inside a mermaid block are not prose.
- Filler and marketing: delve, leverage, seamless, robust, crucial, game-changer, unlock, "in today's", "it's worth noting", "here's the thing", "let that sink in", and their relatives. Say the fact.
- Hedging without content ("might possibly", "it could be argued"). Either the claim has a source, or it is labelled a heuristic, or it goes.
- Emoji, decorative tables, headers as decoration. A table holds data with at least two columns of it.
- Colour that carries information. A console report is coloured by the role a word already has, never instead of a word, and only when the output is a terminal (`decisions/0022`).
- Praise of the reader or the tool. No "great question", no "powerful".
- Claims about how a platform, product, or Google feature behaves without a row in that theme's `references/sources.md`, beside its router (URL and check date, verified against the primary source). Unverified means labelled as a heuristic or left out.

## Structure

- Every line in a `SKILL.md` changes behaviour; what the model does anyway goes.
- Steps end on a completion criterion ("Done when ...").
- A step carries no year, no tool name, and no platform fact. A sourced fact stands outside `## Steps`, in `## Rules`, in `## Interpretation`, or in the opening paragraph.
- Reference material sits behind a pointer to `references/`, never inline in a step.
- Tools are interchangeable and appear only in `references/tools.md`, never in a step.
- Numbers, units, ids, file names, and error strings are exact and unchanged.
- Code goes in fenced blocks; prose names a file, function, or flag only when the reader must go there.
- Headers: at most three levels. Under 500 words, no headers.
- A step that fans out (a crawl, prospecting, SERP recon, a review) sends the reading to subagents and names what comes back: the columns of one table and a word limit. The pages a subagent read stay in its context, never in the caller's.
- A step that hands findings, picks, or drafts to a person names the shape of the answer: the columns of one table, the order of the rows, and the row cap. The frame around it stands once per theme, in the router's `## Writing the answer` (`decisions/0023`). A skill whose answer is a file names the file and writes no table.

## Private data

- Nothing about a customer: no domain, brand, key, analytics id, server path, or workspace under `docs/`. Site workspaces live in a private repository per site. Examples use `example.com` and made-up brands.
- Customer names to reject sit in `.check_public.local` (gitignored, one regex per line), never in a tracked file.
- No credentials of any kind, not even for examples: `scripts/check.sh` runs gitleaks over the whole history, CI runs it on every push, and GitHub push protection blocks a push that carries a known token format.

## Commits

- Conventional prefix: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`. Subject under 72 characters, imperative, no period.
- Body says what changed and why, in the same style as this file.
- Adding, renaming, or changing a sub-skill updates the theme's router `SKILL.md` and the tables in `README.md` in the same commit.
- A release bumps `version` in that plugin's manifest and adds the entry at the top of the changelog beside it: Added, Changed, Removed, one line each, no adjectives. One version and one changelog per plugin (`decisions/0013`).
- A rule change gets a file in `decisions/` that names the context, the decision, and the consequences.
