---
name: deps
description: "Which installed dependency carries a published advisory and which one is already being exploited, in one pass via scripts/deps.py: the lock files resolved to versions, then the advisory database, the catalogue of exploited flaws, and the exploitation probability. Also names a manifest with no lock file beside it. Use when asked whether a dependency is vulnerable, after a lock file changed, when an advisory is announced, or as the dependency half of a security sweep."
---

# Security deps

One pass over what actually gets installed. Reads the lock files, then asks the advisory database about the versions it found. Nothing is installed, nothing is upgraded, and no manifest is written.

This pass needs the network and says so in the report. A downloaded catalogue is kept in the workspace cache with the date it was fetched, so a later pass runs without the network and says how old its answer is. A question the cache cannot answer carries no measure rather than a zero.

A package counts in one check only: exploited, then fixable, then the rest. That order is the whole point of the pass, because a list of every advisory sorted by severity is what nobody acts on.

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <slug>
   python3 scripts/deps.py <deps flags from that output> --json \
     > <workspace>/repos/<slug>/audits/YYYY-MM-DD-deps.json
   ```

   The script paths are relative to this skill's directory. Run it without `--json` first when you only need to look. `--offline` reads the cache only, which is the right flag when the network is not there or not wanted.
   Done when the JSON names the lock files it read, the number of packages, and where its answer came from.

2. **Rank the findings, do not list them.** Order by the ladder in the router. Look each id up in [../security/references/fixes.md](../security/references/fixes.md) for the fix, the class, and the gate. The answer is one table, `check id | cost | targets | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Raise the versions that have somewhere to go.** A direct dependency is one edit in the manifest and one in the lock. A transitive one is an override, and the override carries the date it can be removed again. Run the test suite before the change is logged: a bump that breaks the build is not a fix that held.
   Done when every package that has a published fix is either at that version, or stands under `accepted` with the reason and the date.

4. **Decide about the ones with nowhere to go.** No published fix means the decision is about the call site: remove the dependency, stop calling the affected part, or put a check in front of it. Waiting is also an answer, and it is written down with a date to look again.
   Done when every package without a fix has one of those four answers written next to it.

5. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <ecosystem>/<package> --action "<what happened>" --class <class> \
     --then "<number> <unit>" --status applied
   ```

   The number and the unit both come from the finding's `measure` block, and the unit is copied as it stands there. The target is the package without its version, because the version is what the fix changes and a row has to survive that. A finding nobody acted on is not a row.
   Done when each row names the check id, the class that actually ran, a measure the same script recomputes, and a verify date.

## Interpretation

- The three vulnerability checks do not overlap. A package that is being exploited is counted there and nowhere else, so raising it moves one number down and none up.
- Exploited means one of two things, and the report says which: an identifier that the catalogue of exploited flaws names, or a probability at or above the floor in `standards.md`. A high probability is a forecast, not an observation, which is why the floor is a value somebody chose and not a default this pass hides.
- An advisory with no published fix is not less serious than one with a fix. It is less actionable, which is a different thing, and it sits one rung lower for that reason alone.
- The lock file is what gets installed, so it is what is read. A range in a manifest describes what could be installed, which is a question about the future and not about this repository today.
- A development dependency is installed on the machine that builds, and that machine holds the token that publishes. It is counted like every other package, and a repository that disagrees writes that down under `accepted` with its reason.
- The target of a row is the package without its version. The version is what a fix changes, and a row that names it can never read zero.
- The readers cover the common shape of each lock format. A format none of them reads produces no packages from that file, and the manifest beside it is reported as unresolved, so an unread file counts as a gap and not as a pass.
- A first pass on an old repository reports a lot. That is the baseline. What matters at the second pass is which of the three numbers moved.
