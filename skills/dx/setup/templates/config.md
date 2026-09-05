# Developer experience: what holds across machines

Read before running any `jorekai-dx:*` skill. One `key: value` per line so agents and scripts can parse it. Unknown stays blank; a guess is worse than a blank. Every key here is read by a skill or a script: a key nobody reads does not belong in this file.

## Identity

- git_email: (the address commits should carry, checked against every repository)
- forge: (host where remotes live, for example github.com)
- forge_user: (account name on that forge, whose review requests are counted)
