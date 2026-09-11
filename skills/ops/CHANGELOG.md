# Changelog

One entry per `jorekai-ops` version. The version at the top equals `version` in `skills/ops/.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

## 0.7.0 (2026-09-11)

- Changed: `access.py`, `availability.py`, `exposure.py`, `recovery.py`, `status.py`, `grade.py`, and `report.py` lay out their console report the same way now: the counting line is a bar of counts, a finding's cost stands in its own column, `now` in `status.py` is two aligned columns, and repeated notes in `report.py` fold into one line. Reason: `decisions/0028`.

## 0.6.3 (2026-09-08)

- Fixed: `jorekai-ops:report` told a reader with no host folder to run the DX setup. Copy-paste from the theme it was written from.
- Fixed: `scaffold.py --flags` printed a backup spec whose label holds a space as two arguments, so the line it prints could not be pasted. Every value with a space is quoted now.
- Fixed: the headline of a report called the first fall in ladder order the biggest one. Biggest is measured as a share of what the check cost before, so two units compare.
- Fixed: a log table was read past the end of its section, so a second table under it would have become actions.
- Changed: the first step of `jorekai-ops:exposure` no longer carries what an empty socket list means. That reading stands under `## Interpretation`, where a fact belongs (`STYLE.md`).

## 0.6.2 (2026-09-08)

- Fixed: `jorekai-ops:report` read every audit in a host's folder, including the ones `jorekai-dx` wrote, so a host's month could be told with a machine's numbers. It reads the tools of its own theme and names the rest under what the report does not cover.
- Fixed: a log row that carries a verdict stayed in the open table and in the three next steps when nobody had rewritten its status cell. A settled row is settled.
- Fixed: a host with no expected port list reported nothing, while `jorekai-ops:exposure` says every unnamed port is a finding. It now reports them, and a socket list that was read and holds nothing writes the zero that settles a row about a closed port.
- Fixed: a firewall that did not answer was reported as one that filters nothing. That answer carries no measure now, because a number there settles a log row with a figure nobody took. An nftables chain that accepts by default and drops named traffic counts as filtering, with a note saying which it is, and so does a firewalld zone whose target is ACCEPT.
- Fixed: a certificate date was read as local time and compared against a local clock, so every certificate inside one day of its end could be judged by the zone offset instead of by its date. Both sides carry a zone now.

## 0.6.1 (2026-09-08)

- Fixed: a backup directory that exists and holds nothing counted as a copy, so `backup.missing` and `backup.stale` both passed on a job that created a folder and wrote nothing. A copy is a file now, and the file that dates it is the same read.
- Fixed: a target whose only copy is off this host was passed as fresh with a measure of zero, which settled an older stale row as `won` without measuring anything. Nothing passes there now; the target is named and left open.
- Fixed: unit files were keyed by file name, so two drop-ins called `override.conf` collapsed into one and a credential in the first of them disappeared. The key is the path under the unit directory, which is also what makes `/etc` replace `/usr/lib`.
- Fixed: `log.growth` counted only `.journal` files. The service counts `.journal~` too, so a host whose archived files hold most of the journal read as a fifth of its real share. The source row said the wrong thing and now says what the manual says.
- Fixed: an nftables rule that drops a port was read as a rule that opens it, so `fw.rule-orphan` asked for the wrong line to be removed, and the protocol was dropped, so a udp rule matched a tcp listener. A rule is read whole: protocol, ports, verdict.
- Fixed: a ufw rule about what this host sends or forwards (`ALLOW OUT`, `ALLOW FWD`) counted as an open port, and a port range lost everything but its first port. Only inbound rules count, and a range is named as a range.
- Fixed: a firewalld host was judged by `firewall-cmd --list-all` alone, which prints a zone's rules while nothing enforces them. The state is read with `--state`, which is what the source row documents.
- Changed: the log step of `jorekai-ops:recovery` and `jorekai-ops:exposure` writes `--then "<number> <unit>"`. The old line hardcoded `count` and made every `percent` row ungradeable.

## 0.6.0 (2026-09-08)

- Added: `jorekai-ops:report`, the month on this host, in the shape the DX report has, with the class each action ran under beside its verdict. `scripts/report.py` reads the audits that open and close the month and the log rows inside it, and writes `machines/<host>/reports/ops/YYYY-MM.md`.
- Added: `scaffold.py` creates `reports/<theme>/` beside the log folder, so both themes report on the same host without writing into one file.

## 0.5.0 (2026-09-08)

- Added: `jorekai-ops:exposure`, the pass over what this host offers the network. Eight checks: `port.world-open`, `panel.exposed`, `fw.disabled`, `tls.expired`, `tls.expiring`, `intrusion.off`, `port.unexpected`, `fw.rule-orphan`. The second rung of the ladder is the one a host on the open network is judged by, and until now nothing measured it.
- Added: a port open to anywhere and a port bound to one address are separate findings four rungs apart, and no socket is counted twice. The address a socket binds to decides, not the rule in front of it.
- Added: firewalls are read per kind, `nft`, `ufw` or `firewalld`, from the host or from a captured status; a kind this pass does not read says so instead of reporting a clean firewall.
- Added: `standards.md` gains `## Ops exposure` (`tls_expiring_days`) and a host's `config.md` gains `firewall`, `expected_ports`, `panel_ports`, `cert_paths` and `intrusion_units`; `scaffold.py --flags` turns them into the arguments the pass takes.
- Changed: `grade.py` owns `port`, `fw`, `intrusion`, `tls` and `panel`, and `status.py` measures their ids, so the last parked rows outside `pkg`, `boot`, `os` and `plane` reach a verdict.

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
