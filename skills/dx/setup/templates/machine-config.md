# {{MACHINE}}: machine facts

One `key: value` per line. Written by `jorekai-dx:setup`, edited by hand when the machine changes.

## Where things live

- project_roots: (directories holding repositories, comma separated)
- projects_index: (path to a generated project list, blank to scan project_roots)
- scan_max_depth: (how deep under a root a repository is still found)

## History sources

- shell_history: (path to the shell history file, blank if none)
- shell_history_db: (path to a history database that records exit code and duration, blank if none)
- agent_sessions: (directory holding agent session transcripts, blank if none)
- extra_history: (further history paths, comma separated)

## This machine

- container_runtime: (what runs containers here, blank if none)
- disk_free_min_gb: (overrides the workspace standard for this machine, blank to inherit)
