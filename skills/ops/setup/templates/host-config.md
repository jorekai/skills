# {{HOST}}: host facts

One `key: value` per line. Written during `jorekai-ops:setup`, edited by hand when the host changes.

## Ops access

- role: server
- control_plane: (what owns this host's configuration, detected at setup, or none)
- access: (the ssh targets the measuring pass and the fixing pass use, reading account first)
- report: pull (pull sends the script over ssh; push lets a timer here write the JSON)
- access_paths: (comma separated, each as name@YYYY-MM-DD: the way in and the day a fresh connection proved it)
- allow_users: (comma separated accounts the standards name; anything else is unlisted)

## Ops services

- services: (semicolon separated name=unit[,timer=unit][,path=DIR][,repo=URL][,commit=SHA])
- unit_exceptions: (comma separated UNIT:OPTION a unit may miss, with the reason below)

## Ops recovery

- backups: (semicolon separated name=label,source=PATH[,copy=PATH][,copy=host:/PATH][,tested=YYYY-MM-DD])
- secret_paths: (comma separated files or directories holding a credential this host needs)

## Ops notes

- (why an exception exists, what the control plane regenerates, what a rebuild has to redo)
