---
name: access
description: "Who can reach a host and how, in one pass via scripts/access.py: root login, password authentication, weak algorithms, missing limits in front of sshd, authorized keys without an owner or past their rotation or under the size bar, one key on several accounts, passwordless sudo rules, accounts the standards do not name, and how many independent ways in exist. Use when asked who can log in to a server, before hardening ssh, before removing a key, or when a host has only one way in."
---

# Access

One pass over everything that decides who reaches this host. Reads only: nothing is written, nothing is removed, and the pass runs as the reading account, which has no privilege.

Nothing under `ssh.*`, `key.*`, `fw.*`, `sudo.*` or `user.*` may change until this pass has run and `access.single-path` reads zero. The reason is in [../ops/references/risk-classes.md](../ops/references/risk-classes.md).

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <host>
   bash ../setup/scripts/remote.sh --to <reading account from that output> \
     scripts/access.py <access flags from that output> \
     > <workspace>/machines/<host>/audits/YYYY-MM-DD-access.json
   ```

   The script paths are relative to this skill's directory. A flag the workspace left blank is absent on purpose: that check does not run on this host. Run the script without `--json` first when you only need to look.
   Done when the JSON holds a `counts` block and the account count matches what the host actually carries. A count of zero means the pass did not reach the host, not that nobody can log in.

2. **Rank the findings, do not list them.** Order by the ladder in the router, not by how many keys a check touched. Look each id up in [../ops/references/fixes.md](../ops/references/fixes.md) for the fix on this host's control plane, the class, and the measure.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Act by class, never by judgment, and never before the gate.** Gate 2 first: two independent ways in, each answering from a freshly opened connection, a backup copy, an armed rollback timer. Then the class from the table decides the flow.
   Done when every action taken has a class recorded, an armed timer that was later cancelled, and every refused one has a reason.

4. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <account or setting> --action "<what happened>" --class <class> \
     --then "<number> count" --status applied
   ```

   The number comes from the finding's `measure` block: the target's own entry under `by` for a row about one account, `value` for a row about the host. A finding nobody acted on is not a row.
   Done when each row names the check id, the class that actually ran, a measure the same script recomputes, and a verify date.

## Interpretation

- `access.single-path` is a precondition, not only a priority. A host with one way in cannot be hardened at all, because every hardening step needs something to fall back on.
- The check counts the ways in that carry a proof date in `access_paths`. A name somebody typed is a belief; `scaffold.py --flags` leaves an undated entry out and names it, so the number is of paths that answered and not of paths that were meant to.
- Password authentication is counted per place that permits it. A global `no` with a `Match` block that says `yes` for one group is one finding with one target, and the fix is in the file holding that block, not another global line.
- The weak algorithm list is a judgement about what should no longer be offered, not a standard. It is an argument, so a host that has a reason can replace it.
- A key's age is read from the file it sits in, not from its comment. A comment is what someone typed once; a file's write time is what the host knows.
- `key.orphan` needs `allow_users` to be filled. Without it an orphan key cannot be told from a wanted one, so the check reports a note instead of a number.
- The pass reads names, sizes and settings. It never reads a private key and never reads a file's contents looking for a secret; that is a different check with a different fix.
