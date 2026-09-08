#!/usr/bin/env python3
"""The map of this collection: every theme, its plugin, its skills, and the command that starts it.

Usage:
  catalog.py [--theme NAME] [--json]      the map as a report, or as the object behind it
  catalog.py --scan ROOT [--json]         build the map from a checkout instead of the snapshot
  catalog.py --check [--scan ROOT]        fail when the snapshot no longer matches the checkout

The snapshot in references/catalog.json ships inside the plugin, so the map answers with no
checkout on disk and with no other plugin installed. It is generated, never typed:

  catalog.py --scan . --json > references/catalog.json

Everything in it comes from files this repository already keeps: the frontmatter of every
SKILL.md, each theme's router tables, the plugin manifests, and the marketplace file. A skill
added, renamed, or removed anywhere makes --check fail until the snapshot is regenerated.
Stdlib only, no network. Exit 1 when --check finds a difference, 2 when a path is missing.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL_DIR = HERE.parents[1]
SNAPSHOT = SKILL_DIR / "references" / "catalog.json"
CHECKOUT = HERE.parents[4]

# Colour is a hint on a report that reads the same without it (decisions/0022). It is off unless
# the output is a terminal, so a pipe, a redirect and a captured test all read plain text.
PAINT = {"head": "1", "name": "1", "dim": "2", "you": "36", "agent": "33", "planned": "2"}


def colour_on(stream=sys.stdout):
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return stream.isatty() and os.environ.get("TERM", "") != "dumb"


COLOUR = colour_on()


def paint(text, key):
    """`text` in the colour its role carries. Every escape removed leaves the same report."""
    return f"\033[{PAINT[key]}m{text}\033[0m" if COLOUR and key in PAINT else text


REF = re.compile(r"jorekai-([a-z]+):([a-z-]+)")
FIELD = re.compile(r"^([a-z][a-z-]*):\s*(.*)$")


def frontmatter(text):
    """The `key: value` lines between the first two `---` fences, quotes stripped."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = FIELD.match(line)
        if m:
            key = m.group(1)
            out[key] = m.group(2).strip()
        elif key and line.strip():
            out[key] = f"{out[key]} {line.strip()}".strip()
    for key, value in out.items():
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
            out[key] = value[1:-1]
    return out


def section(text, title):
    """The lines under `## <title>`, up to the next second-level heading."""
    out, on = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            on = line[3:].strip() == title
            continue
        if on:
            out.append(line)
    return out


def rows(lines):
    """The data rows of a markdown table: the header rule and any row with no skill in it go."""
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if REF.search(" ".join(cells)):
            yield cells


def unticked(text):
    return text.replace("`", "")


def needs(text, theme):
    """Skill name to the `Need` cell of the router's sub-skill table: when to reach for it."""
    out = {}
    for cells in rows(section(text, "Sub-skills")):
        for i, cell in enumerate(cells):
            m = REF.search(cell)
            if m and m.group(1) == theme:
                out[m.group(2)] = unticked(cells[0]) if i else ""
                break
    return out


def answers(text, theme):
    """Skill name to what the router says it hands back, from `## Writing the answer`."""
    out = {}
    for line in section(text, "Writing the answer"):
        if not line.startswith("- "):
            continue
        named, sep, answer = line[2:].partition(": ")
        if not sep:
            continue
        for m in REF.finditer(named):
            if m.group(1) == theme:
                out[m.group(2)] = answer.strip()
    return out


def planned(text, theme):
    """The skills a router names as designed and not built (decisions/0021)."""
    out = []
    for cells in rows(section(text, "Planned")):
        m = REF.search(cells[0])
        if m and m.group(1) == theme:
            note = unticked(cells[1]) if len(cells) > 1 else ""
            out.append({"skill": f"jorekai-{theme}:{m.group(2)}", "note": note})
    return out


def manifest(root, theme):
    """The plugin manifest of a theme: beside its skills, or at the root for the first one."""
    for path in (root / "skills" / theme / ".claude-plugin" / "plugin.json",
                 root / ".claude-plugin" / "plugin.json"):
        if not path.is_file():
            continue
        data = json.loads(path.read_text())
        if data.get("name") == f"jorekai-{theme}":
            return data
    return {}


