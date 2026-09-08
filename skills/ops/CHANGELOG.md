# Changelog

One entry per `jorekai-ops` version. The version at the top equals `version` in `skills/ops/.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

## 0.4.0 (2026-09-08)

- Added: `jorekai-ops:recovery`, the pass over what is left when the host is gone. Ten checks over backup targets, secret files, unit credentials and the journal: `backup.missing`, `backup.stale`, `backup.offsite`, `backup.untested`, `secret.missing`, `secret.mode`, `secret.in-repo`, `secret.plaintext`, `log.no-retention`, `log.growth`. The first rung of the ladder named `secret.*` and `backup.missing` since the theme shipped and nothing could measure them, so every log row carrying one stayed parked.
- Added: the pass reads names, modes, write times and unit settings, never the contents of a secret, and a finding names the file and the unit rather than the value. A test proves a value in a unit file does not reach the output.
- Added: `standards.md` gains `## Ops recovery` (`backup_rpo_hours`, `restore_test_days`, `log_share_max_percent`) and a host's `config.md` gains `backups` and `secret_paths`; `scaffold.py --flags` turns both into the arguments the pass takes.
- Changed: `grade.py` owns `backup`, `secret` and `log` instead of parking them, and `status.py` measures their ids, so rows that waited for a tool now reach a verify date.
- Changed: the router's ladder names `backup.stale` on the first rung and `backup.offsite` on the fifth, beside the ids the shipped tool emits.

## 0.3.0 (2026-09-08)

- Added: what a skill hands back has a shape, beside the shape of the report it read. `jorekai-ops:ops` carries `## Writing the answer`: one line of context, one table in ladder order of at most five rows, one line with the next action, and the columns for every sub-skill. `jorekai-ops:access` and `jorekai-ops:availability` share `check id | cost | targets | fix | class`, whose class cell is the class that will actually run, and `jorekai-ops:grade` carries `row | then | now | verdict | next`. `decisions/0023`.
- Added: `scripts/check.sh` fails when a theme router has no `## Writing the answer`, when a sub-skill of that theme is missing from it, and when the column line the router gives a skill stands in no line of that skill's `SKILL.md`. The gate catches the omission; whether the columns are the right ones stays with review.
## 0.2.0 (2026-09-07)

- Added: every script that prints a report colours it, and only when the output is a terminal. `NO_COLOR` turns it off, `FORCE_COLOR` turns it on, and removing every escape leaves the same report, so a pipe, a redirect, a captured test and a subagent read what they always read. A level word, a verdict, a check id and a measure carry the colour their role already has; nothing is coloured for its looks. `decisions/0022`.

## 0.1.0 (2026-09-07)

- Added: the theme itself. A host that serves was already being kept by hand in the machines workspace, under check ids no tool measured and no table explained. `jorekai-ops` gives that work a router, a ladder, a fixes table with a fix per control plane, and three measuring passes.
- Added: `jorekai-ops:setup` takes a host into the shared workspace, detects what owns its configuration, creates a reading account without privilege and a changing account with named sudo, proves both from a fresh connection, and writes the chosen profile into `standards.md`. The order is the content: the second way in exists before anything hardens the first.
- Added: `jorekai-ops:access` measures who can reach the host, in eleven checks from `ssh.root-login` to `user.unlisted`. `access.single-path` measures the ways in missing from the bar, which makes "this host has one key and no console" a number that reaches zero instead of a worry. A way in counts only with the date a fresh connection proved it, so `access_paths` carries `name@YYYY-MM-DD` and an undated entry never reaches the check.
- Added: `jorekai-ops:availability` measures whether the services the standards name run, fire, are hardened, and sit at the commit they should, in nine checks. A failed unit and a stopped one are counted apart, because they need different fixes.
- Added: `jorekai-ops:grade` settles a log row whose verify date has passed, by recomputing its measure from the newest audit of the tool that found it. Without it the theme would write rows with a measure and a date and have nothing that reads either back. `--namespaces` prints which tool owns which check id namespace, and `scripts/check.sh` compares that to the fixes table in both directions.
- Added: `jorekai-ops:and-now` reads the workspace alone and names the stage, the open items in ladder order, and the next verify date. A row whose tool has not shipped yet is reported as parked, naming the skill that will measure it, rather than as an id nobody owns.
- Added: `setup/scripts/remote.sh` sends a measuring script over ssh, runs it as the reading account, removes it, and returns the JSON. `--fetch` reads a report a timer on the host wrote instead, `--probe` says only whether the host answers, and `--dry-run` prints the remote command without running it. Arguments are quoted the POSIX way, because the remote login shell is not always bash.
- Added: gate 2 in front of every change to access: two independent ways in proved from fresh connections, a backup copy, and a rollback timer that is cancelled only after a new connection succeeds. `decisions/0016`.
- Added: `safe` is off until a host turns it on. `scaffold.py --append-row` runs a row classed `safe` as `confirm` while `allow_safe` is `no`, and records the class that actually ran. `decisions/0017`.
