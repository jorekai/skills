# 0025: The security workspace is its own repository, because a repository is not a machine

Date: 2026-09-09

## Context

`decisions/0015` put two themes into one private workspace: `jorekai-dx` and `jorekai-ops` both measure a machine, so one folder per host with one log folder per theme was cheaper than two trees describing the same box. A fourth theme measures a code repository, and the same argument was tried again: a repository is checked out on a machine, so its folder could sit beside the machine's.

It does not hold. A machine folder is named after a host name, and the thing it describes stops existing when the box is rebuilt. A repository is worked on from several machines, by several people, and outlives every checkout of it. A finding about a workflow file belongs to the repository, not to the laptop that happened to read it, and putting it under `machines/<hostname>/` would file the same finding twice on two machines and lose it when one of them is reinstalled.

The second reason is the reader. The dx and ops workspace is personal: one per person, holding what is true of the machines that person works on. A security finding is often shared with the people who work on that repository, and one of them will want the log without also receiving a stranger's disk usage.

## Decision

`jorekai-security` keeps its own private repository, `~/sec` in the examples and recorded during setup: `config.md`, `standards.md`, a `cache/` for downloaded catalogues, and one folder per repository under `repos/<slug>/` holding `config.md`, `audits/`, `log/security/`, `rules/`, `reports/security/` and `proposals/`.

The log folder still carries the theme name, although nothing shares this workspace today. The shape is the shape, and a second theme that ever measures a repository writes beside this one rather than into it.

Nothing this theme produces is written into the repository it measures. A findings file inside a public repository publishes the findings, and the first pass on an old repository is exactly the list an attacker would like to read.

## Consequences

A person who runs both loops keeps two private repositories and answers two `and-now` questions a week. That is the price, and it is smaller than the price of filing a repository's history under a machine that gets reinstalled.

The check id namespaces stay globally unique across the collection, as `decisions/0015` requires. `jorekai-security` owns `cred`, `build`, `dep` and `vuln`. It does not take `secret` from ops or `repo` from dx: those checks answer different questions, and both routers now say where the border runs.

A repository worked on by several people can have its workspace shared with them without sharing anything about anybody's machine.
