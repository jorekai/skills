# Standards: what good looks like here

What every log row and every declaration starts from. A value left blank turns its check off rather than guessing a target. `scaffold.py --flags` turns these values into the arguments the measuring scripts take, so nobody has to remember them.

## Stack profile

- profile: (strict, standard, or lenient; the bars the next `jorekai-stack:choose` starts from)
- allow_safe: no (yes lets a fix classed safe run without asking; in a repository other people push to, leave it no)
- verify_window_days: (days between an applied action and its verdict)
- audit_max_age_days: (an audit older than this describes a repository that moved on)

## Stack bars

No number here. The bars live in each repository's `stack.yaml`, under `gates`, because the project's own tooling reads them there and `CODEOWNERS` guards them there. This file only names the profile a new declaration starts from; a repository that moves away from it does so through review of its own file.
