---
name: pipeline
description: "What the forge runs with this repository's own rights, in one pass via scripts/pipeline.py: a privileged trigger that checks out code from a fork, a shell step that puts a value from outside straight into the command line, a workflow that names no rights for its token, and a third-party action bound to a tag rather than to a commit. Use when asked whether the build can be taken over, before adding a workflow that touches a pull request from a fork, after a dependency of the build changed, or as the pipeline half of a security sweep."
---

# Security pipeline

One pass over the files that run code with this repository's rights. Reads only: nothing is triggered, no token is used, no network call is made.

The rung matters more than the numbers. Whoever can run code in this pipeline can also change the fix that is about to be pushed through it, which is why this stands above every dependency and every finding in the code itself.

A file the reader cannot follow is reported as unread, with the reason. It is never counted as clean, because a workflow nobody parsed is the one that carries the surprise.

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <slug>
   python3 scripts/pipeline.py <pipeline flags from that output> --json \
     > <workspace>/repos/<slug>/audits/YYYY-MM-DD-pipeline.json
   ```

   The script paths are relative to this skill's directory. Run it without `--json` first when you only need to look. A flag the workspace left blank is absent on purpose: that check runs on its own defaults.
   Done when the JSON holds a `counts` block and the workflow list says which files were read.

2. **Rank the findings, do not list them.** Order by the ladder in the router, not by how many lines a check touched. Look each id up in [../security/references/fixes.md](../security/references/fixes.md) for the fix, the class, and the gate. The answer is one table, `check id | cost | targets | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Split the privileged workflow before anything else.** A trigger that carries this repository's secrets and a checkout of somebody else's code belong in two files: one that reads with the rights it needs and writes nothing, one that runs the fork's code with nothing to steal. Narrowing the token on a workflow that still runs the fork's code moves the problem, it does not close it.
   Done when no workflow both runs with this repository's rights and executes code from a fork, or the one that does stands under `accepted` with a reason and a date.

4. **Pin what moves, then write down who does not have to be pinned.** A commit is looked up once and pasted with the version in a comment beside it. An owner as trusted as this repository goes into `trusted_owners` in `config.md`, so the next pass stops asking.
   Done when every third-party reference names a commit, or its owner stands in `trusted_owners`.

5. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <workflow file> --action "<what happened>" --class <class> \
     --then "<number> <unit>" --status applied
   ```

   The number and the unit both come from the finding's `measure` block, and the unit is copied as it stands there. The target is the workflow file, which is the key the finding measures per, so the row grades against that file and not against the repository. A finding nobody acted on is not a row.
   Done when each row names the check id, the class that actually ran, a measure the same script recomputes, and a verify date.

## Interpretation

- A privileged trigger alone is not a finding, and a checkout of a fork alone is not one either. The finding is the pair, in one file, because that is what puts somebody else's code next to this repository's secrets.
- The same workflow counts once, however many steps check out the fork. One file, one decision, one row.
- An expression that reaches a shell is substituted before the shell reads the line, so quoting it inside the command changes nothing and a comment marker in front of it hides nothing. That is why the reader keeps what stands behind a `#` inside a script.
- A value that already needs write access to set is not a value from outside. An input to a manual run is trusted here for the same reason an environment variable is, and the list of what counts as outside stands in the script beside the check.
- A workflow with rights on every job and none at the top is settled. A workflow with rights on some jobs is not: the job without them is the one that gets the default.
- A tag is a name somebody else can move. A commit is not. An action in this repository is this repository, so it needs no pin, and an image reference is a different question with a different fix and is left alone here.
- This pass reads one forge's workflow format. Another forge's pipeline is not measured and is not clean; it is simply not read, and nothing here says otherwise.
- Every finding in this pass is a file in this repository, which is why the classes here are the mildest in the theme. The cost of being wrong is a build that fails, not a door that stays open.