def marketplace(root):
    """The marketplace name, the line that adds it, and every plugin it lists."""
    path = root / ".claude-plugin" / "marketplace.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    repo = ""
    root_manifest = root / ".claude-plugin" / "plugin.json"
    if root_manifest.is_file():
        url = json.loads(root_manifest.read_text()).get("repository", "")
        repo = "/".join(url.rstrip("/").split("/")[-2:])
    return {"name": data.get("name", ""), "add": f"claude plugin marketplace add {repo}",
            "plugins": [p.get("name", "") for p in data.get("plugins", [])]}


def thesis(text):
    """The sentence a router opens with, under its heading: what the theme does in one line."""
    body = text.split("\n---\n", 1)[-1].splitlines()
    for i, line in enumerate(body):
        if line.startswith("# "):
            for para in body[i + 1:]:
                if para.strip() and not para.startswith("#"):
                    return unticked(para.strip()).replace("**", "")
            break
    return ""


def first_clause(text, width=72):
    """The head of a description: up to its first colon or full stop, never a cut word."""
    for stop in (": ", ". "):
        if stop in text[:width + 20]:
            text = text.split(stop, 1)[0]
    if len(text) > width:
        text = text[:width].rsplit(" ", 1)[0]
    return text.strip()


def scan(root):
    """The map, built from the checkout at `root`."""
    root = Path(root)
    if not (root / "skills").is_dir():
        raise FileNotFoundError(f"no skills/ directory under {root}")
    market = marketplace(root)
    themes = []
    for theme_dir in sorted((root / "skills").iterdir()):
        theme = theme_dir.name
        router_md = theme_dir / theme / "SKILL.md"
        if not router_md.is_file():
            continue
        router = router_md.read_text()
        need, answer = needs(router, theme), answers(router, theme)
        found = {}
        for d in sorted(theme_dir.iterdir()):
            md = d / "SKILL.md"
            if not md.is_file():
                continue
            front = frontmatter(md.read_text())
            name = front.get("name", d.name)
            scripts = sorted(p.name for p in (d / "scripts").glob("*")
                             if p.suffix in {".py", ".sh"} and not p.name.startswith("test_"))
            found[name] = {
                "skill": f"jorekai-{theme}:{name}",
                "invoked_by": "you" if front.get("disable-model-invocation") == "true" else "agent or you",
                "description": front.get("description", ""),
                "reach_for_it_when": need.get(name, ""),
                "hands_back": answer.get(name, ""),
                "scripts": scripts,
            }
        # The router first, then the order the router itself chose, then anything it forgot.
        order = [theme] + [n for n in need if n in found] + sorted(found)
        skills, seen = [], set()
        for name in order:
            if name in found and name not in seen:
                seen.add(name)
                skills.append(found[name])
        plugin = manifest(root, theme)
        entry = "setup" if "setup" in found else theme
        themes.append({
            "theme": theme,
            "plugin": plugin.get("name", ""),
            "version": plugin.get("version", ""),
            "covers": plugin.get("description", ""),
            "install": f"claude plugin install {plugin.get('name', '')}@{market.get('name', '')}",
            "listed": plugin.get("name", "") in market.get("plugins", []),
            "thesis": thesis(router),
            "router": f"jorekai-{theme}:{theme}",
            "entry": f"/jorekai-{theme}:{entry}",
            "skills": skills,
            "planned": planned(router, theme),
        })
    return {"generated": dt.date.today().isoformat(),
            "marketplace": {k: market[k] for k in ("name", "add") if k in market},
            "themes": themes}


def load(path):
    return json.loads(Path(path).read_text())


def differences(new, old, path="map"):
    """One line per difference between two maps. `generated` is a date, not content."""
    if isinstance(new, dict) and isinstance(old, dict):
        for key in sorted(set(new) | set(old)):
            if path == "map" and key == "generated":
                continue
            if key not in old:
                yield f"{path}.{key}: only in the checkout"
            elif key not in new:
                yield f"{path}.{key}: only in the snapshot"
            else:
                yield from differences(new[key], old[key], f"{path}.{key}")
    elif isinstance(new, list) and isinstance(old, list):
        for i in range(max(len(new), len(old))):
            if i >= len(old):
                yield f"{path}[{i}]: only in the checkout: {summary(new[i])}"
            elif i >= len(new):
                yield f"{path}[{i}]: only in the snapshot: {summary(old[i])}"
            else:
                yield from differences(new[i], old[i], f"{path}[{i}]")
    elif new != old:
        yield f"{path}: the checkout says {new!r}, the snapshot says {old!r}"


