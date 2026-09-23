#!/usr/bin/env python3
"""A step carries no year (STYLE.md, "Structure"): find a four-digit year inside `## Steps`.

Usage:
  check_steps_years.py [--root DIR]   one line per hit; exit 1 when any exist

A sourced fact, dated or not, stands outside `## Steps`: in `## Rules`, in `## Interpretation`,
or in the opening paragraph. This reads every `SKILL.md`, isolates the text between a `## Steps`
heading and the next `## ` heading (or the end of the file), strips fenced and inline code spans
so a literal year inside an example command or a file name is not a hit, and looks for `19xx` or
`20xx`.

Read only, stdlib only. Exit 0 when no step names a year, 1 when one does.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS_HEADING = re.compile(r"^## Steps\s*$", re.MULTILINE)
NEXT_HEADING = re.compile(r"^## ", re.MULTILINE)
FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def steps_section(text):
    """The text of the first `## Steps` section, or None when the file has none."""
    start = STEPS_HEADING.search(text)
    if not start:
        return None
    rest = text[start.end():]
    end = NEXT_HEADING.search(rest)
    return rest[:end.start()] if end else rest


def years_in_steps(text):
    """(offset, year) pairs for every four-digit year found outside code spans in ## Steps."""
    section = steps_section(text)
    if section is None:
        return []
    stripped = INLINE_CODE.sub(lambda m: " " * len(m.group()),
                                FENCED_CODE.sub(lambda m: " " * len(m.group()), section))
    offset = text.index(section)
    return [(offset + m.start(), m.group()) for m in YEAR.finditer(stripped)]


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    hits = []
    for path in sorted(args.root.glob("skills/*/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        for pos, year in years_in_steps(text):
            rel = path.relative_to(args.root)
            hits.append(f"{rel}:{line_of(text, pos)}: {year} inside ## Steps")
    for line in hits:
        print(line)
    print(f"steps-years: {len(hits)} years found in ## Steps sections", file=sys.stderr)
    return int(bool(hits))


if __name__ == "__main__":
    sys.exit(main())
