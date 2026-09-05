# Standards: what good looks like here

What every check measures against. A finding is the gap between this file and the machine, so a value left blank turns its check off rather than guessing a target.

## Every project

- readme: (yes: a project has a README at its root)
- ignore_file: (yes: a project has an ignore file)
- ci: (yes: a project runs checks on push)
- pointer_file: (the file a project must carry for agents, or blank)
- default_branch: (name the default branch should have)
- remote: (yes: every project has a remote it can be pushed to)

## Retention

- branch_stale_days: (a merged local branch older than this is reported)
- stash_stale_days: (a stash older than this is reported)
- image_retention_days: (a container image unused for longer is reported)
- audit_retention_months: (how long audit JSON is kept in this workspace)

## Budgets

- disk_free_min_gb: (below this, free space becomes the top finding)
- verify_window_days: (days between an applied action and its verdict)
- slow_command_seconds: (a command taking longer counts as friction)
