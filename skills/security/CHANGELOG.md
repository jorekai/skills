# Changelog

One entry per `jorekai-security` version. The version at the top equals `version` in `skills/security/.claude-plugin/plugin.json`; `scripts/check.sh` checks that. Dates are ISO.

## 0.2.0 (2026-09-11)

- Changed: `jorekai-security:secrets`, `jorekai-security:deps`, `jorekai-security:pipeline`, and `jorekai-security:review` print the counting line as a bar of `FAIL`, `WARN`, notes, passed; the cost of a finding stands in its own column after the check id instead of in parentheses; the `next` zone carries the gate on its own line where one applies; the passed list wraps. `jorekai-security:grade` prints a bar of `due`, `won`, `returned`, `no-change` and one line per row of the verdict, the row id, the check id, and `then`/`now` in their own columns. `jorekai-security:report` prints a bar of `won`, `no-change`, `returned`, `open`, and identical notes about a missing audit fold into one line naming every tool. `jorekai-security:and-now` prints each `now` step with the skill name as its own aligned column, and `then` as one line. Reason: `decisions/0028`. The router's `## Reading a report` names the bar and the columns.

## 0.1.2 (2026-09-10)

- Fixed: `jorekai-security:secrets` promised a finding names the path, the line, the kind and a fingerprint, and then printed repository text. `ASSIGNMENT` captured the whole name around the credential word, every filter applied to the value alone, and the name went into the report and into the committed audit as the finding's kind. The character set carried the dot, so a customer domain in a setting name passed through whole. The regex now captures the credential word instead of the name, and a finding reads `value named by secret`.

## 0.1.1 (2026-09-10)

- Fixed: one accepted list reaches every pass, and no pass filtered it by the check ids it owns. A credential somebody accepted in `config.md` stood in the pipeline report as a note under `build.token-broad`, a check that never counted it, and the header said findings were left out of counts that pass never took. Every pass now keeps the entries whose check id it owns and drops the rest, the way `decisions/0015` gives every check id exactly one owner.
- Fixed: `secrets.py` derived `in_tree` from the accepted list instead of from what it found, so accepting a `cred.tracked` finding handed the same value to `cred.history` as a finding of its own and failed `cred.unrotated` with it. One value needed two acceptance lines to go quiet. Which check a value lands in is now settled before anybody accepts anything.

## 0.1.0 (2026-09-09)

- Added: the theme itself. A security review was a single pass that read a diff, named what was wrong, and left nothing behind: the next pass began at zero, and nobody could say whether last month's fix still held. `jorekai-security` gives that work the loop the other themes already have, a router, a ladder, a fixes table, and four measuring passes over a code repository.
- Added: `jorekai-security:setup` takes a repository into its own private workspace, detects the ecosystem, and writes the trust model that every later pass reads: the entry points that carry attacker-controlled input, the frameworks that already mitigate, the secret store and the way a credential is rotated. That file is the reason the second pass is sharper than the first.
- Added: `jorekai-security:secrets` reads file contents and the history, in three checks from `cred.tracked` to `cred.unrotated`. It wraps an installed scanner and falls back to its own patterns, and it never prints a value.
- Added: `jorekai-security:pipeline` reads the workflows a forge runs with the repository's own rights, in four checks from `build.untrusted-checkout` to `build.script-injection`.
- Added: `jorekai-security:deps` resolves the lock files to package versions, asks the vulnerability database, and separates what is known to be exploited from what merely has an advisory.
- Added: `jorekai-security:review` traces attacker-controlled input to a dangerous sink and writes every accepted finding as a rule, so a later pass recomputes the same measure instead of asking the model again.
- Added: `jorekai-security:grade` settles a log row whose verify date has passed, and `jorekai-security:and-now` names the stage, the open items in ladder order, and the next verify date. `jorekai-security:report` writes the month from the audits and the log alone.
