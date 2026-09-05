---
name: setup
description: Set up the developer experience workspace: one private repository holding config, standards, and a folder per machine (audits, log, proposals), plus the pointer that tells later sessions where it is. Run once per machine, again when a machine is added.
disable-model-invocation: true
argument-hint: "[machine]"
---

# DX setup

Scaffold the workspace every other `jorekai-dx:*` skill reads and writes. Prompt driven: explore, present, confirm, write. The layout and the log format live in [templates/workspace-README.md](templates/workspace-README.md); read it once before step 2 so the questions make sense.

The workspace is a private repository of its own, outside every project, because its subject is the machine and not one repository. It records paths, host names, and later command history, so it is never a public repository and never a folder inside a customer project.

## Steps

1. **Explore the machine before asking anything.**
   - Project roots: the directories that actually hold repositories, and how deep they nest. A generated project list already on the machine counts as a root of its own.
   - Identity: the name and address commits carry, and the account remotes belong to.
   - History: the login shell, its history file, a history database that also records exit code and duration, and the directory an agent keeps session transcripts in. Record what exists; record blank for what does not.
   - Containers: whether a container runtime is installed at all.
   - An existing workspace at the proposed path, and whether it is already a repository.
   Done when every key in [templates/config.md](templates/config.md) and [templates/machine-config.md](templates/machine-config.md) has a value from the machine or is marked unknown.

2. **Present and ask, one section per message**, recommended answer first so the user can accept in a word:
   - The workspace path, and that it becomes a private repository. Name what goes in it.
   - The unknown keys from step 1.
   - The standards: what every project must carry, how long a merged branch or an unused image may sit before it is reported, how much free space is the floor, how many days pass between an applied action and its verdict. A value left blank turns its check off, which is a valid answer and better than a number nobody believes.
   - The pointer: whether a line naming the workspace path goes into the agent file the user already keeps for every session. Without it, every session has to be told the path again.
   Done when every value is confirmed or explicitly left blank.

3. **Write.**

   ```bash
   python3 scripts/scaffold.py --root <workspace path> [machine]
   ```

   The script path is relative to this skill's directory. Without a machine argument it uses this machine's host name. The script creates the folders, copies the templates without overwriting, and regenerates the machine table in the workspace `README.md`. Then fill `config.md`, `standards.md`, and `machines/<hostname>/config.md` with the confirmed values.

   Make the workspace a repository and commit the first state, so every later change to standards and every verdict has a history. If the user agreed to the pointer, add this line to the agent file they named, replacing an existing one in place:

   ```markdown
   ## Developer experience

   DX workspace: `<workspace path>/README.md` (layout, log format, standards). Read `standards.md` and `machines/<hostname>/config.md` before running any `jorekai-dx:*` skill; every change to a machine gets a row in that machine's `log/`, and a commit that carries one out in a project ends with the trailer `DX-Log: <row id>`.
   ```

   Done when `python3 scripts/scaffold.py --root <workspace path> --check` prints `ok`, no confirmed value is still a parenthesised placeholder, and the workspace has its first commit.

4. **Hand off.** `jorekai-dx:and-now` reads the workspace and names the stage and the next step. Run it now to see the machine start from an empty log, and weekly from then on.

## Rules

- A blank value is a decision, not a gap. It means the check that reads it does not run on this machine.
- Standards are shared across machines, limits are not. A machine that needs a different floor for free space overrides it in its own `config.md` and leaves the standard alone.
- The workspace is never a folder inside a project, and never the skills collection itself.
- A second machine gets a second folder under `machines/`, not a second workspace.
