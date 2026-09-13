#!/usr/bin/env python3
"""The rung of every check id is the same in the fixes table and in the theme's ladder.

Usage:
  check_rungs.py              one line per id whose two rungs disagree; exit 1 when any do

A report ranks its findings by the `Rung` column of its theme's fixes table (`decisions/0031`).
The `and-now` script of the same theme ranks the open work by a ladder it holds as data. Both
orders describe one thing, so an id that sits on two rungs makes the first line of a report and
the first item of `and-now` two different pieces of work.

Read only. Stdlib only. Exit 0 when every id agrees, 1 when one does not.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The row shape differs per theme: dx carries a Fix column between the meaning and the class.
ROW = re.compile(r"\|\s*`([a-z]+\.[a-z-]+)`\s*\|(?:[^|]*\|)+?\s*(\d+)\s*\|[^|]*\|\s*$")


def ladder_of(theme):
    """The ladder that theme's and-now script holds, whichever name it gives the table."""
    path = ROOT / "skills" / theme / "and-now" / "scripts" / "status.py"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    for name in ("LADDER = {", "RUNG = {"):
        if name in text:
            block = text[text.index(name) + len(name) - 1:]
            return ast.literal_eval(block[:block.index("}") + 1])
    return {}


def rungs_of(theme):
    """The rung column of that theme's fixes table, by check id."""
    path = ROOT / "skills" / theme / theme / "references" / "fixes.md"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--help" in argv or "-h" in argv:
        print(__doc__.strip())
        return 0
    hits = []
    for theme in sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()):
        ladder, table = ladder_of(theme), rungs_of(theme)
        if not table:
            continue
        if not ladder:
            hits.append(f"rung: {theme} names rungs in its fixes table and holds no ladder to check them against")
            continue
        for cid, rung in sorted(table.items()):
            if cid not in ladder:
                hits.append(f"rung: {cid} carries rung {rung} in the fixes table of {theme} and sits on no ladder")
            elif ladder[cid] != rung:
                hits.append(f"rung: {cid} is rung {rung} in the fixes table of {theme} and rung {ladder[cid]} on its ladder")
        # A namespace the table does not carry at all belongs to a tool that has not shipped. The
        # router names it under `## Planned`, and the ladder holds it so a log row can be parked.
        shipped = {cid.split(".", 1)[0] for cid in table}
        for cid in sorted(set(ladder) - set(table)):
            if cid.split(".", 1)[0] in shipped:
                hits.append(f"rung: {cid} sits on the ladder of {theme} and carries no rung in its fixes table")
    for line in hits:
        print(line)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
