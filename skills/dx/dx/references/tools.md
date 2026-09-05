# Tools

What the skills reach for, and what they do without. Tools are interchangeable: a step describes the work, never the product.

## On the machine

- **A container runtime**: the source of `container.*`. The skills ask it for its storage summary and never for anything that changes state. Any runtime that answers the same summary command works; the machine's own is recorded in `machines/<hostname>/config.md`.
- **A shell history database**: a history that records exit code, duration, and working directory per command, rather than the command line alone. Without one, `friction.failed-command` and `friction.slow-command` have nothing to read, and only repeated sequences remain measurable.
- **A secret scanner**: runs over the workspace before a commit, because proposals may quote a command line. Any scanner that fails a commit on a known credential format works.

## What the agent does instead of a tool

- Repository state across many repositories: `repos/scripts/repos.py`.
- Local resources and container storage: `machine/scripts/machine.py`.
- The workspace itself: `setup/scripts/scaffold.py`, and `and-now/scripts/status.py` to read it back.

## Not a tool

- A dashboard that shows the same numbers without writing a log row. The number is not the point; the row with a verify date is.
