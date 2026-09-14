# Three depths

What the generator produces is decided once per thing, by depth. Everything is either real code, a port with one adapter behind it, or a line in the declaration. Nothing sits between.

| Depth | What happens | What belongs here |
|---|---|---|
| 1 | Generated as real code, and owned by the generator afterwards | the layout, strict TypeScript, the formatter, the linter with the complexity bars, the rule engine with six rules, the unit runner with the coverage bars and the assertion requirement, the browser runner with one test, the hooks, the secret scan, the workflows, the env schema, `compose.yaml`, `CODEOWNERS` |
| 2 | Wired as a port: one contract, one adapter, one smoke test | the eight ports of [ports.md](ports.md) |
| 3 | Written into the declaration only, with a recommendation and a date | admin view, blog, docs, onboarding, legal pages, notifications, contact form |

Depth 1 is the core, identical in all fifteen axis pairs. Depth 2 is what the axes choose. Depth 3 is what `open_decisions` in `stack.yaml` holds, and `decl.undecided` counts a line past its date, so a thing that was postponed is a finding on the day the postponement runs out and costs nothing before.

## What the depths cost

A depth-1 thing costs a template in `jorekai-stack:new`, a line in [contracts.md](contracts.md) when it is a contract, and a switch in the `guard.disabled` list when it can be turned off. A depth-2 thing costs a directory of adapters, a row per axis value in [ports.md](ports.md), two env keys, and a smoke test. A depth-3 thing costs one line.

Moving a thing up a depth is a change to this file and to the generator in the same commit. Moving one down is a deletion, and the declaration of every repository that carries it gets the line.

## Adopting

`jorekai-stack:new` with `--adopt` writes the same contracts into a repository that exists. It overwrites nothing, names every file it left alone for that reason, proposes one waiver per suppression it finds with file, line and a date, and sets the three dead-code bars and the two coverage bars to what it measured instead of to the defaults. The reason on a waiver is a person's to write, and an entry without one does not count. So an adopted repository is green on the day of the adoption, and every bar can only move the right way from there.

The depths hold for an adopted repository too: what it already has at depth 1 is left alone and named, what it has at depth 2 is declared as a port exception with the reason `adopted`, and what it has at depth 3 is a decision already taken.
