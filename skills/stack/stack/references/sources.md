# Sources

One row per claim this theme makes about a platform, a generator, a lock format, or a tool. Every row carries the primary source and the date it was checked against that source. A claim without a row is labelled a heuristic below, or it is not made. Nothing here is about a price, a free tier, or a limit.

| Claim | Source | Checked |
|---|---|---|
| The lock file of the package manager carries an `importers` map with one entry per workspace package, each listing its dependencies with their resolved versions | https://pnpm.io/lockfile | 2026-09-14 |
| The `packageManager` field of the root manifest pins the package manager and its version, and `corepack` reads it | https://github.com/nodejs/corepack#readme | 2026-09-14 |
| The unit runner reads coverage thresholds under `coverage.thresholds` and fails the run when a threshold is not met | https://vitest.dev/config/coverage#coverage-thresholds | 2026-09-14 |
| The unit runner fails a test that ran no assertion when `expect.requireAssertions` is set | https://vitest.dev/config/expect | 2026-09-14 |
| The `json-summary` coverage reporter writes `coverage/coverage-summary.json` with `total.lines.pct` and `total.branches.pct` | https://istanbul.js.org/docs/advanced/alternative-reporters/#json-summary | 2026-09-14 |
| The linter ships `complexity` as a core rule that takes a number | https://eslint.org/docs/latest/rules/complexity | 2026-09-14 |
| The linter ships `max-lines` as a core rule that takes a number | https://eslint.org/docs/latest/rules/max-lines | 2026-09-14 |
| The linter ships `max-lines-per-function` as a core rule that takes a number | https://eslint.org/docs/latest/rules/max-lines-per-function | 2026-09-14 |
| The linter ships `max-params` as a core rule that takes a number | https://eslint.org/docs/latest/rules/max-params | 2026-09-14 |
| The type-aware `no-floating-promises` rule reports a promise-returning call whose result is neither awaited, returned, voided nor assigned | https://typescript-eslint.io/rules/no-floating-promises/ | 2026-09-14 |
| The dead-code tool reports unused files, exports and dependencies and writes JSON with `--reporter json` | https://knip.dev/reference/cli | 2026-09-14 |
| The hook runner reads `lefthook.yml` and runs a `pre-commit` command over `{staged_files}` | https://lefthook.dev/configuration/run/ | 2026-09-14 |
| `skip` on a hook or on a command of the hook runner turns it off | https://lefthook.dev/configuration/skip/ | 2026-09-14 |
| The secret scanner reads the whole history with `gitleaks git`, redacts with `--redact`, and exits 1 when it finds something | https://github.com/gitleaks/gitleaks | 2026-09-14 |
| A branch protection rule names required status checks by their check name, and a pull request cannot merge while a required check is missing or failing | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches | 2026-09-14 |
| The `CODEOWNERS` file at the repository root, under `.github/`, or under `docs/` names owners per path pattern, and a pull request touching a matched path asks the owner for review when review from code owners is required | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners | 2026-09-14 |
| The app generator takes `--ts`, `--eslint`, `--app`, `--src-dir`, `--import-alias`, `--use-pnpm`, `--skip-install`, `--no-tailwind`, `--webpack`, `--disable-git`, `--no-agents-md` and `--yes` as flags, and `--yes` answers every remaining prompt with the default | https://nextjs.org/docs/app/api-reference/cli/create-next-app | 2026-09-14 |
| Cron jobs on the first target are declared under `crons` in `vercel.json`, each with `path` and `schedule`, and the platform calls the path | https://vercel.com/docs/cron-jobs/quickstart | 2026-09-14 |
| Cron triggers on the second target are declared under `triggers.crons` in the worker's configuration, and the worker receives a `scheduled` event | https://developers.cloudflare.com/workers/configuration/cron-triggers/ | 2026-09-14 |
| The second target pools connections to an external database through a binding, and the app reads the pooled connection string from that binding | https://developers.cloudflare.com/hyperdrive/get-started/ | 2026-09-14 |
| The third target runs a machine on a schedule with `fly machine run --schedule`, taking `hourly`, `daily`, `weekly` or `monthly` | https://fly.io/docs/machines/flyctl/fly-machine-run/ | 2026-09-14 |
| The third target's object store speaks the S3 API, with a bucket name, an endpoint and a key pair | https://www.tigrisdata.com/docs/ | 2026-09-14 |
| The fifth target runs a service on a cron schedule set on the service, and the service exits when the run is done | https://docs.railway.com/reference/cron-jobs | 2026-09-14 |
| A systemd timer unit with `OnCalendar` starts a service unit of the same name on that schedule | https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html | 2026-09-14 |
| The serverless driver for the first target's database speaks over HTTP and takes the connection string from the environment | https://neon.com/docs/serverless/serverless-driver | 2026-09-14 |
| The first target's blob store takes its token from `BLOB_READ_WRITE_TOKEN` by default and accepts `token` as an option on every call | https://vercel.com/docs/vercel-blob/using-blob-sdk | 2026-09-14 |
| The second target's object store speaks the S3 API at an account endpoint | https://developers.cloudflare.com/r2/api/s3/api/ | 2026-09-14 |
| The second target's object store is reached with an access key id and a secret access key | https://developers.cloudflare.com/r2/api/tokens/ | 2026-09-14 |
| The managed identity provider offers a backend client that verifies a session token from a secret key | https://clerk.com/docs/references/backend/overview | 2026-09-14 |
| The open authentication library runs in the app process with a database adapter and a secret from the environment | https://www.better-auth.com/docs/installation | 2026-09-14 |
| The mail API accepts `POST /emails` with `from`, `to`, `subject` and `text`, authenticated by a bearer token | https://resend.com/docs/api-reference/emails/send-email | 2026-09-14 |
| The analytics ingest accepts `POST /i/v0/e/` with `api_key`, `event`, `distinct_id` and `properties`, on the cloud host or on a self-hosted one | https://posthog.com/docs/api/capture | 2026-09-14 |
| The error tracker's client is configured by a DSN, and the host is one component of it | https://docs.sentry.io/concepts/key-terms/dsn-explainer/ | 2026-09-14 |
| A branch protection's response nests `required_status_checks.contexts` as a list, `enforce_admins` as `{url, enabled}`, and `required_pull_request_reviews.require_code_owner_reviews` as a boolean; the same three names are what the update endpoint takes | https://docs.github.com/en/rest/branches/branch-protection | 2026-09-23 |
| Each gitleaks release publishes `gitleaks_<version>_checksums.txt` beside the archives, one `sha256sum`-format line per archive | https://github.com/gitleaks/gitleaks/releases | 2026-09-23 |

