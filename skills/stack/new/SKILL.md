---
name: new
description: "Generate the monorepo a declaration describes: the tree from the official generator, the guards over it, one adapter per port, and a gate that is green before any account exists. Adopt a repository that exists with --adopt. Ends on the green gate and the seven proofs that it turns red."
disable-model-invocation: true
argument-hint: "[directory] [--adopt]"
---

# Stack new

One repository, once, from its `stack.yaml`. The order below is the point: the plan is read before a file is written, the guards are laid out before the app exists, and the gate is green on memory adapters before a single account is created. Needs the declaration from `jorekai-stack:choose`; missing: run that first.

The generator owns what it writes. Every owned file is listed with its hash in the manifest under `.stack/`, so a change made by hand is a finding and not a surprise at the next regeneration.

## Steps

1. **Read the plan before anything is written.**

   ```bash
   python3 scripts/lay.py --root <directory> --plan
   ```

   The script path is relative to this skill's directory. One line per file, `path | action | reason`: `write` for a file that does not exist, `skip` for one the project owns or changed by hand, `replace` for a file of the app generator that the root now carries, `remove` for one the root makes redundant. Show the list; a `skip` with `changed by hand` is a decision for the user, not for the script.
   Done when every line is read and no `skip` is a surprise.

2. **Lay the guards out.**

   ```bash
   python3 scripts/lay.py --root <directory>
   ```

   Writes the root, the packages, the ports on their memory adapters, the rules with their tests, and the manifest. The app directory is left for the generator, so the files that belong inside it wait for step 3.
   Done when the manifest exists and the script names the generator command as the next step.

3. **Run the generator, then lay out again.** `--flags` prints the command, the files it writes that the root replaces, and the files it removes. Run the command as printed, then run step 2 once more so the app directory gets its files.
   Done when the app directory holds the base config and none of the files the plan named for removal.

4. **Wire the ports.**

   ```bash
   python3 scripts/lay.py --root <directory> --wire
   ```

   The two axes of the declaration resolve to one adapter per port; the adapter is copied beside its memory twin, `wired.ts` points at it, its vendor modules enter the ports manifest, the target's host files land in the root, and the wizard for the accounts is written. Then install with the command `--flags` printed, and the browser the runner needs.
   Done when `--check` prints `ok` and every port holds its four parts.

5. **Prove the gate green with nothing set.**

   ```bash
   bash <directory>/scripts/gate.sh
   ```

   No key in the environment, no account, no network. Every port runs on its memory adapter and the exit code is 0. A red step here is a defect of this skill, not of the repository: report it with the guard's line.
   Done when the gate exits 0 and `.stack/gate-times.log` holds its first line.

6. **Prove the gate red, seven times.** Each of these is inserted, must turn exactly the named guard red with file, line and the allowed state in the message, and is reverted before the next: an `as any` (the waiver check), an `it.skip` (the waiver check), an `eslint-disable` (the waiver check), a line added to a generated file (drift), a read of the environment outside the env package (the rule `no-raw-env`), a function grown past the line bar (lint), an export nobody imports (dead code). Show the seven messages.
   Done when all seven were red, each one named the file and the allowed state, and the gate is green again after the last revert.

7. **Hand over.** No table: the generator command that ran, the paths written, the gate's exit code, and the wizard as the next thing a person runs for the accounts and the branch protection. Then `jorekai-stack:guards` and `jorekai-stack:drift` for the baseline.
   Done when the answer ends on the two passes to run next.

8. **Adopt a repository that exists**, instead of steps 2 to 4:

   ```bash
   python3 scripts/lay.py --root <directory> --adopt --plan
   python3 scripts/lay.py --root <directory> --adopt
   ```

   Nothing that exists is overwritten, and every file left alone is named. One waiver is proposed per suppression found, with file, line and a date, and the reason is left empty for a person to write: an entry without one does not count, so the suppressions stay red until somebody says why they stay. The dead-code bars and the coverage bars are set to what the gate measured where it ran once, else they keep the defaults until it did. Then step 5.
   Done when the plan was read, the waivers are in `stack.yaml` waiting for their reasons, and the gate reports what the repository is rather than what it should be.

## Rules

- The generator owns its files (`decisions/0034`). A change to one goes into the templates of this skill or into `stack.yaml`, and the file is regenerated; a file the project has to own leaves the manifest with `--disown`.
- A rule without a test is not run (`decisions/0037`). Every rule this skill writes carries its two fixtures, and the engine refuses one that arrives without them.
- This skill writes no log row. A scaffold runs once and has no measure to recompute later; the rows are written by `jorekai-stack:guards` and `jorekai-stack:drift` from the baseline this skill ends on.
- An adopted repository's waivers wait for a person's reason. The script proposes the entry; it never writes the reason, because whoever enters an exception is not whoever needs it (`decisions/0036`).
- The app generator, its command, and what the root replaces stand in [references/generators.md](references/generators.md). A second generator is a row there and an entry in the script's table, never a second template tree.
- The adapters, their vendor modules and their env keys stand in [../stack/references/ports.md](../stack/references/ports.md); the contract files the generated `CODEOWNERS` covers stand in [../stack/references/contracts.md](../stack/references/contracts.md).
