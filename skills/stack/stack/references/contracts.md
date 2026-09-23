# Contracts: the files an agent may not change alone

A gate an agent can switch off is decoration. The files below are where a bar, a rule or a guard is defined, and every one of them has a line in `CODEOWNERS` naming a person. An agent that edits one opens a review; a person merges it. `escape.unowned` counts a file here that `CODEOWNERS` does not cover, and the placeholder owner the generator writes counts as nobody until a person replaces it.

## Contract files

| File | Why it is a contract |
|---|---|
| `stack.yaml` | the bars, the waivers, the edges, the rule classes |
| `CODEOWNERS` | the list itself |
| `rules/` | every rule and its fixtures |
| `scripts/gate.sh` | the order and the set of the guards |
| `scripts/waivers.mjs` | what counts as a suppression |
| `scripts/dead.mjs` | how dead code is counted against the bars |
| `scripts/drift.mjs` | how a generated file is proved unchanged |
| `scripts/stack-yaml.mjs` | how every other file reads the declaration |
| `lefthook.yml` | what runs before a commit |
| `.github/workflows/` | the required check |
| `tsconfig.base.json` | `strict` and what it implies |
| `eslint.config.mjs` | the complexity bars and the lint rules |
| `vitest.config.ts` | the coverage bars and the assertion requirement |
| `knip.json` | what dead code is measured over |
| `.gitleaks.toml` | what the secret scanner is allowed to pass |

## Generated files

The generator owns what it writes, and `decl.generated` counts a change made by hand (`decisions/0034`). The manifest `.stack/generated.json` carries one hash per owned file; `jorekai-stack:new --check` and `scripts/drift.mjs` recompute it. A file the project is meant to edit is not in the manifest: the contracts of the ports, the smoke tests, each rule and its test, the app.

Owned by the generator: every file in the table above except `stack.yaml`, plus `packages/env/src/schema.ts`, `packages/env/src/index.ts`, `packages/ports/src/index.ts`, `packages/ports/src/<port>/index.ts`, `packages/ports/src/<port>/memory.adapter.ts`, `packages/ports/src/<port>/wired.ts`, `packages/ports/src/<port>/<adapter>.adapter.ts`, `compose.yaml`, `.env.example`, `.nvmrc`, `pnpm-workspace.yaml`, `tsconfig.json`, `playwright.config.ts`, `.prettierrc.json`, and `README.md` in the root. `rules/` is a contract that needs an owner in `CODEOWNERS`, but inside it only the rule and its test, `rules/<id>.rule.mjs` and `rules/<id>.test.mjs`, are the project's: the engine that runs them, `rules/run.mjs` and `rules/span.mjs`, and `rules/README.md`, are generated like the rest.

A change to an owned file goes into the generator's input (`stack.yaml`, the templates of `jorekai-stack:new`) and the file is regenerated. A file the project needs to own is taken out of the manifest with `--disown <path>`, which records the path under `disowned` in the manifest so the next regeneration skips it.

## The gate

One command, `pnpm check`, which runs `scripts/gate.sh`. The order is by cost, cheapest first, so a suppression is found by the cheap step and the expensive one never runs for it:

| Step | Guard | What it reads from `stack.yaml` |
|---|---|---|
| 1 | `format` | nothing |
| 2 | `lint` | the four complexity bars, the edges under `workspaces` |
| 3 | `rules` | the rule ids; every rule's own fixtures run first |
| 4 | `waivers` | every entry under `waivers` |
| 5 | `typecheck` | nothing; `strict` stands in `tsconfig.base.json` |
| 6 | `unit` | the two coverage bars |
| 7 | `dead` | the three dead-code bars |
| 8 | `drift` | nothing; the manifest under `.stack/` |
| 9 | `secrets` | nothing |
| 10 | `browser` | nothing |

The same command runs in the pre-commit hook over the changed files and in the workflow over everything. The workflow is the required check; the hook is comfort, and `--no-verify` walks past it by design. The gate writes its own timing to `.stack/gate-times.log`, one line per full run, and `guard.slow` reads the last one.

## Artefacts under `.stack/`

The passes of this theme run nothing and read what the gate left behind. The directory is ignored by the repository, except `.stack/generated.json`, which is committed because the drift guard runs in the workflow and needs the manifest there.

| File | Written by | Read by |
|---|---|---|
| `.stack/generated.json` | `jorekai-stack:new` | `decl.generated`, `scripts/drift.mjs` |
| `.stack/gate-times.log` | `scripts/gate.sh` | `guard.slow` |
| `.stack/dead.json` | `scripts/dead.mjs` | `dead.export`, `dead.file`, `dead.dep` |
| `coverage/coverage-summary.json` | the unit runner | `guard.coverage` |

A missing artefact leaves its measure `null`. A pass that has never run is not a pass that found nothing.

## The switches `guard.disabled` reads

A closed list, so the check is the same in every repository:

| File | Switch |
|---|---|
| `tsconfig.base.json` | `"strict": false` |
| `eslint.config.mjs` | any of `complexity`, `max-lines`, `max-lines-per-function`, `max-params` set to `"off"` or `0` |
| `vitest.config.ts` | `enabled: false` under `coverage`, or `requireAssertions: false` |
| `lefthook.yml` | `skip: true`, or the `pre-commit` block removed |
| `knip.json` | an `ignore` entry that covers `packages/` or `apps/` whole |
| `scripts/gate.sh` | a step commented out or behind a flag that is not `--staged` |
