---
name: drift
description: "Whether the tree still matches its declaration, in one pass via scripts/drift.py: a declaration missing a section or pointing at nothing, a generated file changed by hand, a package the declaration does not name, an open decision past its date, a lock that does not resolve a workspace manifest, a pinning place that contradicts the declared runtime, an import over a forbidden edge, two packages importing each other, an import past an entry point, a vendor module outside its adapter, a port missing a part, and a port whose adapter is not the one the axes resolve to. Use after a dependency or lock change, after adding a package or an import across packages, when an adapter or a generated file was edited, as the weekly pass, or when asked whether the tree still matches the declaration."
---

# Stack drift

One pass over the tree against `stack.yaml`. Reads the declaration, the lock, the manifests, the import lines and the generated-files manifest. Runs nothing, installs nothing, and writes nothing into the repository.

The declaration is the bar every other check reads, so a pass on a repository whose declaration is missing or unread reports that first and measures nothing that depends on it. What the tree alone answers is still measured: the parts of every port, the packages without a line, and the pairs that import each other.

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <slug>
   python3 scripts/drift.py <drift flags from that output> --json \
     > <workspace>/repos/<slug>/audits/YYYY-MM-DD-drift.json
   ```

   The script paths are relative to this skill's directory. Run it without `--json` first when you only need to look. `--snapshot` names the workspace's copy of the declaration, and the report notes the keys on which the two differ.
   Done when the JSON says whether the declaration was read, how many source files it scanned, and carries one item per check id.

2. **Rank the findings, do not list them.** Order by the ladder in the router. Look each id up in [../stack/references/fixes.md](../stack/references/fixes.md) for the fix, the class, and the gate. The pass already ranks by that ladder, and `--explain RANK` prints the chain behind one line: what it means, where it comes from, the fix, the way back, and what closes it. The answer is one table, `check id | cost | where | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Put the declaration right first.** A missing section, an entry that points at nothing, a port off its axes: each is an edit to `stack.yaml`, and that file changes through review, never on the default branch. Everything below rung 1 waits, because it is measured against this file.
   Done when the pass reports the declaration as read and `decl.absent` and `decl.unmatched` are zero, or a review carrying the edit is open.

4. **Act by rung, one class at a time.** An edge, a cycle or a vendor import is fixed in the code: the import moves to the entry point or the port, or the edge is allowed through review. A lock is reinstalled and committed. A generated file changed by hand is regenerated after its change went into the generator's input. Print the exact edit for a `confirm` finding and ask once; a finding classed `ask` is handed over with its reason.
   Done when every finding acted on names the file, the line, and the state the rule allows.

5. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <path or package> --action "<what happened>" --class <class> \
     --then "<number> <unit>" --status applied
   ```

   The number and the unit both come from the finding's `measure` block, and the unit is copied as it stands there. A finding nobody acted on is not a row.
   Done when each row names the check id, the class that actually ran, a measure the same script recomputes, and a verify date.

## Interpretation

- **An unread declaration is not a clean one.** A file the reader cannot follow, because of an anchor, a second document or a tab, leaves every dependent check without a number. The first action is to make the file readable; the rest of the report says nothing until then.
- **A cycle is `FAIL` and a deep import is `WARN`.** Two packages that import each other can no longer be built or tested alone, and every file added to either deepens it. A deep import is the same convention breaking one file at a time, and it costs less today.
- **The fifteen axis pairs are a table**, held in the script and in [../stack/references/ports.md](../stack/references/ports.md). A port that runs another adapter on purpose is not wrong; it is data, written under `port_exceptions` with its reason, and the check reads the entry as the exception.
- **The snapshot note carries no measure.** The workspace keeps a copy of the declaration so a person can see what changed since the last pass; the copy is refreshed when the change was meant, and the repository's file is reverted when it was not.
- **A manifest that is missing is a note, not a pass.** Without `.stack/generated.json` nothing says which files the generator owns, so `decl.generated` carries `null`; `jorekai-stack:new` with `--check` writes the manifest again (`decisions/0030`).
- **The import scanner reads text.** An import built from a variable is not an edge, and a relative import that leaves its workspace counts both as an edge and as a deep import, because it bypasses the entry point either way.
- **A first pass on an adopted repository reports a lot.** That is the baseline. What matters at the second pass is which numbers moved, and `--previous` prints the direction beside each.
