# 0015: One workspace, several themes, one log folder each

## Context

`jorekai-dx` measures the machine you work on. `jorekai-ops` measures a host that serves. Both
subjects are a machine, and a server carries repositories, disks and agent configuration as well.
A second workspace would give one host two folders, two logs and two `and-now`, and a finding about
free space would sit in a different tree than a finding about a certificate on the same box.

Sharing one folder creates two problems. Two tools append rows to one week file, so two sessions
can take the same row id. And an `and-now` that reads every row has to decide whether a check id it
does not know is a gap in its own theme or another theme's business.

## Decision

One private workspace repository, one folder per host under `machines/<hostname>/`, shared by every
theme. The week log splits by theme: `machines/<host>/log/<theme>/YYYY-Www.md`. Each theme reads and
writes only its own folder. Every check id belongs to exactly one theme, named in that theme's
`references/fixes.md`.

`jorekai-dx` owns `git`, `repo`, `disk`, `mem`, `container`, `ci`, `pr`, `alert`, `branch`, `agent`,
`friction`. `jorekai-ops` owns `ssh`, `key`, `sudo`, `user`, `access`, `port`, `fw`, `intrusion`,
`tls`, `panel`, `pkg`, `boot`, `os`, `plane`, `backup`, `secret`, `log`, `service`, `timer`, `unit`,
`code`, `deploy`.

## Consequences

The DX layout changes, so `jorekai-dx` goes to 2.0.0 and `scaffold.py --migrate-log` moves existing
week files down one level. Row ids stay unique inside a theme without any locking. A row whose check
id no tool measures is again a real finding, because a theme now only ever sees its own rows.

A host that runs both themes is swept twice and reports twice. That is the price of one folder per
host, and it is smaller than the price of one host in two trees.
