---
name: setup
description: "Take a host into the machines workspace: detect what owns its configuration, create the reading account and the changing account, prove both from a fresh connection, choose the profile that sets the bar, and list the services."
disable-model-invocation: true
argument-hint: "[host]"
---

# Ops setup

One host, once. The order below is the point: the second way in exists before anything hardens the first, because the connection that would repair a mistake is the one the mistake closes.

## Steps

1. **Find or create the workspace.** The same private repository the machine skills use. Ask for its path, then scaffold this host into it:

   ```bash
   python3 scripts/scaffold.py --root <workspace path> <host>
   python3 scripts/scaffold.py --root <workspace path> --check
   ```

   The script paths are relative to this skill's directory. `--check` names a section a shared file is missing, which happens when the other theme created it. Add the named sections; do not rewrite the file.
   Done when `--check` prints `ok` and the host folder holds `config.md`, `audits/`, `log/ops/`, and `proposals/`.

2. **Detect what owns the configuration.** Read, in one connection: the release file, the panel version files, the init system, the active firewall, the package manager, and whether unattended upgrades exist. Write the answer into `control_plane` in the host's `config.md`, with its version. Nothing detected is `none`, which is an answer and not a gap.

   The detected value decides which block of a fixes row applies later. A host where this is blank gets guessed fixes, so this is not optional.
   Done when `control_plane` names a product and a version, or `none`.

3. **Create the reading account.** A login shell, no sudo, its own key pair generated on the workstation. Install the public half, then open a **new** connection as that account and read one file. A pass that measures must carry no privilege.
   Done when a connection opened after the account existed answers, and nothing about it appears in any sudoers file.

4. **Create the changing account.** Its own key pair, and one sudoers file holding only the commands the fixes table names. Validate that file before it counts, because a sudoers file that does not parse takes sudo from everyone. Then open a new connection as that account and run one permitted command.
   Done when the sudoers file validates, the account runs one permitted command, and a command outside the file is refused.

5. **Record the ways in, and the console.** Write both accounts into `access` (reading account first, it is the one the measuring pass uses) and every independent way in into `access_paths`, each as `name@YYYY-MM-DD` with the day a fresh connection answered on it. A way in with no date is not counted, because the count is what decides whether anything may touch access at all. A console at the hosting provider gets a date only after someone has opened it.
   Done when `access_paths` names at least two dated entries that share no account and no key, and `scaffold.py --flags` lists no unproved way in.

6. **Choose the profile.** Offer three, name what each costs, and write the chosen values into the host's section of `standards.md`. A value left blank turns its check off, which is a decision and beats a number nobody believes. `allow_safe` stays `no` unless the host is asked to be brisk.
   Done when `profile` names one of the three and every value under it is either filled or deliberately blank.

7. **List the services.** One entry per service the host is supposed to run: its unit, its timer, its deploy path, its repository, and the commit it should be at. Entries are separated by a semicolon, because an entry carries commas of its own. Then the options every unit must carry, and the exceptions, each with the reason it exists.
   Done when `services` names every unit that should be running, and every exception carries a reason.

8. **Write the pointer.** Add a block to the agent file the user already keeps, naming the workspace path and the two accounts, so a later session does not have to be told again:

   ```markdown
   Ops workspace: `<workspace path>/README.md`. Read `standards.md` and `machines/<host>/config.md`
   before running any `jorekai-ops:*` skill; every change to a host gets a row in that host's
   `log/ops/`, and a commit that carries one out ends with the trailer `Ops-Log: <row id>`.
   ```

   Done when the block names a path that exists.

9. **Measure once.** `jorekai-ops:access`, then `jorekai-ops:availability`. The first pass on a host that has never been swept reports a lot; that is the baseline, not a to-do list.
   Done when both audits are in `audits/` and `jorekai-ops:and-now` names a stage.

## Rules

- The workspace is shared with the machine skills and holds one folder per host and one log folder per theme (`decisions/0015`). This skill writes `log/ops/` and never another theme's folder.
- Two accounts, not one (`decisions/0019`). A measuring pass that can also change the host makes measuring often a habit of exposing a powerful credential often.
- Nothing in step 3 to 7 changes ssh, the firewall, or sudo in a way that removes an existing path. Removing the old way in is the first action of the loop, under gate 2, not part of setup.
- `scaffold.py --flags` prints the arguments the measuring scripts take, built from these files. A step that retypes those numbers gets them wrong.
