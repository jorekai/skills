# Question bank: the design tree

Roots first. Indented items depend on the item above them. Per node: what the agent looks up before asking, then the questions, then the default to recommend. Answers land in the named section of `stack.yaml`; the two axes and the profile are the arguments `scripts/declare.py` takes, the rest is edited into the file it wrote.

## Shape (root), writes the head

Look up: an existing `stack.yaml`, the manifests and lock file if a tree exists, the workflows, the workspace's `standards.md` for the profile, `config.md` for the owner and the forge.

- What is this: one app for one audience, or several apps that share packages? The layout is one web app and four packages either way; a second app is a line under `workspaces` later.
- Who runs it in production: you alone, a team, or a customer who takes it over? This decides the OSS level more than any preference does.
- Where are the users, and does the data have to stay in one region? This narrows the target.
Default: one app, run by the people who build it, no region constraint.

## OSS level (needs Shape), writes `oss_level`

Look up: the three levels in the router's `references/ports.md`: which ports change with the level and which stay.

- `minimal`: the managed service of the vendor whose product is the port; the fewest servers, the most accounts.
- `pragmatic`: an open library in the app process where one exists, a managed service only where running one costs a server.
- `full`: every server yours; identity, mail, analytics and errors run on a host you operate.
- Which one, and who operates the servers `full` brings?
Default: `pragmatic`, because it keeps the identity store in your own database without asking anyone to run a mail server.

## Target (needs Shape), writes `target`

Look up: the four ports the target decides in `references/ports.md`; whether an account with one of the five already exists.

- `vercel` and `cloudflare`: functions without a socket, so the database driver speaks over HTTP or a binding, and no server of yours runs there.
- `fly`, `railway`: a process that lives, so a pool and a scheduler the platform ships.
- `hetzner`: a machine you run, so a container, a pool, and a timer unit.
- Which one? If the level is `full`, is `vercel` or `cloudflare` still right, given that three servers cannot run there? (The declaration records the caveat.)
Default: `vercel` for a web app the team does not want to operate; `hetzner` when `full` was chosen.

## Bars (needs OSS level, Target), writes `gates`

Look up: the profile in `standards.md`; the ten bars and their defaults in the router's `references/declaration.md`; for an existing tree, the last coverage report and dead-code count if the gate has run.

- `strict`, `standard`, or `lenient`? Per bar, what lowering it costs: fewer covered lines means a change nobody's test sees; longer functions mean a diff nobody can review whole; more parameters mean a call nobody can read; a dead-code bar above zero means a file nobody deletes.
- Any single bar to move away from the profile, with the reason written beside it?
Default: the profile from `standards.md`; `standard` when it is blank. A bar moved by hand is a review later, so the default is the cheaper answer.

## Open decisions (needs Bars), writes `open_decisions`

Look up: nothing; these are the seven depth-3 things of the router's `references/tiers.md`.

- By when are the seven decided: admin view, blog, docs, onboarding, legal pages, notifications, contact form? One date for all, or a date each?
- Is any of the seven already decided, so its line is taken out now?
Default: one date ninety days out for all seven, the recommendation the template carries.

## Owner (needs Shape), writes `CODEOWNERS` through `--owner`

Look up: `owner` in the workspace's `config.md`; the forge handle of whoever reviews.

- Who reviews a change to a contract file: a person's handle, or a team's?
- Is that person somebody other than the agent that will work in the repository? (An owner who is the agent makes every review a self-review.)
Default: the owner from `config.md`; `@OWNER` when it is blank, which counts as nobody until replaced.

## Accounts (needs OSS level, Target), writes `human_steps`

Look up: which of the eight adapters need an account, from the resolution `declare.py --show` prints.

- Which accounts exist already, and where do their keys live? Every port runs on the memory adapter until its two keys are set, so nothing here blocks the first green gate.
- Who sets the branch protection, and when?
Default: every account created after the gate is green, one at a time, the date written into `human_steps` as each is done.
