# 0012: A destructive action carries one of three risk classes

Date: 2026-09-05

## Context

Maintenance work removes things: images, caches, build output, merged branches, stopped containers, dependency trees. The value is in doing it without being asked every time, and the danger is one wrong removal costing a day. "Ask before anything destructive" makes the skills useless, because the whole point is that nobody wants to confirm forty prunes. "Just clean up" is how work gets lost.

The distinction that matters is not how much a command deletes. It is whether the deleted thing can be rebuilt without a person.

## Decision

Every check id in `references/fixes.md` carries one class, and the class decides the flow.

`safe` runs immediately and reports what it did. The removed thing is rebuilt by a command, not by a person: dangling images, build cache, compiled bytecode, a local branch fully contained in its pushed upstream default.

`confirm` prints a dry run with exact paths and totals, asks once, then runs. The removed thing is rebuildable but costs time or network: dependency directories of inactive projects, unused volumes, images past the retention in `standards.md`.

`ask` never runs. It prints the command and the reason. The removal is irreversible, or the script cannot prove which class applies: named volumes holding data, stashes, repositories with no remote.

Above all three, one gate: nothing runs against a repository with uncommitted or unpushed work. That is `ask` regardless of the check's own class.

A script may move a finding to a stricter class when it cannot prove the safer one. It may never move a finding to a looser class.

## Consequences

A step never asks the model to judge whether a removal is safe. It looks the class up. The judgment happened once, in `fixes.md`, where it is reviewable and has a source or a stated heuristic.

The gate means a machine full of dirty repositories reports a lot and removes almost nothing, which is correct: unsaved work outranks disk space. `jorekai-dx:repos` therefore runs before any cleanup in the router's flow, so the gate has data to work from.
