# Fixes by check id

One row per check id a shipped tool emits: what the finding means, the risk class it runs under, the rung of the ladder it sits on, and the measure that grades it later with the unit that measure is written in. The rung is what orders a report: a scanner ranks its findings by this column, so the first line of a report and the first item of `jorekai-security:and-now` are the same piece of work. `scripts/check.sh` compares the unit here against the unit the script reports for that id, so a row graded in another unit is graded against nothing.

The gates in [risk-classes.md](risk-classes.md) stand above every class here. Gate 1 covers `cred.*`, gate 2 covers every fix that touches authentication, authorization, sessions, cryptography, or the rights a token carries.

The namespaces `dep`, `cred`, `build` and `vuln` belong to this theme. `secret` belongs to `jorekai-ops` and describes a credential on a host; `repo` and `alert` belong to `jorekai-dx`. A log row carrying one of those is another theme's business, and `jorekai-security:grade` says so rather than guessing.

Two borders run against `jorekai-stack`, which wires the secret scanner into a generated gate and measures whether it runs and cannot be walked around, while this theme grades what the scanner finds and runs the pipeline checker and the advisory lookup over the same repository itself. `dep.unresolved` asks whether a lock file exists; `lock.incomplete` there asks whether it is complete. `dep.*` asks whether a dependency is vulnerable; `dead.dep` there asks whether it is used at all.

## Secrets

| Check | What it means | Class | Rung | Measure (unit) |
|---|---|---|---|---|
| `cred.tracked` | A credential value stands in a file the repository tracks, so every clone has it | `ask` | 1 | Credentials in tracked files (`count`) |
| `cred.history` | A credential is reachable through the history, even where the file is gone today | `ask` | 1 | Credentials reachable in the history (`count`) |
| `cred.unrotated` | A credential this pass found carries no rotation date, so nobody has replaced it | `ask` | 1 | Findings without a rotation date (`count`) |

## Pipeline

| Check | What it means | Class | Rung | Measure (unit) |
|---|---|---|---|---|
| `build.untrusted-checkout` | A workflow that runs with the repository's own rights checks out code from a fork | `ask` | 2 | Privileged workflows that check out fork code (`count`) |
| `build.script-injection` | A shell step puts a context value straight into the command line it runs | `ask` | 2 | Shell steps that interpolate a context value (`count`) |
| `build.token-broad` | A workflow carries no explicit rights, or grants a broad one such as `write-all`, so its token can write more than it needs | `confirm` | 2 | Workflows without narrow rights for their token (`count`) |
| `build.action-unpinned` | A third-party action is bound to a tag, and a tag moves | `confirm` | 2 | Third-party actions without a commit sha (`count`) |
| `build.runner-exposed` | A workflow reachable by a trigger from outside runs on a self-hosted runner, which a compromised job can persist in | `ask` | 2 | Workflows reachable from outside that run on a self-hosted runner (`count`) |

## Deps

| Check | What it means | Class | Rung | Measure (unit) |
|---|---|---|---|---|
| `dep.known-exploited` | An installed version carries an advisory whose identifier stands in the catalogue of exploited flaws | `ask` | 3 | Dependencies with an exploited advisory (`count`) |
| `dep.fix-available` | An installed version carries an advisory, and a version that closes it is published | `confirm` | 3 | Dependencies with a published fix (`count`) |
| `dep.vulnerable` | An installed version carries an advisory and no published fix | `ask` | 5 | Dependencies with no published fix (`count`) |
| `dep.unresolved` | A manifest has no lock file beside it, or a requirement is not pinned to one version, so nothing says which versions are installed | `confirm` | 6 | Manifests with nothing that resolves them (`count`) |

## Review

| Check | What it means | Class | Rung | Measure (unit) |
|---|---|---|---|---|
| `vuln.injection` | Attacker-controlled input reaches an interpreter, a query, or a shell without being bound | `ask` | 4 | Open rules of this class (`count`) |
| `vuln.authz` | A handler is missing the authorization check its neighbours carry | `ask` | 4 | Open rules of this class (`count`) |
| `vuln.deserialize` | Untrusted data reaches a deserializer that can build objects or code | `ask` | 4 | Open rules of this class (`count`) |
| `vuln.ssrf` | The caller decides the host or the protocol of an outgoing request | `ask` | 4 | Open rules of this class (`count`) |
| `vuln.crypto` | Home-made cryptography, a broken algorithm, or a certificate check that was switched off | `ask` | 4 | Open rules of this class (`count`) |
| `vuln.exposure` | A secret or a personal detail reaches a log line or a response body | `confirm` | 5 | Open rules of this class (`count`) |

## Fixes

### cred.tracked, cred.history, cred.unrotated

Gate 1 applies, and the order below is the fix. A history keeps what it was given, so removing the line is the last step and never the first.

1. Rotate the credential at the provider. Write the new value into the secret store `config.md` names.
2. Write the rotation date into `config.md` under `rotated`, one line per finding: `<fingerprint> <provider> YYYY-MM-DD`. That line is what closes `cred.unrotated`.
3. Remove the value from the working tree and add the path to the ignore file.
4. Only then decide about the history. Rewriting it is a second log row, agreed with everyone who has a clone, because every fork and every mirror keeps the old objects.

