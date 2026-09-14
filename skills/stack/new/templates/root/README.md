# {{NAME}}

A monorepo with its guards wired so that switching one off is a review by a person, not a commit. The declaration is `stack.yaml` in this directory: the two axes, one adapter per port, the bars, the guards, the edges between packages, the rules, and the waivers. Everything else reads that file.

## The one command

```bash
pnpm check
```

It runs `scripts/gate.sh`: format, lint, the rule engine, the waiver check, the typecheck, the unit tests with coverage, dead code against the bars, drift of generated files, the secret scan, and one browser test. Cheapest first, so a suppression is found before the expensive steps run. The same command runs over the staged files before a commit, and over everything in the workflow that is the required check on the default branch.

Every failure prints the guard, the file and the line, and the allowed state. Fix the code the message names.

## What is red and why

A suppression breaks the build: `@ts-ignore`, `@ts-expect-error`, `as any`, `eslint-disable`, `.skip`, `.only`. One that has to stay is named under `waivers` in `stack.yaml` with its file, line, reason, owner and a date it expires. An entry without a reason, an owner or a date does not count, and one past its date is red again. Adding a waiver is a change to `stack.yaml`, which is under `CODEOWNERS`, so it is a review.

Dead code is not waived. It has three bars in `stack.yaml`, and raising one is a review too.

## Layout

| Path                        | What it is                                               | Owned by                                                    |
| --------------------------- | -------------------------------------------------------- | ----------------------------------------------------------- |
| `stack.yaml`                | the declaration                                          | the project, through review                                 |
| `apps/web`                  | the app, from the official generator                     | the project                                                 |
| `packages/config`           | constants such as the fetch timeout                      | the project                                                 |
| `packages/env`              | the env schema; the one place that reads the environment | the generator                                               |
| `packages/ports/src/<port>` | contract, offline adapter, wired adapter, smoke test     | contract and test by the project, adapters by the generator |
| `packages/ui`               | shared code without a framework                          | the project                                                 |
| `rules/`                    | the project's own bans, each with a test                 | the project                                                 |
| `scripts/`                  | the gate and the checks it runs                          | the generator                                               |

A file the generator owns is listed with its hash in `.stack/generated.json`; the drift guard fails when one was changed by hand. Change the generator's input instead, or take the file over with `--disown`.

## Ports

Each port has two keys in `.env.example`. While both are empty the port runs on its memory adapter, so the gate is green before any account exists, and no unit test can reach the network. `scripts/wizard.sh` walks through the accounts once they are wanted.

## The local dependency stack

```bash
docker compose up -d
```

A database, an object store and a mail catcher, the same on every target, for trying a wired adapter without an account.
