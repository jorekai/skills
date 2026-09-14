# Rules

The project's own bans. A standard linter does not know this repository's architecture; a file here does. The gate runs every rule as its third step, after each rule's own test proved that it fires.

One rule is one file, `rules/<id>.rule.mjs`, exporting one object with four parts:

| Part    | Key                              | What it is                                                     |
| ------- | -------------------------------- | -------------------------------------------------------------- |
| id      | `id`                             | the name the message and `stack.yaml` use                      |
| pattern | `kind` and the keys of that kind | what is forbidden                                              |
| message | `message`                        | the file and line, what was found, and what is allowed instead |
| test    | `rules/<id>.test.mjs`            | one fixture that must hit, one that must pass                  |

Three kinds:

- `line`: a line matches `match` and not `allow`.
- `block`: a block opened by `open` closes without a line matching `require`.
- `edge`: an import crosses an edge that `workspaces` in `stack.yaml` does not name.

`files` and `exclude` are globs over the path relative to the root. `waivable` names the waiver kind that excuses a hit, when one may.

A rule without a test beside it is not run, and the gate says so. To add one: write the two files, add the id under `rules` in `stack.yaml` through review, run `pnpm check`.
