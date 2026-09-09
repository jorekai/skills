# Config: what holds across every repository here

Values that do not change from one repository to the next. Each key is read as `- key: value`; a
value left in parentheses is still the template's hint and reads as blank, which turns its check off.

## Owner

- owner: (who answers for a finding in these repositories)
- secret_store: (where a credential lives once it is out of a repository)

## Scanners

- install: (the one command this machine uses to install the optional scanners)
- offline: no (yes keeps every pass off the network and reads the cache only)
