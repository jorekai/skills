# Standards: what good looks like here

What every check measures against. A finding is the gap between this file and the repository, so a
value left blank turns its check off rather than guessing a target. `scaffold.py --flags` turns
these values into the arguments the measuring scripts take, so nobody has to remember them.

## Security profile

- profile: (baseline, hardened, or paranoid; the name of the bar the values below carry out)
- allow_safe: no (yes lets a fix classed safe run without asking; in a repository other people push to, leave it no)
- verify_window_days: (days between an applied action and its verdict)
- audit_max_age_days: (an audit older than this describes a repository that moved on)

## Security secrets

- entropy_bits: (bits per character above which a random-looking string becomes a candidate)
- history_days: (how far back the history is read; blank reads all of it)

## Security pipeline

No value here. Which workflow owners need no commit pin is a property of one repository, not of the
workspace, so `trusted_owners` lives in that repository's `config.md` under the trust model.

## Security deps

- epss_floor: (probability from 0 to 1 at or above which an advisory counts as exploited even when no catalogue names it)

## Security review

- confidence_floor: (the bar a finding clears before it becomes a rule, from 1 to 10)
