---
name: review
description: "Where attacker-controlled input reaches a dangerous sink in this repository, traced from the entry points the trust model names, verified against the code, and written down as a rule so scripts/review.py recomputes the same measure later. Covers injection, authorization, deserialization, outgoing requests, cryptography, and values that reach a log or a response. Use when asked to review code or a pull request for security, to find vulnerabilities, or as the code half of a security sweep."
---

# Security review

Two questions, in this order: can somebody outside reach this code, and does what it does with that input hold. A pattern that no entry point reaches is not a finding here, and a value from a setting, an environment variable, or a constant is not attacker-controlled.

What separates this pass from a one-off review is what it leaves behind. Every accepted finding becomes a rule in the workspace, and from then on a script counts it. A model finds; a script measures, twice, weeks apart (`decisions/0026`). A finding that cannot be written as a rule is a proposal, not an action, and it belongs in `proposals/`.

The bar is high on purpose. A report of everything that could be wrong is a report nobody finishes, and the second one is read even less than the first.

## Steps

1. **Set the scope, and read what is already known.** The scope is a diff, a directory, or the whole repository, and it is said out loud before anything is read. Then, from the workspace: `entrypoints` and `mitigations` in the repository's `config.md`, `accepted`, and every rule already in `rules/`.

   The trust model is what makes this pass sharper than the last one. An entry point nobody wrote down turns the review into a list of patterns, and a framework that already escapes turns half the list into noise.
   Done when the scope is named, and every entry point and mitigation that applies to it is on the table.

2. **Find candidates, and send the reading out.** One subagent per entry point or per group of them, never one for the whole repository. Each one traces the input forward: where it enters, what it passes through, where it lands. Give each the entry points, the mitigations, and the classes in the fixes table.

   What comes back is one table, `file:line | class | entry point | the path from one to the other | confidence`, at most 60 words per row, and nothing else. The files a subagent read stay in its context.
   Done when every entry point in scope has been traced once, and the candidates are one table.

3. **Verify each candidate on its own, and try to break it.** One subagent per candidate, and its task is to refute: find the check that already stops this, the framework that escapes it, the caller that only passes a constant. A candidate survives when the subagent cannot refute it and can name the input, the path, and what an attacker gets.

   Drop everything that does not clear the bar in `confidence_floor`. Drop a value that comes from a setting, an environment variable, or a constant. Drop a pattern in a file that only runs in a test.
   Done when every candidate is either refuted with a reason or accepted with an input, a path, and an outcome.

4. **Write one rule per accepted finding, then measure.**

   ```bash
   python3 scripts/review.py --root <repository> \
     --rules-dir <workspace>/repos/<slug>/rules --json \
     > <workspace>/repos/<slug>/audits/YYYY-MM-DD-review.json
   ```

   A rule file is `<check id>-<n>.json` and holds `id`, `check`, `path` as a glob, `sink` as a regular expression matching the code as it stands, optionally `mitigation` matching what would mean it is handled, plus `why`, `written` and `commit`. The sink pattern is narrow enough to name this occurrence and loose enough to survive a rename of a variable. The mitigation is matched against the whole file, not against the lines around the sink, so a pattern that also hits a comment or an unrelated function closes the rule while the sink stands untouched.
   Done when every accepted finding has a rule, the pass runs, and the count per class equals the number of findings that are still open.

5. **Rank the findings, do not list them.** Order by the ladder in the router. Look each id up in [../security/references/fixes.md](../security/references/fixes.md) for the fix, the class, and the gate. The answer is one table, `check id | cost | targets | fix | class`, at most five rows, one row per check id; the rest of the shape is in the router's `## Writing the answer`.
   Done when every `FAIL` id has a named fix and an owner, and the rest is one sentence.

6. **Fix under gate 2, then log what was done.**

   ```bash
   python3 ../setup/scripts/scaffold.py --root <workspace> --append-row --check-id <id> \
     --target <rule id> --action "<what happened>" --class <class> \
     --then "<number> <unit>" --status applied
   ```

   Every fix here that touches authentication, authorization, sessions, or cryptography passes gate 2 first: a test that fails before the change and passes after it, in the same commit. The number and the unit come from the finding's `measure` block, and the target is the rule id, because that is the key the finding measures per.
   Done when each row names the check id, a measure the same script recomputes, and a verify date, and every fix under gate 2 has its test in the same commit.

## Interpretation

- Attacker-controlled is decided by the trust model, not by the shape of the code. The same line is a finding in a request handler and nothing at all in a build script that takes its argument from a constant.
- A framework that escapes, binds, or authorises by default is a mitigation, and a mitigation that is recorded stops a whole class from being reported. What is not recorded is reported, which is the honest direction to be wrong in.
- A rule answers whether the sink is still written the way it was written. That is weaker than whether the code is safe, and it is the question a script can answer twice. The strong question is answered once, by the review, and the rule is what carries that answer forward.
- A rule whose path matches no file reads zero and needs a person, because a file that was deleted and a flaw that was fixed look the same to a matcher.
- A class with no rule is not reported as clean. Nothing has looked at it yet, and a zero would say the opposite.
- A finding in a file that only runs in a test is not a finding. A credential in one is, and that belongs to another pass.
- The bar drops findings that are real but unproved. That is the trade this pass makes, and the ones it drops come back next time with the same evidence, which is cheaper than a report nobody trusts.
- A verified finding that cannot be written as a rule is still worth having. It goes to `proposals/` with its evidence, and it stays out of the log until somebody finds a check for it.
