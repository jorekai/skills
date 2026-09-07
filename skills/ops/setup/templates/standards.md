# Standards: what good looks like here

What every check measures against. A finding is the gap between this file and the host, so a value left blank turns its check off rather than guessing a target. `scaffold.py --flags` turns these values into the arguments the measuring scripts take, so nobody has to remember them.

Shared with `jorekai-dx`: each theme reads its own sections.

## Ops profile

- profile: (baseline, hardened, or paranoid; the name of the bar the values below carry out)
- allow_safe: no (yes lets a fix classed safe run without asking; on a host that serves, leave it no)
- verify_window_days: (days between an applied action and its verdict)
- audit_max_age_days: (an audit older than this describes a host that moved on)

## Ops access

- access_paths_min: (how many independent ways in the host must have, 2 unless there is a reason)
- key_min_bits: (an RSA key under this many bits is weak; blank turns the check off)
- key_rotation_after: (YYYY-MM-DD; a key file written before this date is past its rotation)
- ssh_max_auth_tries: (attempts sshd may allow per connection; blank turns that limit check off)
- sudo_allowed_commands: (comma separated commands a passwordless sudo rule may name)

## Ops services

- unit_required_options: (comma separated NAME=VALUE options every unit must carry)
- service_restart_bar: (restarts a service may have before it counts as falling over)
