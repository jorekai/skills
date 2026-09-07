# Sources

Every claim about how a platform, a product, or a tool behaves has a row here with the primary source and the date it was checked. A claim with no row is labelled a heuristic in the skill that makes it, or it is left out. `python3 scripts/sources_age.py` lists rows older than 180 days.

| Claim | Where it is used | Source | Checked |
|---|---|---|---|
| Keywords under a `Match` line apply only to connections that meet its criteria; they override the global section instead of setting it | `access.py`, `sshd_settings` stops at the first `Match` line | `man 5 sshd_config` (OpenSSH 10.2p1), `Match` | 2026-09-07 |
| `PasswordAuthentication` defaults to `yes` when no line sets it | `access.py`, `ssh.password-auth` counts the default as a place that permits a password | `man 5 sshd_config` (OpenSSH 10.2p1), `PasswordAuthentication` | 2026-09-07 |

## Heuristics, deliberately unsourced

These are judgements this collection makes, not documented behaviour. They are named here so nobody mistakes them for facts.

- The weak algorithm list in `access.py` is a judgement about what should no longer be offered, not a standard. It is an argument (`--weak-algorithm`) so a host can replace it.
- The grace window in `availability.py` exists because a systemd timestamp carries a zone abbreviation, which is ambiguous. The date and the clock are read, the zone is not, and the window absorbs the offset.
- Two independent ways in is the bar this collection chose. Nothing external says two rather than three.
- The reload in `fixes.md` names `ssh` and then `sshd` because the unit is spelled both ways across distributions. Naming both costs nothing; this collection has not checked which distribution uses which.
- Ten minutes for the rollback timer is long enough to notice a broken login and short enough that a forgotten timer is not an outage.
