# {{SLUG}}

What this repository is, and what a pass has to know before it can tell a pattern from a finding.
Each key is read as `- key: value`; a value left in parentheses is still the hint and reads blank.

- role: code (this theme measures a folder that says code, and nothing else)
- path: (the checkout this machine reads, for example ~/Developer/example/example-repo)
- origin_kind: (public, private, or vendor; who can read the history)

## Ecosystem

- languages: (comma separated, most code first)
- package_managers: (comma separated, one per manifest that is committed)
- ci: (what runs the build, or none)

## Trust model

- entrypoints: (one per entry, semicolon separated, each `kind@path`: http, cli, queue, webhook, cron)
- mitigations: (comma separated, what already escapes or binds by default in this repository)
- trusted_owners: (comma separated, workflow owners as trusted as this repository itself)

## Secrets

- secret_store: (where a value lives instead of the repository)
- rotation_runbook: (the page or command that rotates a credential of this kind)
- rotated: (one per entry, semicolon separated, `fingerprint provider YYYY-MM-DD`)

## Exceptions

- accepted: (one per entry, semicolon separated, `check-id target reason YYYY-MM-DD`)
