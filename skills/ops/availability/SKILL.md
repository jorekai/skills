---
name: availability
description: "Whether the services a host is supposed to run are running, firing, current and hardened, in one pass via scripts/availability.py: units that are down or failed, units that restart too often, timers that are not enabled or past their elapse, unit options the profile requires, a deploy path behind the commit it should be at, a repository with no identity file, and a service with no deploy path. Use when a service is down, a timer did not fire, after a deployment, or when asked what is running on a server."
---

# Availability

One pass over every service the standards name. Reads only: nothing is started, stopped, or written, and only the commit distance looks at a repository, locally and without fetching.

A service the workspace does not name is not measured. The list in `config.md` is the question this pass answers, so an unlisted service is a gap in the workspace, not a clean result.

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <host>
   bash ../setup/scripts/remote.sh --to <reading account from that output> \
     scripts/availability.py <availability flags from that output> \
     > <workspace>/machines/<host>/audits/YYYY-MM-DD-availability.json
   ```

   The script paths are relative to this skill's directory. When the host writes its own report on a timer, fetch it instead of sending the script: `remote.sh --to <account> --fetch <path>`.
   Done when the JSON names every service the workspace lists and none it does not.

2. **Rank the findings, do not list them.** What is down comes before what is only behind, and both come before what is merely unhardened. Look each id up in [../ops/references/fixes.md](../ops/references/fixes.md) for the fix on this host's control plane, the class, and the measure. The answer is one table, `check id | cost | targets | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Act by class, never by judgment.** Every id here is `ask` in the table: a restart on a host that serves other people is an outage, however short. Print the command with its reason, and let the person decide.
   Done when every action taken has a class recorded, and every refused one has a reason.

4. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <service> --action "<what happened>" --class <class> \
     --then "<number> count" --status applied
   ```

   The number comes from the finding's `measure` block: the service's own entry under `by`.
   Done when each row names the check id, a measure the same script recomputes, and a verify date.

## Interpretation

- A failed unit and a stopped unit are two findings with two fixes, so a unit in state `failed` is counted once, under `service.failed`, and not also as down.
- `service.restarts` measures only what is over the bar, so a service allowed three restarts and taking seven costs four. The bar is in `standards.md`, and a blank bar turns the check off.
- A systemd timestamp carries a zone abbreviation, which is ambiguous, so the date and the clock are read and the zone is not. The grace window absorbs the offset; a timer inside that window is not reported. This is a heuristic and it is listed as one.
- `unit.unhardened` takes an exception per unit with a reason, recorded once in `config.md`. An option that breaks the service it protects is a fact about that service, not a judgement to make again every week.
- `code.behind` is measured from what the clone already holds. When the named commit is not there the pass says so instead of guessing a distance: the number needs a fetch first, and this pass does not fetch.
- A service with no deploy path is `deploy.absent` and not `service.down`, even when it is also not running. The fix is a deployment, not a restart.
