# Tools

What each tool is for in the generated repository, and what this theme does when one is not installed. The passes of this theme run none of them: `jorekai-stack:drift` and `jorekai-stack:guards` read the tree and the artefacts the gate left under `.stack/`. A tool that is missing on the measuring machine lowers nothing; a tool that is missing in the generated repository is what `guard.missing` counts.

Rules for this file, and for whoever adds a row: a tool is interchangeable, so no step in any `SKILL.md` names one. The name lives here and in the templates of `jorekai-stack:new`, the behaviour lives in the generated scripts, and the pass degrades to `null` when the artefact a tool writes is not there.

## In the generated repository

| Role | Tool | Writes | Without it |
|---|---|---|---|
| App generator | `create-next-app` | `apps/web` | `jorekai-stack:new --flags` prints the command; nothing else replaces it |
| Package manager | `pnpm` | `pnpm-lock.yaml` | `lock.incomplete` reads the lock; another manager needs a second reader |
| Formatter | `prettier` | nothing | the format step fails, which is the answer |
| Linter | `eslint` with `typescript-eslint` | nothing | the complexity bars and the type-aware floating-promise rule do not run; the rule engine still runs its text twin |
| Rule engine | `rules/run.mjs`, generated | nothing | it is generated, so missing means `decl.generated` or `guard.missing` |
| Type checker | `tsc` | nothing | the typecheck step fails |
| Unit runner | `vitest` with the `v8` coverage provider | `coverage/coverage-summary.json` | `guard.coverage` reads `null` |
| Browser runner | `playwright` | nothing | the browser step fails; the browser binary is installed once by `--wire` |
| Dead code | `knip` | `.stack/dead.json` through `scripts/dead.mjs` | the three `dead.*` checks read `null` |
| Hooks | `lefthook` | nothing | the hook does not run; the workflow is the lock anyway |
| Secret scan | `gitleaks` | nothing | the secrets step fails and names the install command; a gate that skips a guard in silence is the thing this theme measures |
| Forge client | `gh` | a captured branch protection, `gh api repos/<owner>/<repo>/branches/<default>/protection`, for `--protection-file` | the protection can still be set in the forge's web interface, but without a capture `escape.unenforced` cannot prove it and stays unknown, never a pass |

## On the measuring machine

Nothing. Both passes are Python from the standard library and read files. `jorekai-stack:new` needs the generator and the package manager on the machine that lays the project out, and `--flags` says which.
