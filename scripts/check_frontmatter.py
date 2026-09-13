#!/usr/bin/env python3
"""Check the header at the start of each SKILL.md.

Usage: check_frontmatter.py [--root DIR] [--json]
Names match their folders. Descriptions and argument hints use double quotes.
Inside strings, escape quotes and backslashes as in JSON.
Write disable-model-invocation as true or false, without quotes.
Use one field per line. See STYLE.md for a complete example and the allowed fields.
Exit 1 on invalid metadata, 0 when every skill passes.
"""
import argparse
import json
import re
import sys
from pathlib import Path

FIELD = re.compile(r"^([a-z][a-z-]*): (.+)$")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STRINGS = {"description", "argument-hint"}
BOOLEANS = {"disable-model-invocation"}


def check(text, name):
    """Return line numbers and reasons for invalid fields or an incomplete header."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return [(1, "start the skill header with ---")]
    end = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
    if end is None:
        return [(1, "end the skill header with a second --- line")]
    errors, seen = [], set()
    for n, line in enumerate(lines[1:end], 2):
        if not line.strip():
            continue
        match = FIELD.fullmatch(line)
        if not match:
            errors.append((n, "put one field and its value on this line"))
            continue
        key, value = match.groups()
        if key in seen:
            errors.append((n, f"duplicate field: {key}"))
        seen.add(key)
        if key == "name":
            if not NAME.fullmatch(value) or value != name:
                errors.append((n, "name must match the skill folder, using lowercase letters, digits, and hyphens"))
        elif key in STRINGS:
            try:
                decoded = json.loads(value)
            except ValueError:
                decoded = None
            if not isinstance(decoded, str) or not decoded.strip():
                errors.append((n, f'{key} needs text in double quotes, for example {key}: "Text"'))
        elif key in BOOLEANS:
            if value not in ("true", "false"):
                errors.append((n, f"{key} must be true or false"))
        else:
            errors.append((n, f"unsupported frontmatter field: {key}"))
    for key in sorted({"name", "description"} - seen):
        errors.append((1, f"missing field: {key}"))
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    paths = sorted(args.root.glob("skills/*/*/SKILL.md"))
    errors = []
    for path in paths:
        try:
            found = check(path.read_text(encoding="utf-8"), path.parent.name)
        except (OSError, UnicodeError):
            found = [(1, "cannot read frontmatter as UTF-8")]
        errors.extend({"file": str(path.relative_to(args.root)), "line": n, "reason": reason}
                      for n, reason in found)
    if not paths:
        errors.append({"file": "skills", "line": 1, "reason": "no skill files found"})
    result = {"checked": len(paths), "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for error in errors:
            print("{file}:{line}: {reason}".format(**error))
        # The gate reads stdout for hits alone, and prints `ok` when there are none. The count is
        # status a person running this script wants, so it goes where check.sh puts its warning.
        print(f"frontmatter: {len(paths)} checked, {len(errors)} errors", file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
