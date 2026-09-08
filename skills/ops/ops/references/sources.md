# Sources

Every claim about how a platform, a product, or a tool behaves has a row here with the primary source and the date it was checked. A claim with no row is labelled a heuristic in the skill that makes it, or it is left out. `python3 scripts/sources_age.py` lists rows older than 180 days.

| Claim | Where it is used | Source | Checked |
|---|---|---|---|
| Keywords under a `Match` line apply only to connections that meet its criteria; they override the global section instead of setting it | `access.py`, `sshd_settings` stops at the first `Match` line | `man 5 sshd_config` (OpenSSH 10.2p1), `Match` | 2026-09-07 |
| `PasswordAuthentication` defaults to `yes` when no line sets it | `access.py`, `ssh.password-auth` counts the default as a place that permits a password | `man 5 sshd_config` (OpenSSH 10.2p1), `PasswordAuthentication` | 2026-09-07 |
| Environment variables set for a unit are exposed to unprivileged clients over D-Bus and propagate down the process tree; credentials loaded by the service manager are the documented way to pass a secret | `recovery.py`, `secret.plaintext` | `man 5 systemd.exec` (systemd 262~rc1), `Environment=` | 2026-09-08 |
| The journal service reads `journald.conf` and the `journald.conf.d/*.conf` drop-ins beside it, so a value set in a drop-in is the value the host runs | `recovery.py`, `journald_settings` reads both | `man 5 journald.conf` (systemd 262~rc1), FILES | 2026-09-08 |
| `MaxRetentionSec` defaults to 0, which turns age-based deletion off; `SystemMaxUse` defaults to 10 percent of the filesystem, capped at 4G | `recovery.py`, `log.no-retention` calls an unset bound a decision nobody made, not an unbounded journal | `man 5 journald.conf` (systemd 262~rc1), `MaxRetentionSec=`, `SystemMaxUse=` | 2026-09-08 |
| `Storage=auto` keeps the journal on disk only while `/var/log/journal` exists, and the directory is what decides the mode | `recovery.py`, the note that names a volatile journal | `man 5 journald.conf` (systemd 262~rc1), `Storage=` | 2026-09-08 |
| Only files ending in `.journal` or `.journal~` count towards the journal's disk usage, because that is what the service and its reader add up | `recovery.py`, `journal_usage` | `man 5 journald.conf` (systemd 262~rc1), `SystemMaxUse=` | 2026-09-08 |
| `ss -l` shows listening sockets only, `-n` prints numeric addresses instead of service names, and `-H` drops the header line | `exposure.py`, `sockets` reads `ss -H -ltunp` | `man 8 ss` (iproute2, main), OPTIONS | 2026-09-08 |
| `openssl x509 -enddate` prints the notAfter date, and `-dateopt iso_8601` prints dates in ISO form instead of the default | `exposure.py`, `enddate` | `openssl-x509` manual (OpenSSL, master), `-enddate`, `-dateopt` | 2026-09-08 |
| `firewall-cmd --state` reports whether the daemon is running and prints that state | `exposure.py`, `fw.disabled` on a firewalld host | `firewall-cmd` manual (firewalld, main), Status Options | 2026-09-08 |
| In ufw's status output, `Anywhere` means any address, that is `0.0.0.0/0` and `::/0` | `exposure.py`, the rules read out of a ufw status | `man 8 ufw` (ufw, master), `status` | 2026-09-08 |

## Heuristics, deliberately unsourced

These are judgements this collection makes, not documented behaviour. They are named here so nobody mistakes them for facts.

- The weak algorithm list in `access.py` is a judgement about what should no longer be offered, not a standard. It is an argument (`--weak-algorithm`) so a host can replace it.
- The grace window in `availability.py` exists because a systemd timestamp carries a zone abbreviation, which is ambiguous. The date and the clock are read, the zone is not, and the window absorbs the offset.
- Two independent ways in is the bar this collection chose. Nothing external says two rather than three.
- The reload in `fixes.md` names `ssh` and then `sshd` because the unit is spelled both ways across distributions. Naming both costs nothing; this collection has not checked which distribution uses which.
- Ten minutes for the rollback timer is long enough to notice a broken login and short enough that a forgotten timer is not an outage.
- The names `recovery.py` treats as a credential (`PASSWORD`, `SECRET`, `TOKEN`, and their relatives) are a judgement about which variable names carry one, not a standard.
- A copy no older than 24 hours and a restore test inside 90 days are the defaults this collection chose. `standards.md` sets both, and a host with a reason writes another number.
- The column order of a socket list is not a documented interface, so `exposure.py` reads the address tokens on a line instead of counting columns.
- The `Status: active` line of a ufw status and the shape of an nftables ruleset dump are output this collection reads by pattern. Neither is documented as an interface.
- An nftables input chain whose policy is accept and which drops nothing counts as not filtering; one that accepts by default and drops named traffic counts as filtering, with a note saying so. Both are judgements about what a firewall is for, not documented states.
- Twenty-one days before a certificate's date is the window this collection chose. `standards.md` sets it, and a host with a shorter renewal cycle writes another number.
