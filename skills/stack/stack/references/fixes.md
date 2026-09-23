# Fixes by check id

One row per check id a shipped tool emits: what the finding means, what closes it, the risk class the action runs under, the rung of the ladder it sits on, and the measure that grades it later with the unit that measure is written in. The rung is what orders a report: a pass ranks its findings by this column, so the first line of a report and the first item of `jorekai-stack:and-now` are the same piece of work. `scripts/check.sh` compares the unit here against the unit the script reports for that id, and `scripts/check_rungs.py` compares the rung here against the ladder in `jorekai-stack:and-now`.

Every measure counts what the finding costs, so lower is better and zero means the check no longer fires. Two units differ from `count`: `guard.coverage` is written in `percent` (the points missing below the bar), `guard.slow` in `seconds` (the seconds over the time bar). A measure the pass could not take is `null`, never zero (`decisions/0030`): a coverage report that does not exist, a gate that never wrote its timing.

The namespaces `decl`, `boundary`, `adapter`, `lock`, `escape`, `guard` and `dead` belong to this theme. Where a neighbouring theme measures something that sounds alike, the border runs in the table under `## Borders` below, and the other theme's fixes table says the same.

The secret scanner is wired into the generated gate and measured by nobody here: `cred.*` stays with `jorekai-security`. The pipeline checker and the advisory lookup are not wired into this gate; `jorekai-security` runs `build.*` and `dep.*` as skills of its own, over the same repository, and neither is counted here. This theme measures whether a wired guard is wired and cannot be walked around; `jorekai-security` grades what a wired or a separately run guard finds.

## Declaration

| Check | What it means | Fix | Class | Rung | Measure |
|---|---|---|---|---|---|
| `decl.absent` | `stack.yaml` is missing, or a section every pass reads is missing from it | Run `jorekai-stack:choose`, or add the section the pass names | `ask` | 1 | Missing declarations (`count`) |
| `decl.unmatched` | An entry of the declaration points at a file or a directory that does not exist | Correct the entry, or delete it with its reason | `ask` | 1 | Entries that point at nothing (`count`) |
| `decl.generated` | A file the generator owns was changed by hand, so the next regeneration overwrites the change | Move the change into the generator's input or into a file the project owns, then regenerate | `confirm` | 6 | Generated files changed by hand (`count`) |
| `decl.undeclared` | A package sits in the tree and `workspaces` does not name it, so no boundary applies to it | Add the package with its allowed imports, or delete it | `confirm` | 8 | Packages the declaration does not name (`count`) |
| `decl.undecided` | An open decision is past the date it was to be taken by | Take it and move the line into the declaration, or set a new date with the reason | `ask` | 8 | Open decisions past their date (`count`) |

## Escapes

| Check | What it means | Fix | Class | Rung | Measure |
|---|---|---|---|---|---|
| `escape.unenforced` | A guard the declaration names is required by no branch protection, admin bypass is on, or code owner review is not required, so a local flag or an administrator walks past it | Make the gate a required check on the default branch with admin bypass off and code owner review required, record the date, and capture the protection for `--protection-file` | `ask` | 2 | Guards nothing enforces on the server (`count`) |
| `escape.unowned` | A contract file has no owner, so a change to the bars is a commit and not a review | Add the path to `CODEOWNERS` with a person who is not the agent | `ask` | 2 | Contract files without an owner (`count`) |
| `escape.expired` | A waiver is past its date, so the suppression it covered is red again | Fix the code the waiver excused, or set a new date with a reason, through review | `ask` | 2 | Waivers past their date (`count`) |
| `escape.type` | A type suppression stands in the code and no waiver names its file and line | Fix the type, or add a waiver with reason, date and owner, through review | `ask` | 3 | Type suppressions without a waiver (`count`) |
| `escape.lint` | A lint suppression stands in the code and no waiver names its file and line | Fix the line, or add a waiver with reason, date and owner, through review | `ask` | 3 | Lint suppressions without a waiver (`count`) |
| `escape.test` | A test is skipped or made exclusive and no waiver names its file and line | Repair the test, or add a waiver with reason, date and owner, through review | `ask` | 3 | Skipped or exclusive tests without a waiver (`count`) |

## Guards

