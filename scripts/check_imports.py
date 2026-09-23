#!/usr/bin/env python3
"""Every tracked script imports only the standard library or a sibling in its own directory.

Usage:
  check_imports.py [--root DIR]   one line per import that fails the rule; exit 1 when any do

CONTRIBUTING.md and AGENTS.md say a script stays Python stdlib or bash: nothing installed from
PyPI. `import pip` used to pass this gate because nothing read an import statement. This walks
each tracked `*.py` under `skills/` and `scripts/` with the `ast` module and checks every import
against `sys.stdlib_module_names` (Python 3.10+). A name that is not stdlib but matches a `.py`
file beside the one being checked is a local import, such as a test importing the script next to
it (`import scaffold`), and passes even when the same name also exists in the standard library
(`skills/security/secrets/scripts/secrets.py`, imported as `import secrets`).

Read only, stdlib only. Exit 0 when every import passes, 1 when one does not.
"""
import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def local_names(path):
    """The sibling modules a file at this path may import: every other *.py beside it."""
    return {p.stem for p in path.parent.glob("*.py") if p != path}


def bad_imports(path):
    """Top-level import names in this file that are neither stdlib nor a sibling module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeError) as e:
        return [(1, f"cannot parse: {e}")]
    allowed = set(sys.stdlib_module_names) | set(sys.builtin_module_names) | local_names(path)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".", 1)[0]
                if top not in allowed:
                    hits.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue  # a relative import is local by construction
            top = (node.module or "").split(".", 1)[0]
            if top and top not in allowed:
                hits.append((node.lineno, f"from {node.module} import ..."))
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    paths = sorted(set(args.root.glob("skills/**/*.py")) | set(args.root.glob("scripts/*.py")))
    hits = []
    for path in paths:
        rel = path.relative_to(args.root)
        for lineno, what in bad_imports(path):
            hits.append(f"{rel}:{lineno}: {what} is not stdlib and not a sibling module")
    for line in hits:
        print(line)
    print(f"imports: {len(paths)} files checked, {len(hits)} not stdlib", file=sys.stderr)
    return int(bool(hits))


if __name__ == "__main__":
    sys.exit(main())