```bash
# what the fix removes from the tree, per finding, after the rotation is recorded
git rm --cached <path>
printf '%s\n' '<path>' >> .gitignore
```

A value that was never pushed is still rotated when it reached a shared machine, a log, or a paste. The question is not whether the commit is public. It is who has read the value since it was written.

### build.untrusted-checkout

The privileged trigger and the checkout of fork code are separated. One workflow reads the pull request with the rights it needs and writes nothing; a second one runs the fork's code with no secrets and no write rights.

```yaml
# the privileged half: no checkout of the fork's head
permissions:
  pull-requests: write
```

```yaml
# the unprivileged half: the fork's code runs here, with nothing to steal
on: [pull_request]
permissions:
  contents: read
```

A workflow that must have both is a design decision, and it belongs in `config.md` under `accepted` with the reason and the date.

### build.script-injection

The value goes through an environment variable, and the shell reads the variable. Quoting the expression inside the command is not the fix: the value is substituted before the shell ever sees it, so quoting happens too late.

```yaml
env:
  TITLE: ${{ github.event.pull_request.title }}
run: echo "$TITLE"
```

### build.token-broad

Every workflow carries a `permissions` block, read-only at the top, widened per job where a job needs it. A repository default that is already read-only is worth setting as well, and it does not replace the block: the block is what a reader of the file can see. `write-all`, and a bare `write`, name every scope at once. Replace either with the one or two scopes the job actually writes.

```yaml
permissions:
  contents: read
```

### build.action-unpinned

A third-party action is bound to the full commit sha, with the human-readable version in a comment beside it, so the next update is a decision and not a surprise.

```bash
gh api repos/<owner>/<repo>/commits/<tag> --jq .sha
```

```yaml
uses: owner/action@<40 character sha>  # v4.2.1
```

An action from the same owner as the repository is a different case: it is as trusted as the repository itself, and pinning it costs an update step for no gain. Record that once under `accepted`.

### build.runner-exposed

A self-hosted runner should almost never serve a workflow a trigger from outside can start. Any user who can open a pull request or a comment can then run code on that runner. A compromised job can leave code behind for the run after it (`references/sources.md`). Two ways close this, in order of preference.

1. Move the job back to a runner GitHub hosts. That is the fix when the job needs nothing the self-hosted machine alone provides.
2. Where the job needs the self-hosted machine, split it the way `build.untrusted-checkout` splits a privileged checkout. An unprivileged job reads the event first and writes nothing. The self-hosted job runs only after a maintainer approves it, and nothing from outside reaches it directly.

A workflow that must keep running on request from outside is a design decision, and it belongs in `config.md` under `accepted` with the reason and the date.

### dep.known-exploited, dep.fix-available

Raise the version to the one the advisory names as fixed, in the manifest and in the lock file, then run the test suite. A direct dependency is one edit. A transitive one is an override or a resolution in the manifest, and the override is removed again when the parent catches up.

```bash
# the version that is installed, before anything moves
<package manager> why <name>
```

Where no upgrade is possible today, the row is not closed: it becomes a proposal with the reason, and `dep.known-exploited` stays open. A finding that is answered by a note keeps costing what it costs.

### dep.vulnerable

No published fix means the decision is about the call site, not the version: remove the dependency, stop calling the affected function, or put a check in front of it. All three are ordinary changes with a test. Waiting is also an answer, and it is written under `accepted` with a date to look again.

### dep.unresolved

Generate the lock file and commit it. Until it exists, nothing can say which versions are installed, so every other dependency check on that manifest measures nothing. Where the requirement is the gap, pin it to one version with `==` instead of a range or a bare name. A `pom.xml` closes no row here today. This pass reads no Maven lock format, so the manifest stays open until one is added.

### vuln.injection, vuln.authz, vuln.deserialize, vuln.ssrf, vuln.crypto, vuln.exposure

Gate 2 applies to every fix here that touches authentication, authorization, sessions, or cryptography: a test that fails before the change and passes after it, in the same commit.

The fix is the one the class names, and it is the same everywhere:

- Bind the value instead of formatting it into the statement. Parameters for a query, an argument list for a process, a template that escapes by default.
- Put the authorization check where the data is fetched, not where the page is drawn, and let the check name the actor and the object.
- Deserialize into a declared shape, never into whatever the input describes.
- Compare an outgoing address against a list of allowed hosts after it is resolved, and refuse a protocol nobody named.
- Use the platform's own library for hashing, signing, and random values, and let the certificate check stay on.
- Keep the value out of the log line: log the identifier, not the object.

Then close the rule: the finding is over when `review.py` counts zero for it, which happens when the sink is gone from every file the rule's glob matches, or the mitigation pattern matches somewhere in that file. The match is file-wide and not line-local, so a mitigation pattern loose enough to hit a comment or an unrelated function closes the rule without the sink having moved. Write it narrow enough that only the real handling matches it.

To close a rule through a code change, read at least one matching file and every other file its path matches. A missing or unreadable file leaves the result unknown (`null`). Check whether it moved or became unreadable, then rerun review. Recording an accepted risk also removes the rule from the count; it does not prove a code fix.