| Check | What it means | Fix | Class | Rung | Measure |
|---|---|---|---|---|---|
| `guard.missing` | The declaration names a guard and gives it no command, or the command names a script that is not there | Write the command, or regenerate the script the generator owns | `confirm` | 4 | Declared guards without a command (`count`) |
| `guard.disabled` | A guard runs, and its own configuration switches off what the declaration promised | Remove the switch; the bar it protects stands in `stack.yaml` | `ask` | 4 | Guards their own configuration disables (`count`) |
| `guard.unwired` | A guard the declaration names runs in no workflow, so the server never sees its result | Run the one gate command in the workflow that is the required check | `confirm` | 4 | Declared guards no workflow runs (`count`) |
| `guard.unbarred` | A bar in the declaration stands in no configuration, so no tool enforces its number | Point the configuration at the bar in `stack.yaml`; the generated files already do | `confirm` | 4 | Bars that stand in no configuration (`count`) |
| `guard.rulegap` | The declaration names a rule class and no rule file carries it, or the rule has no test that proves it fires | Write the rule with its two fixtures, or remove the class from the declaration through review | `confirm` | 4 | Rule classes without a rule or without a test (`count`) |
| `guard.coverage` | The last unit run covered fewer lines than the bar | Test what the report names as uncovered; lowering the bar is a review of `stack.yaml` | `ask` | 7 | Points below the coverage bar (`percent`) |
| `guard.assertionless` | A test block asserts nothing, so it passes whatever the code does | Add the assertion the test name promises, or delete the test | `ask` | 7 | Tests without an assertion (`count`) |
| `guard.slow` | The last full gate took longer than the time bar, and a slow gate is a gate people skip | Cache what the gate rebuilds, or split the slow step behind the fast ones | `confirm` | 7 | Seconds over the time bar (`seconds`) |

## Dead code

| Check | What it means | Fix | Class | Rung | Measure |
|---|---|---|---|---|---|
| `dead.export` | More exports than the bar allows are imported by nobody | Delete them, or lower the visibility to the file | `confirm` | 7 | Unused exports over the bar (`count`) |
| `dead.file` | More files than the bar allows are reachable from no entry point | Delete them | `confirm` | 7 | Unreachable files over the bar (`count`) |
| `dead.dep` | More dependencies than the bar allows are imported by nobody | Remove them from the manifest and reinstall | `confirm` | 7 | Unused dependencies over the bar (`count`) |

## Lock

| Check | What it means | Fix | Class | Rung | Measure |
|---|---|---|---|---|---|
| `lock.incomplete` | A workspace manifest names a dependency the lock file does not resolve, so two machines install two trees | Reinstall so the lock is written again, then commit it | `confirm` | 5 | Manifests the lock does not resolve (`count`) |
| `lock.runtime` | A place that pins the runtime or the package manager disagrees with the declaration | Set every pinning place to the value in `stack.yaml` | `confirm` | 5 | Pinning places that contradict the declaration (`count`) |

## Boundaries and adapters

| Check | What it means | Fix | Class | Rung | Measure |
|---|---|---|---|---|---|
| `boundary.crossed` | A file imports across an edge `workspaces` does not allow | Import the port or the package the line allows, or allow the edge through review | `ask` | 6 | Imports over a forbidden edge (`count`) |
| `boundary.cycle` | Two packages import each other, so neither can be built or tested alone | Move the shared part into the package both may import | `ask` | 6 | Package pairs that import each other (`count`) |
| `adapter.bypassed` | A vendor module is imported outside the adapter of its port, so the port no longer hides the vendor | Import the port; the adapter is the only file that names the vendor | `ask` | 6 | Vendor imports outside an adapter (`count`) |
| `boundary.deep-import` | A file imports a path inside another package instead of that package's entry point | Import the package name; export what is needed from its entry point | `confirm` | 7 | Imports past an entry point (`count`) |
| `adapter.missing` | A port lacks one of its parts: the contract, the offline adapter, the wired adapter, or the smoke test | Regenerate the port, or write the missing part | `confirm` | 7 | Missing parts over all ports (`count`) |
| `adapter.untargeted` | The adapter a port declares is not the one the two axes resolve to | Run `jorekai-stack:choose` again, or record the exception in the declaration | `ask` | 7 | Ports whose adapter does not match the axes (`count`) |

## Borders

| This theme | The neighbour | Where the border runs |
|---|---|---|
| `guard.unwired` | `repo.no-ci` in `jorekai-dx` | dx asks whether anything at all runs on push. This theme asks whether the declared guard runs there |
| `lock.incomplete` | `repo.lock-drift` in `jorekai-dx` | dx compares two timestamps. This theme checks whether the lock resolves every workspace manifest |
| `lock.incomplete` | `dep.unresolved` in `jorekai-security` | security asks whether a lock file exists. This theme asks whether it is complete |
| `dead.dep` | `dep.*` in `jorekai-security` | security asks whether a dependency is vulnerable. This theme asks whether it is used at all |
| `decl.*` | `agent.*` in `jorekai-dx` | dx asks whether a session finds its way in every project. This theme asks whether the contract of this one repository holds |

## Fixes

### decl.absent, decl.unmatched

The declaration is the bar every other check reads, so nothing below rung 1 is worth acting on while it is wrong. `jorekai-stack:choose` writes a complete file; a file that exists and lacks a section gets the section from `templates/stack.yaml` in that skill, with the values of this repository. An entry that points at nothing is corrected or deleted, never left for the next pass to report again.

