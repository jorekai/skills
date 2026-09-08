---
name: exposure
description: "What a host offers the network and what stands in front of it, in one pass via scripts/exposure.py: listening ports open to anywhere, ports nobody named, a control panel on the open network, a firewall that is not filtering, rules for ports nothing serves, certificates past their date or close to it, and units that should watch failed attempts and are not. Use when asked what is reachable on a server, before opening a port, when a certificate is close to running out, or after a firewall change."
---

# Exposure

One pass over what this host answers on and what filters it. Reads only: no port is closed, no rule is written, and the pass runs as the reading account.

A change to a rule or a port is a change to a way in, so gate 2 runs first: two independent ways in that answered from fresh connections, a backup copy, and a rollback timer cancelled only after a new connection succeeds. The gate stands in [../ops/references/risk-classes.md](../ops/references/risk-classes.md).

A port the workspace does not name is a finding, not an exception. The expected list in `config.md` is the question this pass answers, so a host with no list produces one finding per socket, which is the honest answer for a host nobody has described. A socket list that was read and holds nothing is an answer too: it writes the zero that settles a row about a port somebody closed.

## Steps

1. **Take the arguments from the workspace, then run the pass once.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --flags <host>
   bash ../setup/scripts/remote.sh --to <reading account from that output> \
     scripts/exposure.py <exposure flags from that output> \
     > <workspace>/machines/<host>/audits/YYYY-MM-DD-exposure.json
   ```

   The script paths are relative to this skill's directory. A flag the workspace left blank is absent on purpose: that check does not run on this host. Run the script without `--json` first when you only need to look.
   Done when the JSON holds a `counts` block and the socket list is not empty. An empty list means the pass did not reach the host, not that the host answers on nothing.

2. **Rank the findings, do not list them.** Order by the ladder in the router, not by how many rules a check touched. Look each id up in [../ops/references/fixes.md](../ops/references/fixes.md) for the fix on this host's control plane, the class, and the measure. The answer is one table, `check id | cost | targets | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

3. **Pass the gate before a rule changes, then act by class.** Everything under `fw.*` waits for gate 2, and so does the first rule on a host that had none. A port is closed by stopping what listens on it or by binding it to one address, never by a rule that leaves the service answering behind a filter nobody rereads.
   Done when every action taken has a class recorded, an armed timer that was later cancelled, and every refused one has a reason.

4. **A port that stays open gets a name, not an exception.** What the standards should have listed goes into the expected list with the service behind it, so the next pass measures against the host as it is meant to be.
   Done when every port that is staying stands in `config.md`, or is a finding still open.

5. **Log what was done, not what was found.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <port, rule, or certificate> --action "<what happened>" --class <class> \
     --then "<number> <unit>" --status applied
   ```

   The number and the unit both come from the finding's `measure` block, and the unit is copied as it stands there. A row written in another unit than the check measures in can never be graded: the target's own entry under `by` for a row about one port, `value` for a row about the host. A finding nobody acted on is not a row.
   Done when each row names the check id, the class that actually ran, a measure the same script recomputes, and a verify date.

## Interpretation

- A port open to anywhere and a port bound to one address are different findings, and they sit four rungs apart. The first is reachable by whatever can route to this host; the second costs tidiness and a little attack surface inside the network. Nothing is counted twice: a socket is one or the other.
- The address a socket binds to is what decides this, never the firewall in front of it. A service bound to every interface behind a closed rule is one rule change away from being open, which is why the socket is the finding and the rule is only the fix.
- A panel port is counted apart from every other port because the surface it opens changes the host itself, and it is counted only there: a port the workspace calls a panel is left out of the other two checks, so no port appears in two rows. It is also the one port where the fix is usually an address restriction rather than a closed port, since the owner still needs it.
- Not reading a firewall and reading one that filters nothing are different answers. The first carries no number, because a measure there would settle a log row with a figure nobody took.
- A firewall that holds rules and is not filtering is worse than no firewall, because the rules read as protection to whoever looks. A firewall that takes everything it has no rule for still filters, and the note beside the finding says which of the two it is.
- A rule counts only when it lets something in. A rule that drops a port, one about what this host sends, and one about what it forwards are all rules, and none of them opens a port. A rule that names a range or a service is named as that and never resolved into ports, because the answer would be a guess.
- A rule for a port nothing serves is not dangerous today. It is counted because it says the host once served something there, and nobody wrote down that it stopped.
- A certificate is read by its end date alone. Whether the chain is complete, whether the name matches, and whether a client trusts the issuer are different questions with different fixes, and this pass makes none of those claims.
- A unit that watches failed attempts is named by the workspace, not by this pass. What counts is that the unit the host relies on is running; which one it is stays a decision of the host's owner.
- The parsers read output shapes. The options are documented and stand in `references/sources.md` beside the router; the column order of a socket list and the exact wording of a firewall status are not, and both are named as heuristics there.
