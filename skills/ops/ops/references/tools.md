# Tools

Interchangeable. A step never names one; it names what has to be true. This file says what each is for, so a host that carries a different one is not blocked.

| For | On the host | Notes |
|---|---|---|
| Effective ssh settings | `sshd -T` | Needs privilege. Without it the configuration file and its includes are parsed instead, which reads the same keywords but not the daemon's own defaults. |
| Listening sockets | `ss -lntup`, `netstat -lntup` | The second is older and prints the same columns in a different order. |
| Firewall rules | `nft list ruleset`, `ufw status verbose`, the control plane's own view | A control plane usually regenerates its own rules, so its view is the one that survives an update. Needs privilege, and unlike `sshd -T` there is no unprivileged fallback: neither prints anything without it, so the reading account cannot list a firewall itself. |
| Unit and timer state | `systemctl show`, `systemctl list-timers` | `show` prints `Key=Value` lines, which parse without a table reader. |
| Pending updates | `apt-get -s upgrade`, `unattended-upgrade --dry-run` | The simulation names the packages; the second says whether they would install by themselves. |
| Certificates | `openssl x509 -noout -dates`, the control plane's certificate list | |
| Copying a script to a host | `ssh` with the script on standard input | Nothing is installed on the host and nothing is left behind. |
| Secrets at rest | an encryption tool the deploy step decrypts with | Named in `config.md` as `secret_store`, so a host that carries a different one is still measured. |

## The firewall listing gap

`nft list ruleset` needs root: access from userland to the kernel needs it, whatever the account. `ufw status verbose` is documented the same way, always shown with `sudo`. `firewall-cmd` is usually no different, though it is mediated by polkit and a host's own policy can move that bar; `exposure.py` never assumes an answer either way and reads a refusal as unknown, not as a clean pass.

The reading account carries none of that, on purpose (`setup/SKILL.md`, step 3): a pass that measures carries no privilege. `sshd -T` has a fallback for the same shape of gap, reading the configuration file when it cannot ask the daemon; a firewall has none, because there is nothing to fall back to that is not the live kernel state.

The path that keeps the reading account unprivileged: the changing account, which already runs the fixes table's commands under a narrow sudoers file, captures one dump on the host and writes it somewhere the reading account can read, for example:

```bash
ssh <changing account>@<host> 'sudo nft list ruleset > /tmp/ops-fw.txt && chmod 644 /tmp/ops-fw.txt'
```

Then `--fw-file /tmp/ops-fw.txt --fw-kind nft` is added to the exposure flags for that one run, in place of `--fw-kind auto`. `exposure.py` itself still runs as the reading account and only reads a file; the one command that needed privilege ran under the account that already holds it. Add the exact listing command for this host's control plane to `sudo_allowed_commands` in `standards.md`, the same list the fixes table's own commands sit in, so `access.py`'s `sudo.nopasswd` reads the rule as one the table names instead of a finding.
