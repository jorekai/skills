---
name: machine
description: Local resources of this machine via scripts/machine.py: free space against the floor, cache directories, rebuildable dependency and build trees, available memory, and the storage a container runtime reports as reclaimable. Use when the disk is full, when the machine is slow, when containers eat space, or as the resource half of a sweep.
---

# Machine

What this machine has left and what is eating it. Reads `machines/<hostname>/config.md` for the project roots and the floor for free space, and `standards.md` for the retention. No workspace: ask for the roots and the floor, and skip the log steps.

Nothing is removed by this skill's measurement. What may follow is decided by the risk class of each finding, in [../dx/references/risk-classes.md](../dx/references/risk-classes.md).

## Steps

1. **Measure once, with the roots.** Passing the project roots is what turns "the disk is full" into a list of trees that a manifest rebuilds. `scaffold.py --flags` prints the roots and the arguments the floor and the runtime record.

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags
   python3 scripts/machine.py <paths from that output> <machine flags from that output> --json > <workspace>/machines/<hostname>/audits/YYYY-MM-DD-machine.json
   ```

   The script paths are relative to this skill's directory. The pass reads sizes off the disk and takes about a minute on a machine with large caches, so run it in the background and do something else. Without roots it still measures the volume, memory, caches, and the container runtime.
   Done when the JSON holds a `counts` block and `disk.low` reports a free figure. An `INFO` on a check means its source is missing on this machine, not that the check passed.

2. **Rank by what is actually blocking.** Free space below the floor outranks everything else here, because nothing else finishes on a full disk. Otherwise take the biggest reclaimable class first: caches, then container storage, then rebuildable trees. Look each id up in [../dx/references/fixes.md](../dx/references/fixes.md). The answer is one table, `check id | cost | targets | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when the order is by bytes returned per risk taken, not by how untidy something looks.

3. **Act by class.** `safe` runs and reports what came back. `confirm` shows the exact paths and the total first, asks once, then runs. `ask` prints the command and stops. A rebuildable tree inside a repository is removed only when that repository is clean and pushed, which `jorekai-dx:repos` answers.
   Done when every removal names the class it ran under and the bytes it returned.

4. **Log the measure, then re-measure at the verify date.** One row per check id, written by the scaffold, with the finding's own measure as `Then`:

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <path> --action "<what happened>" --class <class> --then "<number> GB" --status applied
   ```

   The number comes from the finding's `measure` block: the path's own entry under `by`, or `value` for the whole machine. Free space is measured as the bytes missing from the floor, so a row that reaches zero says the floor is met.
   Done when each row carries a number the script produces, not an estimate, and a verify date.

## Interpretation

- The reclaimable figure a container runtime prints is an upper bound. Measure again after each class instead of trusting the total.
- Removing anonymous volumes is a different decision from removing named ones: a named volume holds data that nothing else holds. The runtime's default removal leaves unused volumes alone for that reason.
- A cache directory is not waste. It is a bet that the next install is soon. Emptying it costs one slow build and returns the space immediately.
- `mem.pressure` is a symptom, not a task. A machine that reaches it during ordinary work needs a decision about what runs on it, and there is nothing to clean up.
- A rebuildable tree in a repository nobody is working on is the cheapest space on the machine. In a repository being worked on it is the most expensive, because the rebuild interrupts.
