# Sources

One row per claim this theme makes about a platform, a catalogue, or a tool. Every row carries the primary source and the date it was checked against that source. A claim without a row is labelled a heuristic below, or it is not made.

| Claim | Source | Checked |
|---|---|---|
| The advisory database answers `POST /v1/query`, `POST /v1/querybatch` and `GET /v1/vulns/{id}`, needs no authentication, and publishes no rate limit | https://google.github.io/osv.dev/api/ | 2026-09-09 |
| The catalogue of exploited flaws is published as JSON and CSV, with `catalogVersion`, `dateReleased`, `count`, and `vulnerabilities` entries carrying `cveID`, `dateAdded`, `dueDate` and `knownRansomwareCampaignUse` | https://www.cisa.gov/known-exploited-vulnerabilities-catalog | 2026-09-09 |
| The exploitation-probability service answers at `https://api.first.org/data/v1/epss` with `cve`, `epss`, `percentile` and `date` per entry | https://www.first.org/epss/ | 2026-09-09 |
| Pinning an action to a full-length commit sha is the only way to use it as an immutable release | https://docs.github.com/en/actions/reference/security/secure-use | 2026-09-09 |
| Workflows using a privileged trigger must not check out untrusted code, including from forks | https://docs.github.com/en/actions/reference/security/secure-use | 2026-09-09 |
| Setting the default permission of the build token to read access only, and raising it per job, is the documented practice | https://docs.github.com/en/actions/reference/security/secure-use | 2026-09-09 |
| For inline scripts the documented way to handle untrusted input is an intermediate environment variable, not the expression inside the command | https://docs.github.com/en/actions/reference/security/secure-use | 2026-09-09 |
| A secret scanner writes JSON or SARIF via `--report-format`, redacts with `--redact`, takes a baseline with `--baseline-path`, and exits 1 when it finds something | https://github.com/gitleaks/gitleaks | 2026-09-09 |
| A pattern-based analyser scans with `semgrep scan --config`, writes `--json` or `--sarif`, exits 1 on findings with `--error`, and needs no account for open rule sets | https://docs.semgrep.dev/cli-reference | 2026-09-09 |
| The 2025 edition of the ten most reported application risks has ten categories over 248 weaknesses, and supply chain failures are one category of its own | https://owasp.org/Top10/2025/ | 2026-09-09 |
| A repository scoring project measures the same pipeline properties this theme's `build.*` checks measure, under the names `Dangerous-Workflow`, `Token-Permissions` and `Pinned-Dependencies` | https://github.com/ossf/scorecard/blob/main/docs/checks.md | 2026-09-09 |

## Heuristics

Not sourced, and labelled here so nothing above carries their weight.

- The workflow reader parses the subset of the format this theme needs: triggers, jobs, steps, `uses`, `run`, and `permissions`. A file using anchors, flow style, or a key this reader skips is reported as unread, never as clean.
- The entropy threshold that turns a random-looking string into a candidate is a guess tuned to produce too many candidates rather than too few. Every candidate is a name of a place to look, not proof.
- The lock file readers cover the common shape of each format. A format they cannot read produces `dep.unresolved`, so an unread file counts as a gap and not as a pass.
- The rule matcher compares text. It answers whether the sink is still written the way it was written when the rule was made, which is a weaker question than whether the code is safe, and it is the question a script can answer twice.
- Which frameworks already escape or parameterise is read from the trust model, because it depends on how the repository uses them, not on the framework alone.
