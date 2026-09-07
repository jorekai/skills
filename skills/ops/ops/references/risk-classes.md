# Risk classes and the two gates

Every action that changes a host carries one class, decided once here and looked up at run time, never judged in the moment.

## The classes

- `safe`: runs and reports what it did. Off by default on a host that serves: `standards.md` carries `allow_safe: no`, and while it is off a row classed `safe` runs as `confirm`. The scaffold writes the class that actually ran.
- `confirm`: prints a dry run with the exact paths and totals, asks once, then runs.
- `ask`: never runs. Prints the command with its reason and stops.

Which class an id carries is in [fixes.md](fixes.md), one row per check id. The rule behind the column: a fix that removes, closes, restarts, or rewrites a file another process owns is `ask`. A fix that only adds a limit, a jail, a cap, or a permitted update is `confirm`.

## Gate 1: unsaved work

Nothing destructive runs against a repository holding uncommitted or unpushed work. A deploy path on a host is a repository like any other, so `jorekai-dx:repos` answers this question before `jorekai-ops` removes or replaces anything inside one.

## Gate 2: the way in

No change under `ssh.*`, `key.*`, `fw.*`, `sudo.*` or `user.*` runs unless all four hold:

1. Two independent ways in answer, each from a connection opened after the check began.
2. The change first writes a backup copy of every file it touches.
3. The change arms a timer on the host that restores those copies after ten minutes.
4. The timer is cancelled only after a connection opened after the change succeeds.

A change that cannot arm the timer does not run.

Two ways in are independent when they share no account and no key. The reading account with its own key and the changing account with its own key are two. The same account reached over two addresses is one. A console at the hosting provider counts only when `config.md` records it with the date someone opened it, because an untested console is a belief and not a path. `access_paths` carries that date per entry, and `scaffold.py --flags` passes only the dated ones to the check, so the rule is enforced and not only stated.

A host that fails this gate has one finding worth acting on, `access.single-path`, and it is on the first rung of the ladder for that reason. Reasons: `decisions/0016` and `decisions/0019`.
