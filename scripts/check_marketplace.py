#!/usr/bin/env python3
"""Every marketplace entry matches the plugin it points at.

Usage:
  check_marketplace.py [--root DIR]   one line per mismatch; exit 1 when any exist

`decisions/0013` makes each plugin's own manifest the owner of its name, version, and
description; `.claude-plugin/marketplace.json` at the repository root only lists them. This
checks, for every entry in `plugins`:

  1. `source` resolves to a directory that exists and holds a `.claude-plugin/plugin.json`
     (the repository root itself, for a source of `./`).
  2. The entry's `name` is that manifest's `name`.
  3. The entry's `description` is that manifest's `description`, character for character.
  4. When a manifest's description has the form "... loop ...: a, b, c, ..., and-now.", every
     skill directory of that theme (a folder holding a `SKILL.md`, other than the router
     directory named after the theme itself) is named somewhere in that list. A description
     that does not end the list on "and-now" is not this form and is skipped (`jorekai-intro`
     today), because forcing every description into one shape would be the wrong fix for a
     collection where one theme only maps the others.

Read only, stdlib only. Exit 0 when every entry passes, 1 when one does not.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def skill_dirs(root, theme):
    """Every skill directory of a theme: one per SKILL.md, minus the theme's own router."""
    return sorted(p.parent.name for p in (root / "skills" / theme).glob("*/SKILL.md")
                  if p.parent.name != theme)


def loop_items(description):
    """The comma-separated list after the first colon, when it ends the loop on 'and-now'."""
    if ": " not in description:
        return None
    tail = description.split(": ", 1)[1].rstrip()
    if not tail.endswith("."):
        return None
    items = [item.strip() for item in tail[:-1].split(", ")]
    return items if items and items[-1] == "and-now" else None


def check(root):
    root = root.resolve()
    marketplace_path = root / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    hits = []
    for entry in marketplace.get("plugins", []):
        name = entry.get("name", "<unnamed>")
        source = entry.get("source", "")
        plugin_dir = (root / source).resolve() if source != "./" else root
        if not plugin_dir.is_dir():
            hits.append(f"marketplace: {name} source '{source}' resolves to no directory")
            continue
        manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
        if not manifest_path.is_file():
            hits.append(f"marketplace: {name} source '{source}' holds no .claude-plugin/plugin.json")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rel_manifest = manifest_path.relative_to(root)
        if manifest.get("name") != name:
            hits.append(f"marketplace: {name} names {rel_manifest} whose plugin.json name is "
                        f"{manifest.get('name')!r}")
        m_desc, p_desc = entry.get("description", ""), manifest.get("description", "")
        if m_desc != p_desc:
            hits.append(f"marketplace: {name} description differs from {rel_manifest}: "
                        f"{m_desc!r} != {p_desc!r}")
        theme = name.removeprefix("jorekai-")
        items = loop_items(p_desc)
        if items is not None:
            missing = [d for d in skill_dirs(root, theme) if d not in items]
            if missing:
                hits.append(f"marketplace: {rel_manifest} description names no {', '.join(missing)} "
                            f"in its loop, though {theme} has that skill")
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT)
    args = ap.parse_args(argv)
    hits = check(args.root)
    for line in hits:
        print(line)
    print(f"marketplace: {len(hits)} mismatches", file=sys.stderr)
    return int(bool(hits))


if __name__ == "__main__":
    sys.exit(main())
