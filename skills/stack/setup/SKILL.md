---
name: setup
description: "Take a repository into the stack workspace: create its folder, record where the checkout lives and whether the repository exists yet, choose the profile the declaration starts from, and write the pointer so a later session finds the workspace."
disable-model-invocation: true
argument-hint: "[repository]"
---

# Stack setup

One repository, once. The workspace is where findings go; the declaration goes into the repository itself, and this skill records where that repository is so every later pass reads the same checkout.

Nothing in this skill changes the repository it describes. It reads, and it writes into the workspace.

## Steps

1. **Find or create the workspace.** A private repository, separate from every project. Ask for its path, then scaffold this repository into it:

   ```bash
   python3 scripts/scaffold.py --root <workspace path> <slug>
   python3 scripts/scaffold.py --root <workspace path> --check
   ```

   The script paths are relative to this skill's directory. `--check` names a file, a directory or a section that is missing. Add what it names; do not rewrite a file that holds values.
   Done when `--check` prints `ok` and the repository folder holds `config.md`, `audits/`, `log/stack/`, `reports/stack/`, and `proposals/`.

2. **Record the repository.** In `repos/<slug>/config.md`: `path` naming the checkout, `origin_kind` saying who can read the history, `default_branch`, and `state`: `new` when the generator has not run yet, `existing` when a tree with its own history is being adopted.

   `state` decides the hand-over at the end. A wrong value there sends an existing repository through the generator, which overwrites nothing but proposes files that already have an owner.
   Done when `path` names a directory that exists, or a directory that will be created, and `state` is one of the two words.

3. **Choose the profile.** Offer three and name what each costs, then write the chosen name into `standards.md` beside `verify_window_days` and `audit_max_age_days`:

   - `strict`: the highest coverage bars and the tightest complexity limits; every function short, every branch tested.
   - `standard`: the defaults of the declaration template; the bar a new team keeps without a fight.
   - `lenient`: room for a tree that grows fast, at the price of larger functions and thinner tests.

   The numbers behind each name stand in the declaration the next skill writes, not here. `allow_safe` stays `no` unless this repository is worked on alone.
   Done when `profile` names one of the three and both windows carry a number of days.

4. **Write the pointer.** Add a block to the agent file the project already keeps, or will keep once the generator ran, so a later session does not have to be told again:

   ```markdown
   Stack workspace: `<workspace path>/README.md`. Read `standards.md` and `repos/<slug>/config.md`
   before running any `jorekai-stack:*` skill; every change gets a row in that repository's
   `log/stack/`, and a commit that carries one out ends with the trailer `Stack-Log: <row id>`.
   ```

   Done when the block names a path that exists.

5. **Hand over.** A `state: new` repository goes to `jorekai-stack:choose`, which writes the declaration. A `state: existing` one goes to `jorekai-stack:new` with `--adopt --plan`, which names what it would write and what it leaves alone before anything is written. After either, `scaffold.py --snapshot` copies the declaration into this folder.
   Done when the next command is named and `scaffold.py --flags` prints a repository path.

## Rules

- The workspace is its own private repository, one folder per repository (`decisions/0035`). Nothing this theme measures is committed to the repository it measures; the declaration is the one file that lives there, because the project's own tooling reads it.
- This skill changes nothing in the target repository. The first change is `jorekai-stack:new`, and every later one is an action of the loop with a class and a log row.
- The declaration lives in the repository and its snapshot in the workspace. The passes note when the two differ; the repository's file is the truth, the snapshot is the record of what was measured against.
- An accepted risk is written once under `accepted` in `config.md`, with the reason and the date, and it stops being a finding.
- `scaffold.py --flags` prints the arguments the measuring scripts take, built from these files. A step that retypes those values gets them wrong.
