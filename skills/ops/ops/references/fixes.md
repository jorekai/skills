# Fixes by check id

One row per check id a shipped tool emits: what the finding means, the risk class it runs under, and the measure that grades it later with the unit that measure is written in. `scripts/check.sh` compares the unit here against the unit the script reports for that id, so a row graded in another unit is graded against nothing.

Where the fix differs between control planes, a section under [Fixes per control plane](#fixes-per-control-plane) holds one block per plane. A check that is fixed the same way everywhere has no section.

The namespaces `pkg`, `boot`, `os` and `plane` belong to this theme and arrive with their tools; the `## Planned` table in the router says which skill brings which. A log row carrying one of them is parked until then, and `jorekai-ops:and-now` and `jorekai-ops:grade` both say so rather than calling it an unknown id.

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

## Recovery

| Check | What it means | Class | Measure (unit) |
|---|---|---|---|
| `backup.missing` | A target the standards name has no copy on this host and none recorded anywhere else | `confirm` | Targets without a copy (`count`) |
| `backup.stale` | The newest copy of a target is older than the window the standards allow | `confirm` | Targets past their window (`count`) |
| `backup.offsite` | Every copy of a target sits on this host, so what takes the host takes the copy | `confirm` | Targets with every copy here (`count`) |
| `backup.untested` | No restore of this target finished inside the window, so the copy is a file nobody has read back | `confirm` | Targets without a restore test (`count`) |
| `secret.missing` | A secret the standards name is not on this host, so something that needs it fails later | `ask` | Secrets that are not there (`count`) |
| `secret.mode` | A secret is readable or writable by more than the account that owns it | `ask` | Secrets readable beyond their owner (`count`) |
| `secret.in-repo` | A secret sits inside a work tree without being ignored, so a commit can take it into a history that keeps it | `ask` | Secrets inside a work tree (`count`) |
| `secret.plaintext` | A credential reaches a service as an environment variable, which unprivileged clients read back over the bus | `ask` | Credentials passed in units (`count`) |
| `log.no-retention` | Neither bound on the journal is set, so how far back it reaches is whatever the build chose | `confirm` | Bounds nobody set, out of two (`count`) |
| `log.growth` | The journal holds more of its filesystem than the standards allow | `ask` | Percentage points over the share (`percent`) |

## Exposure

| Check | What it means | Class | Measure (unit) |
|---|---|---|---|
| `port.world-open` | A port takes connections from anywhere and the standards name none of them | `ask` | Ports open to anywhere (`count`) |
| `panel.exposed` | The surface that changes this host answers on the open network | `ask` | Panel ports open to anywhere (`count`) |
| `fw.disabled` | Nothing filters this host, or the firewall holds rules and is not filtering | `confirm` | Hosts with nothing filtering (`count`) |
| `tls.expired` | A certificate is past its date, so a client is told the connection cannot be trusted | `confirm` | Certificates past their date (`count`) |
| `tls.expiring` | A certificate runs out inside the window the standards allow | `confirm` | Certificates inside the window (`count`) |
| `intrusion.off` | A unit that should watch failed attempts is not running | `confirm` | Units that are not watching (`count`) |
| `port.unexpected` | A port nobody named listens on one address of this host | `ask` | Ports nobody named (`count`) |
| `fw.rule-orphan` | A rule lets a port in that nothing on this host serves | `ask` | Rules for ports nothing serves (`count`) |

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

### backup.missing, backup.stale, backup.offsite

The copy itself is the host's own job, and this collection does not bring one. What the fix does is name the target, point the job at a place that is not this host, and run it once:

```bash
# none: prove the target is readable before anything is scheduled against it
install -d -m 700 <copy directory>
<the host's copy command> <source> <copy directory>
```

A copy that lands on the same disk answers `backup.missing` and leaves `backup.offsite` where it was. Only a copy the host cannot delete by itself settles that one, which is why the entry in `config.md` carries the remote copy as `host:/path` and not as a mount that is always there.

### backup.untested

```bash
# none: restore into a scratch path, compare, then remove the scratch path
install -d -m 700 /var/tmp/restore-check
<the host's restore command> <copy> /var/tmp/restore-check
diff -rq <source> /var/tmp/restore-check | head
```

The date the restore finished goes into that target's `tested=` field in `config.md`. Without the date the check has nothing to measure, and a job that runs nightly still counts as untested.

### secret.mode, secret.in-repo

```bash
# none: narrow the file, never the group behind it
chmod 600 <path>
chown <the account the service runs as> <path>
```

A secret inside a work tree moves out of it, and the path it moves to goes into the unit that reads it. Adding the file to `.gitignore` stops the next commit and does nothing about a history that already holds it: a secret that was committed is rotated, not deleted.

### secret.plaintext

Gate 1 applies: the unit is a file a deployment may own, so the change is made where that deployment reads it.

```bash
# none: the value moves into a file the service manager hands over, and out of the unit
install -m 600 -o root -g root /dev/null /etc/credstore/<name>
systemctl edit <unit>          # LoadCredential=<name>:/etc/credstore/<name>, and the Environment= line goes
systemctl daemon-reload && systemctl restart <unit>
```

The service then reads the value from the directory the manager exports to it. A credential that was in a unit file is treated as known: it is replaced, not moved.

### log.no-retention, log.growth

```bash
# none: both bounds in one drop-in, so a package update does not take them back
install -d /etc/systemd/journald.conf.d
printf '[Journal]\nMaxRetentionSec=<days>d\nSystemMaxUse=<size>\n' \
  > /etc/systemd/journald.conf.d/10-ops.conf
systemctl restart systemd-journald
```

The restart is of the journal service alone and no stored entry is lost by it. Bringing a journal that is already over its share back under it removes files, which is why `log.growth` is `ask` while the bound that prevents it is `confirm`.

### port.world-open, port.unexpected, panel.exposed

Gate 2 applies to every one of these, because a port that is closed by hand is closed for the connection reading this report as well.

```bash
# none: bind the service to one address instead of every interface, then prove it moved
ss -H -ltnp | grep -w <port>
systemctl edit <unit>          # the address the service listens on, in the unit's own option
systemctl restart <unit> && ss -H -ltnp | grep -w <port>
```

A panel is the exception that stays reachable: the fix restricts the addresses that may reach it rather than closing it, and the address that is allowed is the one the owner connects from. A rule that closes a panel port without that address takes the control plane away from its owner.

### fw.disabled

Gate 2 applies. The first rule on a host that had none is the change most likely to end the session that made it.

```bash
# none: allow the way in first, then turn filtering on, then prove a fresh connection still lands
<the host's firewall> allow <ssh port>/tcp
<the host's firewall> enable
```

```bash
# plesk: the panel owns its own rule set, so the rule is added there and not beside it
plesk bin extension --exec firewall --set-rules-and-apply
```

The order in the first block is the fix: a firewall enabled before the way in is allowed is the classic lockout, and it is the reason this id sits behind gate 2 even though it only adds a limit.

### fw.rule-orphan

```bash
# none: name the rule, then remove it, then prove nothing else used it
<the host's firewall> status numbered
<the host's firewall> delete <number>
```

A rule that let in a port nothing serves is removed only after the service that used it is known to be gone. An orphan is a sign of an undocumented change as often as it is leftover.

### tls.expired, tls.expiring

```bash
# none: renew, then reload the service that serves the certificate, then read the new date
<the host's certificate client> renew
systemctl reload <unit>
openssl x509 -noout -enddate -dateopt iso_8601 -in <path>
```

The last line is the check itself, so the fix is verified with the same reading that found it. A certificate that renews and is not reloaded keeps serving the old one, which is the failure this check reports again a day later.

### intrusion.off

```bash
# none: enabling arms it, starting it makes it watch now
systemctl enable --now <unit>
systemctl show <unit> --property=ActiveState
```

A unit that starts and stops again inside the verify window is the `returned` verdict: what it watches is failing, not the watching.
