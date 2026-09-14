# {{SLUG}}

What this repository is, and what a pass has to know before it can read its declaration.
Each key is read as `- key: value`; a value left in parentheses is still the hint and reads blank.

- role: stack (this theme measures a folder that says stack, and nothing else)
- path: (the checkout this machine reads, for example ~/Developer/example/example-app)
- origin_kind: (public, private, or vendor; who can read the history)
- default_branch: (the branch the gate protects, blank means the workspace default)
- state: (new before the generator ran, existing for a repository that is adopted)

## Exceptions

- accepted: (one per entry, semicolon separated, `check-id target reason YYYY-MM-DD`)
