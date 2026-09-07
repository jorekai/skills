# Tools

Interchangeable. A step never names one; it names what has to be true. This file says what each is for, so a host that carries a different one is not blocked.

| For | On the host | Notes |
|---|---|---|
| Effective ssh settings | `sshd -T` | Needs privilege. Without it the configuration file and its includes are parsed instead, which reads the same keywords but not the daemon's own defaults. |
| Listening sockets | `ss -lntup`, `netstat -lntup` | The second is older and prints the same columns in a different order. |
| Firewall rules | `nft list ruleset`, `ufw status verbose`, the control plane's own view | A control plane usually regenerates its own rules, so its view is the one that survives an update. |
| Unit and timer state | `systemctl show`, `systemctl list-timers` | `show` prints `Key=Value` lines, which parse without a table reader. |
| Pending updates | `apt-get -s upgrade`, `unattended-upgrade --dry-run` | The simulation names the packages; the second says whether they would install by themselves. |
| Certificates | `openssl x509 -noout -dates`, the control plane's certificate list | |
| Copying a script to a host | `ssh` with the script on standard input | Nothing is installed on the host and nothing is left behind. |
| Secrets at rest | an encryption tool the deploy step decrypts with | Named in `config.md` as `secret_store`, so a host that carries a different one is still measured. |