## Heuristics

Not sourced, and labelled here so nothing above carries their weight.

- The declaration reader parses the subset of the format the checks need. A file using anchors, a second document, or a tab in its indentation is reported as unread, never as clean.
- `no-floating-promise` and `no-test-without-assertion` in the rule engine are text rules, and `guard.assertionless` counts with the same text rule. A call that returns a promise under another name, or an assertion helper that does not spell `expect(`, is not seen. The type-aware linter rule and the runner's assertion requirement are the twins that catch what the text rule cannot.
- The import scanner reads `import` and `export ... from` lines and dynamic `import(` with a string literal. An import built from a variable is not an edge.
- The suppression scanner counts `@ts-ignore`, `@ts-expect-error`, `as any`, `eslint-disable` in every spelling, and `.skip` and `.only` on `it`, `test` and `describe`. Another spelling of the same escape is not counted, and adding one to the list is a change to `scripts/waivers.mjs` in the generated repository and to the scanner in `jorekai-stack:guards` in the same commit.
- The adapter table is an opinion about which adapter fits which axis value today, not a fact about a platform. A row moves when a better fit exists, and a repository that disagrees records a port exception.
- `guard.slow` reads the last full run the gate wrote. A gate that ran with `--staged` writes no line, so the measure describes the workflow's run, not the hook's.
