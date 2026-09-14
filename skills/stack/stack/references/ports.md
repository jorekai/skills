# Ports and adapters

Eight ports. Each hangs on exactly one of the two axes, so fifteen axis pairs resolve through eighteen table rows and not fifteen trees. The core around the ports is the same in every pair and is not configurable: the workspace layout, strict TypeScript, the formatter, the linter, the rule engine, the unit runner, the browser runner, the hooks, the secret scan, the workflows, the bars, the env schema, the local dependency stack in `compose.yaml`, and `CODEOWNERS`.

An adapter name is a file name, `packages/ports/src/<port>/<adapter>.adapter.ts`, and it names the protocol or the vendor the file talks to, never a product line (`decisions/0033`). Nothing here carries a price, a free tier, or a limit: an adapter name is an opinion, a price would be a platform fact with a source that ages every month.

## The axes

| Axis | Values | What it decides |
|---|---|---|
| `oss_level` | `minimal`, `pragmatic`, `full` | Whose server holds the identity store, delivers the mail, receives the events and the errors |
| `target` | `vercel`, `cloudflare`, `fly`, `hetzner`, `railway` | Where the app runs, and with it the database driver, the object store, and the scheduler |

`minimal` takes the managed service of the vendor whose product is the port. `pragmatic` takes an open library in the app process and a managed service only where running one costs a server. `full` runs every server itself, which is a caveat on `vercel` and `cloudflare`: the three servers of mail, analytics and errors cannot run there, and `oss_caveat` in `stack.yaml` says where they run instead.

## Ports decided by the target

| Port | `vercel` | `cloudflare` | `fly` | `hetzner` | `railway` |
|---|---|---|---|---|---|
| `db` | `neon-http` | `hyperdrive` | `pool` | `pool` | `pool` |
| `storage` | `vercel-blob` | `r2` | `tigris` | `s3` | `s3` |
| `jobs` | `vercel-cron` | `worker-cron` | `machine-schedule` | `systemd-timer` | `railway-cron` |
| `host` | `vercel` | `workers` | `fly` | `docker` | `railway` |

The engine behind `db` is the same everywhere; the three adapters differ in how a connection reaches it: over HTTP from a function that owns no socket, through a binding that pools for a worker, or through a pool in a process that lives. `storage` speaks one object protocol everywhere; the four adapters differ in the endpoint and in what carries the credential. `jobs` names the scheduler each runtime already ships, because a second scheduler costs a server. `host` is the target.

One override: `storage` resolves to `s3` under `oss_level: full` on every target, because the generic client is the one that talks to a store the project runs itself.

## Ports decided by the OSS level

| Port | `minimal` | `pragmatic` | `full` |
|---|---|---|---|
| `auth` | `clerk` | `better-auth` | `better-auth` |
| `mail` | `resend` | `resend` | `smtp` |
| `analytics` | `posthog` | `posthog` | `posthog` |
| `errors` | `sentry` | `sentry` | `sentry` |

`auth` runs in the app process on every target; the level decides whose identity store it talks to. `mail` has one transport and one sender everywhere; the level decides whose delivery. `analytics` and `errors` are one client and one ingest address each; the level decides whose server the address points at, so the adapter is the same file and the difference is the value of `ANALYTICS_URL` and `ERRORS_URL`.

## The offline adapter

Every port carries a ninth adapter, `memory.adapter.ts`, which the declaration never names. The env schema resolves a port to it while both keys of that port are empty. It carries four things at once: the gate is green before any account exists, the eight smoke tests run without the network, a unit test cannot reach the network by accident, and `scripts/check.sh` in this collection proves the whole tree offline.

## The env keys

Two keys per port, sixteen in all, every one optional. A port whose two keys are both empty resolves to `memory`. The names stand in `packages/env/src/schema.ts` and in `.env.example`, and `jorekai-stack:drift` checks both against this table.

| Port | Keys | What the wired adapter reads from them |
|---|---|---|
| `db` | `DB_URL`, `DB_KEY` | the connection string; the binding name for `hyperdrive` |
| `storage` | `STORAGE_URL`, `STORAGE_KEY` | `s3://<bucket>@<endpoint>` and `<access key id>:<secret>`; `vercel-blob` reads the token from `STORAGE_KEY` alone |
| `jobs` | `JOBS_URL`, `JOBS_KEY` | the address the scheduler calls, and the secret it sends |
| `host` | `HOST_URL`, `HOST_KEY` | the public address, and the deploy token where the target takes one |
| `auth` | `AUTH_URL`, `AUTH_KEY` | the issuer, and the signing or API secret |
| `mail` | `MAIL_URL`, `MAIL_KEY` | `https://` for an API, `smtp://` for a relay, and the credential |
| `analytics` | `ANALYTICS_URL`, `ANALYTICS_KEY` | the ingest address and the project key |
| `errors` | `ERRORS_URL`, `ERRORS_KEY` | the DSN; the second key is unused and stays for the shape |

A value in `.env.example` reads `(set in the secret store)`, never a sample that looks like a key, because the secret scanner reads the whole history.

## The vendor modules

The modules an adapter may import and nothing else may. `no-vendor-outside-adapter` in the rule engine and `adapter.bypassed` in `jorekai-stack:drift` read the same list.

| Module | Adapter |
|---|---|
| `@neondatabase/serverless` | `db/neon-http` |
| `pg` | `db/pool`, `db/hyperdrive` |
| `@vercel/blob` | `storage/vercel-blob` |
| `@aws-sdk/client-s3` | `storage/r2`, `storage/tigris`, `storage/s3` |
| `@clerk/backend` | `auth/clerk` |
| `better-auth` | `auth/better-auth` |
| `nodemailer` | `mail/smtp` |
| `@sentry/node` | `errors/sentry` |

`mail/resend`, `analytics/posthog` and every `jobs` and `host` adapter use `fetch` with a timeout from `@app/config` and import no vendor module.

## The parts of a port

Every port under `packages/ports/src/<port>/` has four parts, and `adapter.missing` counts a missing one:

| Part | File | Owned by |
|---|---|---|
| The contract | `contract.ts` | the project |
| The offline adapter | `memory.adapter.ts` | the generator |
| The wired adapter | `wired.ts`, which re-exports one `<adapter>.adapter.ts` | the generator; `--wire` rewrites it |
| The smoke test | `smoke.test.ts` | the project |

`index.ts` chooses between the two at start-up by asking `@app/env` which adapter the keys resolve to, and it is the only file another package imports: `@app/ports/<port>`.
