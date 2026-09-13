# 0031: A report answers seven questions, two in the list and five on request

Date: 2026-09-13

## Context

`decisions/0028` made every finding three lines: the level word, the id, the cost, then the message and up to five targets. Eleven findings filled eighty lines. A person reading that asks the same seven questions of every line: what is it, how heavy is it, why does it matter, where does it come from, what do I do, what does it cost to do it, and how will I know it worked. The old shape answered the first three and left the rest in a reference file the reader had to open by hand.

Two other things were missing everywhere. No report said whether a number had moved since the last pass, although every audit JSON on disk holds the earlier one. And the order of the findings was the sort order of the script, while the ladder that decides the order of work lived in the `and-now` script of the theme and in prose in the router.

## Decision

In every theme whose findings carry a measure, a risk class and a rung, the console report prints one line per finding:

```
  #  level  check               measure           change  where        class
  1  FAIL   access.single-path  1 missing way in  =       ops-admin    ask
```

`#` is the rank and the address: `--explain 1` prints the chain for that line, and `--explain access.single-path` reaches the same one. `change` appears only with `--previous FILE`, an earlier findings JSON, and reads `=`, a signed number, or `new`. A finding with no cost keeps the columns and carries its sentence dimmed under its row, because a note's content is its sentence.

`--explain` answers the rest, one finding at a time, with the fields in the order the questions come:

| Field | Answers | Source |
|---|---|---|
| `what` | what is it | the finding's message and its targets |
| `weight` | how heavy | rank, level, change, and the gate the id stands under |
| `means` | why it matters | the `What it means` column of the theme's fixes table |
| `cause` | where it comes from | printed only when the pass proved one |
| `fix` | what to do | the class, the gate, and what the fixes table holds for the id |
| `undo` | the way back | the class and the gate it runs under |
| `verify` | how I know it worked | the check id, zero in its unit, and where the date goes |

A cause nobody measured is never printed. A guessed cause costs more trust than the line saves time, so the field stays out until a pass carries a signal for it.

The fixes table of each of those themes gains a `Rung` column, copied from the ladder that theme's `and-now` script already holds. The scripts rank by that column, so the first line of a report and the first item of `and-now` are the same piece of work. `scripts/check.sh` compares the two tables both ways.

This replaces rule 3 of `decisions/0028`. The other six rules of that decision stand unchanged: the head, the counting bar, the folded notes, the wrapped passed list, the `next` zone, and the shape of `and-now`. A theme whose findings carry no measure, no class and no rung keeps rule 3 until they do; today that is `jorekai-seo:tech-audit` alone, and its fixes file holds prose per id rather than a table with those columns.

## Consequences

A report of eleven findings is sixteen lines instead of eighty, and it fits a terminal without scrolling. What the old shape printed for every finding is one keystroke away for the one finding a person picked.

The cost is a second command for detail and a table that must stay in step with the ladder. The gate in `check.sh` pays the second cost. The first is the trade the format is for.

Labels are one word each, at most six characters, and none of them means something else in this collection: `verdict` belongs to a log row, `risk` to the risk class, `target` to the host or repository in a findings JSON, and `check` to the id. So the fields read `what`, `weight`, `means`, `cause`, `fix`, `undo`, `verify`.
