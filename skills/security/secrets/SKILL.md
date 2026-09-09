---
name: secrets
description: "Credentials in the files a repository tracks and in the history behind them, in one pass via scripts/secrets.py: a value in a tracked file, a value still reachable through the history where the file no longer carries it, and a value this pass found that carries no rotation date. Use when asked whether a key leaked, before making a repository public, after a credential was pasted into a file, or as the first pass of a security sweep."
---

# Security secrets

One pass over what this repository already gave away. Reads files only: nothing is rotated, nothing is removed, and no value is sent anywhere.

A value is never printed and never written into the workspace. A finding names the path, the line, the kind, and a fingerprint, which is what lets two passes weeks apart talk about the same credential without either of them holding it.

This is the first rung of the ladder because it is the only finding an edit cannot undo. A history keeps what it was given, so the fix begins at the provider and the log row is the rotation. Gate 1 in [../security/references/risk-classes.md](../security/references/risk-classes.md) says the order.

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <slug>
   python3 scripts/secrets.py <secrets flags from that output> --json \
     > <workspace>/repos/<slug>/audits/YYYY-MM-DD-secrets.json
   ```

   The script paths are relative to this skill's directory. Run it without `--json` first when you only need to look. The first pass over a long history takes minutes; a window shortens it and says so in the report.
   Done when the JSON holds a `counts` block and says whether the history was read and whether a scanner was used.

2. **Rank the findings, do not list them.** Order by the ladder in the router. Look each id up in [../security/references/fixes.md](../security/references/fixes.md) for the fix, the class, and the gate. The answer is one table, `check id | cost | targets | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Rotate first, and rotate before the tree is touched.** Gate 1 applies to every finding here. The value is replaced at the provider, the new one goes into the secret store, and only then does anything change in the repository. Removing the line first hides the finding from the next pass while the value keeps working.
   Done when every value that was ever pushed has a new value at its provider, or a sentence saying why it cannot be rotated and who accepted that.

4. **Record the rotation, then clean the tree.** One entry per value in `rotated` in the repository's `config.md`, as the fingerprint from the finding, the provider, and the date. That entry is what settles `cred.unrotated`; a rotation nobody wrote down is a rotation the next pass cannot see.
   Done when every finding has a `rotated` entry or stands under `accepted`, and the ignore file covers the path so the value does not come back.

5. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <path or fingerprint> --action "<what happened>" --class <class> \
     --then "<number> <unit>" --status applied
   ```

   The number and the unit both come from the finding's `measure` block, and the unit is copied as it stands there. The target is the file for a row about a place, and the fingerprint for a row about a value, because those are the keys the finding measures per. The action names the rotation, never the value.
   Done when each row names the check id, the class that actually ran, a measure the same script recomputes, and a verify date.

## Interpretation

- The two place checks do not overlap. A value that is in the tree is counted there; the history check is what is left over, which is a value every clone still holds and no file shows any more. Rewriting the history is what moves that number, and rotating is what makes the number stop mattering.
- Rewriting a history does not reach a fork, a mirror, or a clone somebody made last week. That is why the rotation is the fix and the rewrite is a second, separate decision.
- A value that was never pushed is still rotated when it reached a shared machine, a build log, or a chat. The question is not whether the commit is public. It is who has read the value since it was written.
- A name that says credential proves nothing, so the value decides: long enough, mixing at least two kinds of character, random enough, and not one of the stand-ins people write. That is a heuristic tuned to miss a passphrase of ordinary words rather than to report every path in the repository.
- A provider's own format needs no name beside it and is matched on its own. The list of formats is in the script; a provider nobody wrote down there is not covered, and an installed scanner is what closes that gap.
- Two readers that see the same line saw one credential. They match different spans of the same value, so their fingerprints differ and the place is what they agree on.
- A rotation date is recorded per value, not per place. One value in three files is one rotation and three cleanups.
- The pass reads what the repository tracks. An untracked file is not read here, and a credential file that nothing ignores is a different check in a different theme.
