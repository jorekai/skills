---
name: agent-config
description: The agent surface of every project, compared against standards.md: the pointer file a session reads first, permission settings, hooks that run on a tool call, and the servers a session depends on. Use when an agent does not find its way in a project, when settings drifted between projects, when a hook fails, or after adding a project.
---

# Agent configuration

What a session finds when it opens a project, and whether that matches what the standards say it should find. Reads the project list from the newest `audits/*-repos.json` or from `machines/<hostname>/config.md`, and the target state from `standards.md`. No workspace: ask which projects to look at and what the pointer file should be, then skip the log steps.

A project's agent files are read, never sent anywhere. Their contents can name customers.

## Steps

1. **Take the project list and the target state.** `pointer_file` in `standards.md` names the file a project must carry for agents, and the rest of that file says what else a project must have. A blank value there means this check does not run on this machine, which is an answer.
   Done when the list has a length and the target state has a value for every key this pass reads.

2. **Read each project's agent surface in parallel.** Send the reading to subagents, at most ten projects each. Each returns one table with the columns `project | pointer file | hooks | permissions | servers | gap` and nothing else, under 200 words. A gap is one short phrase, not a diff.
   Done when every project appears in exactly one table row and no file contents reached this context.

3. **Turn gaps into findings, one per check id.** A missing pointer file, a pointer that names a path the project no longer has, a permission entry that grants more than the standard, a hook whose command is not on the machine, a configured server that does not answer. Look each id up in [../dx/references/fixes.md](../dx/references/fixes.md).
   Done when every gap has a check id and every check id has one finding listing its projects.

4. **Fix by class and log.** Adding a missing pointer file is `safe`. Narrowing a permission or removing a hook changes how sessions behave and is `confirm`. Anything inside a repository with uncommitted or unpushed work is `ask`. Save the tables as `audits/YYYY-MM-DD-agent-config.json` in the shape the other passes use, then one log row per check id acted on, with the number of projects as the measure.
   Done when each row names the check id, the class, and the count the next pass recomputes.

The check ids this skill produces are `agent.no-pointer`, `agent.pointer-drift`, `agent.permission-drift`, `agent.hook-broken`, and `agent.server-unreachable`. Each has a row in [../dx/references/fixes.md](../dx/references/fixes.md).

## Rules

- The standard comes from `standards.md`, never from the project that happens to look tidiest. Copying one project onto the others is how a wrong setting spreads.
- A pointer file that exists is not a pointer file that is right. The check is whether it names paths and commands that still exist.
- Making every project identical is not the goal. A project that deliberately differs gets a line in `standards.md` saying so, and then it is no longer a finding.

## Interpretation

- Checking whether a configured server answers needs the network. Every other check here is offline, so a session with no network still gets four of the five.
- A permission that grants more than the standard is worth narrowing; one that grants less is usually a project that needs less. Only the first is a finding.
- A broken hook is the most expensive item on this list. It fails on every tool call in that project, so it costs time in every session until someone looks.
