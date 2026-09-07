# 0019: Reading and changing are different accounts

## Context

A measuring pass should run often. On the machine you work on that is free, because the pass reads
local files as you. On a host that serves, every pass arrives over the network as some account, and
if that account can change the host, then a habit of measuring often is a habit of exposing a
powerful credential often.

The host as it stands is reached as root with one key. Under that arrangement `ssh.root-login` can
never reach zero, because the tool that reports it depends on it.

## Decision

Setup creates two accounts on the host.

- `ops-scan`: a login shell, no sudo, reads only. Every measuring pass runs as this account.
- `ops-admin`: sudo for the commands the fixes table names, from one sudoers file setup writes.

Two key pairs are generated on the workstation, the public halves installed, and both accounts
proved from a fresh connection. That proof is also what gate 2 in `decisions/0016` requires, which
is why it happens before the first hardening step. Only then may direct root login be closed.

## Consequences

Two accounts, two keys and one sudoers file to maintain per host. In return a measurement carries no
privilege, so it can run on a schedule without widening anything, and `ssh.root-login` becomes a
finding that can actually reach zero.

`sudo.nopasswd` reads the sudoers file setup wrote like any other: a rule that is not in the fixes
table is a finding, including one this collection put there.
