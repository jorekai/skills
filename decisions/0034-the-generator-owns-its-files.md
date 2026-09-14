# 0034: The generator owns its files

Date: 2026-09-14

## Context

`jorekai-stack:new` writes about sixty files into a repository: the gate, the hooks, the workflow, the configurations that carry the bars, the env schema, the offline adapters. A week later somebody edits one of them by hand, because it is a file in the tree and files in the tree get edited. The next time the generator runs, it either overwrites the edit or refuses to touch the file, and both are wrong in silence: the first loses work, the second leaves a file that no longer does what the declaration says.

The scaffold of every other theme avoids the question by never overwriting anything. That works for a workspace, where a file is written once and then holds values. It does not work for a guard, which has to be regenerated when the declaration changes.

## Decision

The generator owns what it writes, and records it: `.stack/generated.json` carries one hash per owned file. `jorekai-stack:new --check`, the generated `scripts/drift.mjs`, and `decl.generated` in `jorekai-stack:drift` recompute the hashes, so a hand edit is a finding and not a surprise.

A change to an owned file goes into the generator's input, which is `stack.yaml` or the templates of the skill, and the file is regenerated. A file the project has to own is taken out of the manifest with `--disown <path>`, which records the path so the next run skips it. The list of owned files stands in `references/contracts.md`; the contracts of the ports, the smoke tests, the rules and the app are not on it, because those are the project's.

## Consequences

Regenerating is safe, because the manifest says which files the generator may replace and which it may not. The first run of `--adopt` on an existing repository writes only what does not exist and owns only what it wrote, so nothing of the repository's own becomes the generator's by accident.

A generated file changed by hand is a rung 6 finding with class `confirm`: the fix is to regenerate, and the way back is the copy the dry run writes first. The finding is worth its rung because the next file in the tree is written like the one beside it.
