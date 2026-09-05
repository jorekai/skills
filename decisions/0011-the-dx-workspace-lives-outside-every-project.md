# 0011: The dx workspace lives outside every project, in one private repository

Date: 2026-09-05

## Context

`decisions/0003` puts skill state in the repository of the thing the skill works on. For SEO that is exact: one site, one repository, one workspace under `docs/seo/<domain>/`. The site repository is also where the change lands, so the log row and the commit that carries it sit next to each other.

Developer experience work has no such repository. The subjects are the machine, the container runtime, the shell history, the agent configuration, and the set of local projects taken together. A finding like "four repositories hold unpushed commits" belongs to none of the four. Writing per project would split one weekly answer across dozens of folders, and `and-now` would have to scan every project to reconstruct it. Writing into the skills collection is worse: the collection is public, and the state names paths, hostnames, and project names.

## Decision

The `dx` workspace is one private repository, by default `~/Developer/jorekai/jorekai-dx`, and never a folder inside a project. `machines/<hostname>/` holds everything that is true of one machine: config, audits, log, proposals. `config.md` and `standards.md` at the root hold what is true of the person across machines.

A change that lands in a project repository still leaves its commit there, and that commit ends with the trailer `DX-Log: <row id>`. The row stays in the dx workspace, the diff stays in the project.

## Consequences

`jorekai-dx:setup` creates a repository instead of a folder, and says so before it writes. The workspace is private because its contents name customer projects; `friction` additionally redacts before writing, and the workspace carries its own secret scan.

The collection stays public and holds only templates and scripts, exactly as `0003` intended. The rule in `0003` is now read as its principle rather than its path: state lives with its subject, and the subject of `dx` is the machine.

A second machine gets a second folder under `machines/`, not a second repository, so one history covers both.