def summary(item):
    if isinstance(item, dict):
        return item.get("skill") or item.get("theme") or ", ".join(sorted(item))
    return str(item)


def report(catalog, theme=None, out=sys.stdout):
    themes = [t for t in catalog["themes"] if theme in (None, t["theme"])]
    total = sum(len(t["skills"]) for t in themes)
    market = catalog.get("marketplace", {})
    print(paint(f"{len(themes)} theme(s), {total} skill(s), marketplace {market.get('name', '')}", "head"), file=out)
    print(paint(f"snapshot of {catalog.get('generated', '')}, install once: {market.get('add', '')}", "dim"), file=out)
    for t in themes:
        print(file=out)
        head = f"{t['theme']}  {t['plugin']} {t['version']}  {len(t['skills'])} skill(s)"
        print(paint(head, "head"), file=out)
        if t["thesis"]:
            print(f"  loop     {t['thesis']}", file=out)
        if t["covers"]:
            print(f"  covers   {t['covers']}", file=out)
        print(f"  install  {t['install']}", file=out)
        print(f"  start    {t['entry']}", file=out)
        width = max((len(s["skill"]) for s in t["skills"]), default=0)
        for s in t["skills"]:
            key = "you" if s["invoked_by"] == "you" else "agent"
            when = s["reach_for_it_when"] or first_clause(s["description"])
            print(f"  {paint(s['skill'].ljust(width), 'name')}  {paint(s['invoked_by'].ljust(12), key)}"
                  f"  {when}", file=out)
        for p in t["planned"]:
            print(paint(f"  {p['skill'].ljust(width)}  planned       {p['note']}", "planned"), file=out)
    print(file=out)
    print(f"Start with the theme whose subject you have in front of you. {len(themes)} shown.", file=out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--theme", help="one theme instead of all of them")
    ap.add_argument("--json", action="store_true", help="the map itself, not the report")
    ap.add_argument("--scan", metavar="ROOT", help="build the map from a checkout")
    ap.add_argument("--snapshot", default=SNAPSHOT, help="the shipped map (default: references/catalog.json)")
    ap.add_argument("--check", action="store_true", help="fail when the snapshot is not the checkout")
    a = ap.parse_args(argv)

    if a.check:
        root = a.scan or (CHECKOUT if (CHECKOUT / "skills").is_dir() else None)
        if not root:
            print("check needs a checkout: pass --scan ROOT", file=sys.stderr)
            return 2
        try:
            fresh = scan(root)
        except FileNotFoundError as e:
            print(e, file=sys.stderr)
            return 2
        if not Path(a.snapshot).is_file():
            print(f"no snapshot at {a.snapshot}", file=sys.stderr)
            return 2
        drift = list(differences(fresh, load(a.snapshot)))
        for line in drift:
            print(line)
        if drift:
            print(f"{len(drift)} difference(s): regenerate with "
                  f"catalog.py --scan {root} --json > {a.snapshot}", file=sys.stderr)
            return 1
        print("ok")
        return 0

    if a.scan:
        try:
            catalog = scan(a.scan)
        except FileNotFoundError as e:
            print(e, file=sys.stderr)
            return 2
    else:
        if not Path(a.snapshot).is_file():
            print(f"no snapshot at {a.snapshot}", file=sys.stderr)
            return 2
        catalog = load(a.snapshot)

    if a.theme and not any(t["theme"] == a.theme for t in catalog["themes"]):
        print(f"no such theme: {a.theme}", file=sys.stderr)
        return 2
    if a.json:
        if a.theme:
            catalog = dict(catalog, themes=[t for t in catalog["themes"] if t["theme"] == a.theme])
        json.dump(catalog, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0
    return report(catalog, a.theme)


if __name__ == "__main__":
    sys.exit(main())
