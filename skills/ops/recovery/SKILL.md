---
name: recovery
description: "What survives this host, in one pass via scripts/recovery.py: backup targets with no copy, copies past their window, copies that all sit on this host, targets nobody restored, secrets that are missing, readable beyond their owner, or sitting in a work tree, credentials passed to a unit as environment variables, and what the journal is allowed to keep. Use when asked whether a host is backed up, before a risky change, after a restore, when a secret may be exposed, or when logs are eating the disk."
---

# Recovery

One pass over what is left when this host is gone: the copies of its data, the secrets on it, and what its journal keeps. Reads only: nothing is copied, removed, or rotated, and the pass runs as the reading account.

The pass reads names, modes, write times, and unit settings. It never reads the contents of a secret, so a finding names the file and the unit, never the value. An audit that carried a value would move the secret into the workspace.

A target the workspace does not name is not measured. The list in `config.md` is the question this pass answers, so a database nobody wrote down is a gap in the workspace and not a clean result.

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <host>
   bash ../setup/scripts/remote.sh --to <reading account from that output> \
     scripts/recovery.py <recovery flags from that output> \
     > <workspace>/machines/<host>/audits/YYYY-MM-DD-recovery.json
   ```

   The script paths are relative to this skill's directory. A flag the workspace left blank is absent on purpose: that check does not run on this host. Run the script without `--json` first when you only need to look.
   Done when the JSON holds a `counts` block and the number of backup targets matches what `config.md` names. A count of zero means the workspace names nothing, not that nothing needs a copy.

2. **Rank the findings, do not list them.** Order by the ladder in the router, not by how many files a check touched. Look each id up in [../ops/references/fixes.md](../ops/references/fixes.md) for the fix on this host's control plane, the class, and the measure. The answer is one table, `check id | cost | targets | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Fix a copy before a mode, and a mode before a bound.** A missing copy is the only finding here that a later day cannot repair. A secret that is readable too widely is repaired by narrowing it, which needs the account that owns the service, so it is agreed before it runs.
   Done when every action taken has a class recorded, and every refused one has a reason.

4. **Prove a copy by restoring it, never by listing it.** A restore into a scratch location, then the date of that restore written into the target's entry in `config.md`. A copy nobody has read back is a file, not a backup.
   Done when the target carries the date of a restore that finished, or the finding stays open.

5. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <target or path> --action "<what happened>" --class <class> \
     --then "<number> count" --status applied
   ```

   The number comes from the finding's `measure` block: the target's own entry under `by` for a row about one target, `value` for a row about the host. A finding nobody acted on is not a row.
   Done when each row names the check id, the class that actually ran, a measure the same script recomputes, and a verify date.

## Interpretation

- A copy on this host is a copy of a file, not a copy of the host. It survives a deleted directory and a bad deployment, and it does not survive the disk, the provider, or the account. That is why `backup.offsite` counts every target whose copies all sit here, even when each of them is fresh.
- A copy off this host cannot be dated by a pass that only reads this host. The report says so rather than calling it fresh: an undated copy is a belief, the same way an undated way in is.
- The age of a copy is the newest file inside it, never the directory's own write time. A directory keeps the time of its last change, which a copy written into it leaves behind.
- `backup.untested` is the only check here that measures a habit. A restore test is what tells a copy from a file, and it is graded on the date it last finished, not on whether a job exists.
- A secret readable by group or other is counted once per file. The mode is the finding; who the group holds is a question for the host's owner, and the fix narrows the file rather than the group.
- A secret inside a work tree is a finding while nothing ignores it. A history keeps what it is given, so this is one of the few findings a later commit cannot take back, which is why it stands beside a missing copy on the first rung.
- Environment variables set for a unit are exposed to unprivileged clients over D-Bus, and they travel down the process tree across security boundaries, so a credential passed that way is readable by more than the service. Credentials loaded by the service manager are the documented way to pass one. Source: `references/sources.md` beside the router.
- A unit that loads an environment file is a note and not a finding. The names inside it would say whether a credential is passed that way, and reading them means reading the values, which this pass does not do.
- The journal keeps what two bounds allow: a time bound and a size cap. Both have defaults, so an unset bound is not an unbounded journal; it is a decision nobody made, and the finding says that rather than claiming a number.
- A journal that is volatile keeps nothing across a reboot. That is a note here, because it is a choice a host may have made on purpose, and the log rows that would prove it live in the same journal.
