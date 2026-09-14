# The rule engine

A standard linter does not know the architecture of this repository. A directory `rules/` in the generated repository is the one place a project teaches an agent a boundary of its own, and the gate runs it as step 3. Every rule is one file with four required parts, and a rule without a test is not run (`decisions/0037`): a rule that looks like a lock and catches nothing is worse than no rule, because everybody believes the branch is defended.

## The shape of a rule

`rules/<id>.rule.mjs` exports one object:

| Part | Key | Why |
|---|---|---|
| The id | `id` | the message is findable, and `stack.yaml` names the class under `rules` |
| The pattern | `kind`, `match`, and the keys of that kind | what is forbidden |
| The message | `message` | names the place and the allowed state, never only the ban |
| The test | `rules/<id>.test.mjs` | one fixture that must match, one that must not |

Three kinds, and the runner `rules/run.mjs` knows no other:

| Kind | Fires when | Keys |
|---|---|---|
| `line` | a line matches `match` and not `allow` | `files` (globs), `match`, `allow` |
| `block` | a block opened by `open` closes without a line matching `require` | `files`, `open`, `require` |
| `edge` | an import from a file in one workspace names a package its line in `workspaces` does not allow | `files` |

A rule may declare `waivable: "boundary"` and the like; the runner then skips a hit whose file and line stand under `waivers` in `stack.yaml` with that kind and a date that has not passed.

## The message

`boundary violation in packages/ui` makes an agent guess. `packages/ui/src/index.ts:3 imports @app/ports, allowed from packages/ui: @app/config` makes it fix the line. Every message names three things: the file and line, what was found, and what is allowed instead. The runner prints them as `<file>:<line>  <id>  <message>`.

## The test

`rules/<id>.test.mjs` runs under the platform's own test runner, before the rule runs over the tree, and holds two fixtures as strings: `hit`, which must produce exactly one finding, and `pass`, which must produce none. The runner refuses a rule whose test file is missing or whose test fails, and `guard.rulegap` in `jorekai-stack:guards` counts the same gap statically, so a skipped run does not hide it.

## The starting set

Six rules follow from the declaration and are not invented. Each is generated with its test; the project adds its own the same way.

| Rule | Kind | Forbids | Allows instead |
|---|---|---|---|
| `no-raw-env` | `line` | `process.env` outside `packages/env` | the import from `@app/env` |
| `no-vendor-outside-adapter` | `line` | a module from the vendor list of [ports.md](ports.md) outside `packages/ports/src/<port>/` | the port's contract through `@app/ports/<port>` |
| `no-cross-boundary` | `edge` | an import over an edge `workspaces` does not name | the packages that line allows |
| `no-untimed-fetch` | `block` | a `fetch(` call whose argument list carries no `signal` | `signal: AbortSignal.timeout(TIMEOUT_MS)` from `@app/config` |
| `no-floating-promise` | `line` | a statement that calls `fetch` or a function named `...Async` and neither awaits, returns, voids, nor assigns it | `await`, `return`, `void` with a named handler, or an assignment |
| `no-test-without-assertion` | `block` | a test block with no `expect(` inside it | at least one assertion |

`no-floating-promise` and `no-test-without-assertion` are text rules and heuristics: the type-aware twin of the first runs in the linter, the runtime twin of the second is the assertion requirement of the unit runner. The text rule is what makes the gap countable when the other one was switched off.

## Adding a rule

1. Write `rules/<id>.rule.mjs` with the four parts.
2. Write `rules/<id>.test.mjs` with `hit` and `pass`.
3. Add `<id>` under `rules` in `stack.yaml`, which is a review.
4. `pnpm check` runs the test and then the rule.

The id is the join key between the rule file, the declaration, the gate's output and a waiver's `kind`.