### escape.unenforced

The local hook is fast feedback and a flag walks past it. The lock is the forge: the workflow that runs the gate is a required check on the default branch, a pull request cannot merge while it is red, and neither an administrator nor a merge without a code owner's review can walk past it either. Record the date it was confirmed under `enforcement` in `stack.yaml`, one line per guard, `gate@YYYY-MM-DD`. An entry without a date does not count, the same way an undated way in does not count in `jorekai-ops`.

```bash
gh api -X PUT repos/<owner>/<repo>/branches/<default>/protection \
  -f 'required_status_checks[strict]=true' -f 'required_status_checks[contexts][]=gate' \
  -F 'enforce_admins=true' -f 'required_pull_request_reviews[required_approving_review_count]=1' \
  -f 'required_pull_request_reviews[require_code_owner_reviews]=true'
```

A date in `stack.yaml` is what a person confirmed; it is not what the pass reads as proof. `jorekai-stack:guards` takes `--protection-file` with a capture of the same branch's protection, and a guard counts as enforced only when its name stands among `required_status_checks.contexts` there, `enforce_admins.enabled` is true, and `required_pull_request_reviews.require_code_owner_reviews` is true. Without that file the check stays unknown, never a pass (`decisions/0030`):

```bash
gh api repos/<owner>/<repo>/branches/<default>/protection
```

### escape.unowned

Every file in [contracts.md](contracts.md) has a line in `CODEOWNERS` naming a person. An agent that edits a bar opens a review; a person merges it. The generated `CODEOWNERS` carries every line with a placeholder owner, and the placeholder counts as unowned until a person replaces it.

### escape.type, escape.lint, escape.test, escape.expired

A suppression is red unless a waiver in `stack.yaml` names its file, its line, a reason, an owner and a date. The fix is the code, not the waiver: a waiver is for the case the code cannot be fixed today, and it expires. Adding one is a change to a contract file, so it is a review.

```yaml
waivers:
  - kind: type
    file: packages/ports/src/db/pool.adapter.ts
    line: 84
    reason: "the driver types its return value as any, issue 214"
    until: 2026-12-14
    owner: a-person
```

The waiver check runs in the gate before the typecheck, so a suppression is found by the cheap step and the expensive one never runs for it.

### guard.missing, guard.unwired, guard.unbarred, guard.rulegap

The generated files carry every guard, and the one gate command runs every one of them. A guard that went missing was deleted or renamed by hand, and the fix is to regenerate the file the generator owns (`jorekai-stack:new` with `--check` names it). A guard no workflow runs is wired by making the workflow run the gate command and nothing narrower. A bar that stands in no configuration is pointed at `stack.yaml` again. A rule class without a rule gets the rule and its two fixtures, or leaves the declaration through review.

### guard.disabled

The switches this check reads are a closed list, in [contracts.md](contracts.md): `strict` set to false, a bar rule set to `off`, coverage or assertion checking turned off, a hook skipped, a rule directory ignored. Each is removed; the number it protected stands in `stack.yaml` and moves only through review.

### guard.coverage, guard.assertionless, guard.slow

Coverage is raised by testing what the report names, never by lowering the bar, and the bar moves through review of `stack.yaml`. A test without an assertion is finished or deleted; the runner refuses it at run time, and this check counts it statically so a skipped run does not hide it. A slow gate is split by cost: the cheap steps first, the browser test last, and what a step rebuilds is cached.

### dead.export, dead.file, dead.dep

Delete what nobody uses. The three bars in `stack.yaml` start at zero for a new repository and at the measured count for an adopted one, so the number in the log is a curve that falls, not a light that turns red. Raising a bar is a review.

### lock.incomplete, lock.runtime

Reinstall, commit the lock. Then set every pinning place to the value the declaration holds: the version file, the manifest's `engines` and `packageManager`, the workflow's runtime step, and the container file. A second place with a different number is how two machines install two trees.

### boundary.crossed, boundary.cycle, boundary.deep-import, adapter.bypassed

The edge is the fix, not the import. A file that needs something from a package it may not import gets it through a package both may import, or the edge is allowed in `workspaces` through review. A cycle is broken by moving the shared part down. A deep import becomes an export of the entry point. A vendor import outside its adapter becomes a call on the port, and the adapter stays the one file that names the vendor.

### adapter.missing, adapter.untargeted

`jorekai-stack:new --check` names the missing part and `--wire` writes the adapter the axes resolve to. A port that deliberately runs another adapter records that under `ports` with a reason, and the check reads the reason as the exception.

### decl.generated, decl.undeclared, decl.undecided

A change to a generated file goes into the generator's input or into a file the project owns, then the file is regenerated; the manifest under `.stack/` is what proves it. A package the declaration does not name gets its line in `workspaces` or is deleted. An open decision past its date is taken now, or its date moves with a reason.
