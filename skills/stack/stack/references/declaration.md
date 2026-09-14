# The declaration

`stack.yaml` in the root of the generated repository. It is YAML and not Markdown because the project's own tooling reads it: the boundary rule, the waiver check, the bars in the linter and the unit runner. The passes of this theme read it with the same subset reader the pipeline pass of `jorekai-security` uses: maps, lists, scalars, flow lists on one line, one document, no anchors. A file the reader cannot follow is reported as unread, never as clean.

It lives in the measured repository, not in the workspace, which differs from `jorekai-security`. A declaration is project configuration like `tsconfig.json`; a finding is not, and findings go on into the workspace (`decisions/0035`). The workspace keeps a snapshot of it under `repos/<slug>/stack.yaml`, and `jorekai-stack:drift` notes when the two differ.

The template with every section is `templates/stack.yaml` in `jorekai-stack:choose`; `decl.absent` counts a section from that template that is missing here.

## Sections

| Section | Holds | Read by |
|---|---|---|
| head | `name`, `declared`, `oss_level`, `target`, `oss_caveat`, `runtime` | every pass; `lock.runtime` compares `runtime` to every pinning place |
| `ports` | one adapter per port | `adapter.untargeted` against the axes in [ports.md](ports.md) |
| `port_exceptions` | `port`, `reason`, `since` for a port that runs another adapter on purpose | `adapter.untargeted` reads the entry as the exception |
| `gates` | the ten bars | `guard.unbarred`, `guard.coverage`, `guard.slow`, `dead.*` |
| `guards` | guard name to command, in gate order | `guard.missing`, `guard.unwired`, `guard.disabled` |
| `enforcement` | guard names, each `name@YYYY-MM-DD` once a person confirmed the required check | `escape.unenforced` |
| `workspaces` | package path to the list of packages it may import | `boundary.*`, `decl.undeclared`, `decl.unmatched` |
| `rules` | the rule ids the engine enforces | `guard.rulegap` |
| `waivers` | `kind`, `file`, `line`, `reason`, `until`, `owner` per entry | `escape.type`, `escape.lint`, `escape.test`, `escape.expired`, `decl.unmatched` |
| `open_decisions` | `what`, `recommend`, `until` per entry | `decl.undecided` |
| `human_steps` | `what`, `done` per entry | `jorekai-stack:and-now`, as open items |

## The bars

| Bar | Default | Stands in | Meaning |
|---|---|---|---|
| `coverage_lines` | 70 | `vitest.config.ts` | percent of lines the unit run must cover |
| `coverage_branches` | 60 | `vitest.config.ts` | percent of branches the unit run must cover |
| `max_function_lines` | 60 | `eslint.config.mjs` | lines per function |
| `max_file_lines` | 400 | `eslint.config.mjs` | lines per file |
| `max_complexity` | 10 | `eslint.config.mjs` | cyclomatic complexity per function |
| `max_params` | 4 | `eslint.config.mjs` | parameters per function |
| `dead_exports_max` | 0 | `scripts/dead.mjs` | unused exports allowed |
| `dead_files_max` | 0 | `scripts/dead.mjs` | unreachable files allowed |
| `dead_deps_max` | 0 | `scripts/dead.mjs` | unused dependencies allowed |
| `gate_max_seconds` | 90 | `scripts/gate.sh` | seconds a full gate may take |

Each configuration file reads its bar from `stack.yaml` through `scripts/stack-yaml.mjs`; none carries a number of its own. `guard.unbarred` counts a bar whose file does not mention its key, and `guard.disabled` counts a file that switches the guard off around it.

An adopted repository starts with the three `dead_*` bars at the measured count and the coverage bars at the measured percentage, so it is green on the day of the adoption and cannot get worse. Raising a `dead_*` bar or lowering a coverage bar is a review, because the file is under `CODEOWNERS`.

## A waiver

```yaml
waivers:
  - kind: type          # type, lint, test, boundary
    file: packages/ports/src/db/pool.adapter.ts
    line: 84
    reason: "the driver types its return value as any, issue 214"
    until: 2026-12-14
    owner: a-person
```

Missing `reason`, `until` or `owner`: the entry does not count, and the suppression is red. Past `until`: red, whatever the reason was. `kind` decides which suppression the entry excuses: `type` for `@ts-ignore`, `@ts-expect-error` and `as any`; `lint` for `eslint-disable` in every spelling; `test` for `.skip` and `.only`; `boundary` for an import over an edge `workspaces` does not name. Dead code is not waived: it has three bars instead, because its stock in an old repository is too large for a list of names.

## An open decision

Depth 3 of [tiers.md](tiers.md) is written here and nowhere else: seven lines, each with a recommendation and a date. `decl.undecided` counts a line past its date. Taking the decision means building the thing or deleting the line; moving the date needs a reason on the line.
