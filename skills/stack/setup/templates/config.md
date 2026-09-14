# Config: what holds across every repository here

Values that do not change from one repository to the next. Each key is read as `- key: value`; a
value left in parentheses is still the template's hint and reads as blank, which turns its check off.

## Owner

- owner: (who answers for a finding in these repositories, and who reviews a contract file)
- forge: (where the repositories are hosted, so the required check is set in one place)

## Conventions

- default_branch: main (the branch the gate protects unless a repository says otherwise)
- generator: create-next-app (the app generator every new repository starts from)
