# 0033: An adapter name is a file name, not a product line

Date: 2026-09-14

## Context

`jorekai-stack` wires eight ports, and every axis value chooses one adapter per port. Something has to name them. Two ways were on the table: the vendor's product name as marketed, with a row per product carrying its plan, its free tier and its limits, or the name of the file that talks to it.

The first way produces a reference file of prices, and a price is a platform fact. `decisions/0004` requires a source and a check date for every platform fact, and `sources_age.py` warns when the date is older than half a year. A table of prices for twenty-three adapters would make `sources.md` three digits long and stale every month, and none of it decides which adapter a repository gets: the axes decide that.

## Decision

An adapter is named by its file, `packages/ports/src/<port>/<adapter>.adapter.ts`, and the name is the protocol or the vendor the file talks to: `pool`, `neon-http`, `r2`, `s3`, `smtp`, `resend`. The table in `references/ports.md` maps each axis value to an adapter name and carries no price, no free tier and no limit. The rows of `sources.md` are about protocols and generator surfaces, which change rarely, and about nothing that changes monthly.

An adapter name is an opinion about what fits an axis value today. A repository that disagrees records a port exception in `stack.yaml` with a reason, and `adapter.untargeted` reads the reason as data.

## Consequences

Renaming a product costs nothing here. Changing a price costs nothing here. Moving an adapter from one axis value to another is a change to one row and to the tables that duplicate it in `declare.py`, `lay.py` and `drift.py`, and the tests of `jorekai-stack:new` compare the three to the file both ways.

What a person wants to know before choosing a target, which is what it costs, is a question this collection does not answer, on purpose. `jorekai-stack:choose` asks it and the person answers it from the vendor's page of the day.
