---
name: setup
description: "Take a repository into the security workspace: detect the ecosystem, write the trust model that says which input an attacker controls and what already mitigates, record the secret store and the way a credential is rotated, choose the profile that sets the bar, and measure once."
disable-model-invocation: true
argument-hint: "[repository]"
---

# Security setup

One repository, once. The order below is the point: the trust model is written before the first pass runs, because a pass without it reports every pattern it can match and a person then sorts the list by hand, every week, forever.

Nothing in this skill changes the repository it describes. It reads, and it writes into the workspace.

## Steps

1. **Find or create the workspace.** A private repository, separate from every project. Ask for its path, then scaffold this repository into it:

   ```bash
   python3 scripts/scaffold.py --root <workspace path> <slug>
   python3 scripts/scaffold.py --root <workspace path> --check
   ```

   The script paths are relative to this skill's directory. `--check` names a file, a directory or a section that is missing. Add what it names; do not rewrite a file that holds values.
   Done when `--check` prints `ok` and the repository folder holds `config.md`, `audits/`, `log/security/`, `rules/`, and `proposals/`.

2. **Detect the ecosystem.** Read, without asking: the manifests and lock files that are committed, the languages by file count, and what the forge runs. Write them into `languages`, `package_managers` and `ci` in the repository's `config.md`, with `path` naming the checkout.

   A manifest with no lock file beside it is not a gap in this step. It is the first finding of the dependency pass, and it stays for that pass to report.
   Done when `path` names a directory that exists and `package_managers` names one entry per committed manifest, or `none`.

3. **Write the trust model.** One entry per place where input from outside enters this repository, as `kind@path`: an HTTP route file, a command line entry point, a queue consumer, a webhook handler, a scheduled job. Then `mitigations`: what already escapes, binds, or authorises by default here.

   This is the file that decides whether a matched pattern is a finding. A repository with no entry points recorded gets every pattern reported, which is the honest answer for a repository nobody has described, and it is why this step is not optional.
   Done when every entry point carries a kind and a path that exists, and `mitigations` names what is in force or is deliberately empty.

4. **Record the secret store and the rotation path.** Where a credential lives instead of the repository, and the page or command that replaces one. A value that cannot be rotated in a documented way is a finding waiting to become an incident, and naming that now costs one line.
   Done when `secret_store` names a place and `rotation_runbook` names something a person can follow without asking anyone.

5. **Choose the profile.** Offer three, name what each costs, and write the chosen values into `standards.md`. A value left blank turns its check off, which is a decision and beats a number nobody believes. `allow_safe` stays `no` unless this repository is worked on alone.
   Done when `profile` names one of the three and every value under it is either filled or deliberately blank.

6. **Note the scanners.** `scaffold.py --flags` prints which of the optional tools this machine has. Install the ones that are missing and wanted, or record that they are absent. A missing tool lowers coverage and stops nothing.
   Done when the scanner line is read out loud, and every tool that is missing is either installed or named as missing.

7. **Write the pointer.** Add a block to the agent file the project already keeps, so a later session does not have to be told again:

   ```markdown
   Security workspace: `<workspace path>/README.md`. Read `standards.md` and `repos/<slug>/config.md`
   before running any `jorekai-security:*` skill; every change gets a row in that repository's
   `log/security/`, and a commit that carries one out ends with the trailer `Security-Log: <row id>`.
   ```

   Done when the block names a path that exists.

8. **Measure once.** `jorekai-security:secrets`, then `jorekai-security:pipeline`. The first pass on a repository that has never been swept reports a lot; that is the baseline, not a to-do list. A credential it finds is the exception: that one is acted on today, under gate 1.
   Done when both audits are in `audits/` and `jorekai-security:and-now` names a stage.

## Rules

- The workspace lives outside every project and holds one folder per repository (`decisions/0025`). Nothing this theme produces is committed to the repository it measures: a findings file inside a public repository publishes the findings.
- This skill changes nothing in the target repository. The first change is an action of the loop, with a class and a log row.
- The trust model is data, not memory. Whatever a session learns about which input is attacker-controlled goes into `config.md`, or the next session learns it again.
- An accepted risk is written once under `accepted`, with the reason and the date, and it stops being a finding. A finding that is answered in conversation comes back next week.
- `scaffold.py --flags` prints the arguments the measuring scripts take, built from these files. A step that retypes those numbers gets them wrong.
