# Fixes by check id

One row per check id a shipped tool emits: what the finding means, the risk class it runs under, and the measure that grades it later with the unit that measure is written in. `scripts/check.sh` compares the unit here against the unit the script reports for that id, so a row graded in another unit is graded against nothing.

Where the fix differs between control planes, a section under [Fixes per control plane](#fixes-per-control-plane) holds one block per plane. A check that is fixed the same way everywhere has no section.

The namespaces `port`, `fw`, `intrusion`, `tls`, `panel`, `pkg`, `boot`, `os`, `plane`, `backup`, `secret` and `log` belong to this theme and arrive with their tools; the `## Planned` table in the router says which skill brings which. A log row carrying one of them is parked until then, and `jorekai-ops:and-now` and `jorekai-ops:grade` both say so rather than calling it an unknown id.

## Access

| Check | What it means | Class | Measure (unit) |
|---|---|---|---|
| `ssh.root-login` | Root can log in over ssh directly, so the account that measures can also change the host | `ask` | Ways in that reach root directly, zero when `PermitRootLogin no` (`count`) |
| `ssh.password-auth` | A guessed password is a way in beside every key. Counted per place that permits one, including a `Match` block that reopens it for one group | `ask` | Settings that permit a password login (`count`) |
| `ssh.weak-crypto` | An offered algorithm rests on SHA-1, a 64-bit block cipher, or a key type OpenSSH no longer offers by default | `ask` | Weak algorithms offered (`count`) |
| `ssh.no-limit` | Nothing in front of sshd makes an attempt expensive: no allow list, no attempt cap, no grace time, no per-source limit | `ask` | Limits not set, out of four (`count`) |
| `key.orphan` | An authorized key sits on an account the standards do not name, so nobody owns the way in it opens | `ask` | Keys with no named owner (`count`) |
| `key.past-rotation` | A key file was last written before the rotation date the profile sets | `ask` | Keys past their rotation (`count`) |
| `key.weak` | A key uses a retired type or falls under the bit bar | `ask` | Keys under the bar (`count`) |
| `key.duplicate` | One key opens several accounts, so revoking one person takes access from everyone holding it | `ask` | Accounts sharing a key (`count`) |
| `access.single-path` | Fewer independent ways in than the bar, so no change to access may run at all | `ask` | Ways in missing from the bar (`count`) |
| `sudo.nopasswd` | A passwordless sudo rule names a command this table does not | `ask` | Rules outside the permitted commands (`count`) |
| `user.unlisted` | An account carries a login shell and the standards do not name it | `ask` | Unnamed accounts with a login shell (`count`) |

## Availability

| Check | What it means | Class | Measure (unit) |
|---|---|---|---|
| `service.down` | A unit the standards name is not running | `ask` | Units not running (`count`) |
| `service.failed` | A unit ended in a failure, so its last run did not do what it is for | `ask` | Units in a failure (`count`) |
| `service.restarts` | A unit restarted more often than the bar, so something makes it fall over | `ask` | Restarts over the bar (`count`) |
| `timer.disabled` | A timer the standards name is not enabled, so nothing fires it after a reboot | `ask` | Timers not enabled (`count`) |
| `timer.missed` | A timer is past its next elapse by more than the grace window | `ask` | Timers past their elapse (`count`) |
| `unit.unhardened` | A unit is missing an option the profile requires and no exception records why | `ask` | Required options not set (`count`) |
| `code.behind` | A deploy path runs code behind the commit the standards name | `ask` | Commits behind (`count`) |
| `deploy.no-key` | A repository's host carries no identity file, so nothing here can pull it | `ask` | Repositories without a key (`count`) |
| `deploy.absent` | A service the standards name has no deploy path on this host | `ask` | Services without a path (`count`) |

## Fixes per control plane

### ssh.root-login

Gate 2 applies: two proved ways in, a backup copy, and an armed rollback timer before any of this runs.

```bash
# none: the OS owns sshd
cp -a /etc/ssh/sshd_config.d/10-ops.conf /etc/ssh/sshd_config.d/10-ops.conf.bak 2>/dev/null || true
printf 'PermitRootLogin no\n' > /etc/ssh/sshd_config.d/10-ops.conf
sshd -t && { systemctl reload ssh || systemctl reload sshd; }
```

```bash
# plesk: the panel regenerates its own ssh settings, so the drop-in it reads is the one to write
plesk bin settings --set solution-ssh-permit-root-login=false 2>/dev/null \
  || printf 'PermitRootLogin no\n' > /etc/ssh/sshd_config.d/10-ops.conf
sshd -t && { systemctl reload ssh || systemctl reload sshd; }
```

A drop-in wins over the lines below the `Include` in the main file, which is why the fix writes one instead of editing `sshd_config` a panel may rewrite. Read the copy in the first line as the backup gate 2 asks for: the live file goes to `.bak`, never the other way round. The reload names `ssh` and then `sshd`, because the unit is spelled both ways across distributions.

Run `sshd -T | grep -i permitrootlogin` after the reload. A host whose `sshd_config` carries no `Include` ignores the drop-in in silence, and the check would keep reading the old value with nothing saying why.

### ssh.password-auth

```bash
# none
cp -a /etc/ssh/sshd_config.d/10-ops.conf /etc/ssh/sshd_config.d/10-ops.conf.bak 2>/dev/null || true
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\n' \
  >> /etc/ssh/sshd_config.d/10-ops.conf
sshd -t && { systemctl reload ssh || systemctl reload sshd; }
```

A `Match` block that reopens passwords for one group is a separate edit in the file that holds it. The finding names the block, so the fix is to remove that line rather than to add another global one.

### key.orphan, key.past-rotation, key.weak, key.duplicate

The fix is the same everywhere and it is a decision, not a command: name the account in `allow_users`, or remove the key. Removing one runs under gate 2, because a key that turns out to be the only way in for someone is exactly the mistake the gate exists for.

```bash
# none: keep the file, replace the line, leave the copy until the next pass reads zero
cp -a ~USER/.ssh/authorized_keys ~USER/.ssh/authorized_keys.bak
grep -v -F "<the key blob from the finding>" ~USER/.ssh/authorized_keys.bak > ~USER/.ssh/authorized_keys
```

### sudo.nopasswd

```bash
# none: one file per purpose under sudoers.d, validated before it counts
visudo -c -f /etc/sudoers.d/ops-admin && systemctl reload sudo 2>/dev/null || true
```

`visudo -c` is not optional: a sudoers file that does not parse takes sudo away from everyone, which is the second way to lock yourself out of a host.

### service.down, service.failed

```bash
# none
systemctl status <unit> --no-pager
journalctl -u <unit> -n 50 --no-pager
systemctl start <unit>
```

A unit that fails again inside the verify window is the `returned` verdict: the fix treated a symptom.

### timer.disabled

```bash
# none: enabling arms it, starting it makes the next elapse real
systemctl enable --now <timer>
systemctl list-timers <timer> --no-pager
```

### unit.unhardened

The option is added in a drop-in, never in the unit file a package owns:

```bash
# none
systemctl edit <unit>          # writes /etc/systemd/system/<unit>.d/override.conf
systemctl daemon-reload && systemctl restart <unit>
```

An option that breaks the service goes into `unit_exceptions` in the host's `config.md` with its reason, and stops being a finding. That is the point of the exception: it is data, not a judgement made again every week.

### code.behind

```bash
# none: fetch first, because the distance was measured from what this clone already held
git -C <path> fetch --tags origin
git -C <path> log --oneline HEAD..<commit>
git -C <path> checkout <commit>
```

### deploy.no-key, deploy.absent

Both are a missing piece, not a broken one. The fix is an entry in the ssh configuration with its own identity file, and a clone at the recorded commit. Both run under gate 2 because they touch ssh configuration.
