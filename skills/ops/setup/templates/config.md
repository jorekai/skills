# Machines workspace: what holds across hosts

Read before running any `jorekai-ops:*` skill. One `key: value` per line so agents and scripts can parse it. Unknown stays blank; a guess is worse than a blank. Every key here is read by a skill or a script.

This file is shared with `jorekai-dx`. Each theme names the sections it reads, and `scaffold.py --check` in either theme says which of its own sections a file is missing.

## Ops identity

- forge: (host where the deploy repositories live, for example github.com)
- secret_store: (how secrets reach a host: the encryption tool the deploy step decrypts with)
