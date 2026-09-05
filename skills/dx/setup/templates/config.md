# Developer experience: what holds across machines

Read before running any `jorekai-dx:*` skill. One `key: value` per line so agents and scripts can parse it. Unknown stays blank; a guess is worse than a blank.

## Identity

- name: (the name commits carry)
- git_email: (the address commits should carry, checked against every repository)
- forge: (host where remotes live, for example github.com)
- forge_user: (account name on that forge)

## Defaults a new machine inherits

- shell: (the login shell)
- container_runtime: (what runs containers here, blank if none)
- pointer_file: (file that carries the agent pointer block in a project: AGENTS.md, CLAUDE.md, or both)
