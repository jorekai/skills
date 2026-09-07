#!/usr/bin/env python3
"""State of every local repository under one or more paths: unsaved work first, then hygiene.

Usage:
  repos.py PATH [PATH ...] [--depth N] [--stale-days N] [--stash-days N]
           [--expect-email ADDRESS] [--timeout S] [--json]
  repos.py --measures                     the unit every check id is measured in

`scaffold.py --flags` in the setup skill prints these arguments from the workspace standards.

A PATH is either a repository or a directory to scan for repositories. Every check runs
locally: no fetch, no push, no network. Nothing is written and nothing is removed.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import os
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# Colour is a hint on a report that reads the same without it (decisions/0022). It is off unless
# the output is a terminal, so a pipe, a redirect and a captured test all read plain text.
# NO_COLOR turns it off everywhere, FORCE_COLOR turns it on, which is how a test proves both.
PAINT = {"FAIL": "1;31", "WARN": "33", "PASS": "32", "INFO": "36", "head": "1", "id": "1",
         "dim": "2"}


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


LEVEL_ORDER = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
# The unit of every check id this script measures. A measure counts what the finding costs, so
# lower is better and zero means the check no longer fires (decisions/0014). `--measures` prints
# this table and scripts/check.sh compares it to the unit named in the theme's fixes.md.
MEASURES = {"repo.secret-exposed": "count", "git.dirty": "count", "git.unpushed": "count",
            "repo.no-remote": "count", "git.no-upstream": "count", "git.detached": "count",
            "git.stash-old": "count",
            "git.identity": "count", "git.stale-branch": "count", "repo.lock-drift": "count",
            "repo.no-readme": "count", "repo.no-ignore": "count", "repo.no-ci": "count"}
# What the number in a row counts, per check id. Without it a row prints a bare number and the
# reader has to guess whether it means files, commits, or branches.
ROW_WORD = {"git.dirty": ("changed path", "changed paths"), "git.unpushed": ("commit", "commits"),
            "git.stash-old": ("stash entry", "stash entries"),
            "git.stale-branch": ("merged branch", "merged branches"),
            "repo.secret-exposed": ("credential file", "credential files")}
SKIP = {".git", "node_modules", ".venv", "venv", "vendor", "target", "dist", "build",
        ".next", ".cache", "Library", ".Trash"}
CI_PATHS = (".github/workflows", ".gitlab-ci.yml", ".circleci", "Jenkinsfile", ".woodpecker.yml")
READMES = ("README.md", "README.rst", "README.txt", "README")
# Manifest and the lock file that must not be older than it. A lock older than its manifest
# means the installed tree and the declared one disagree.
LOCKS = [("package.json", "package-lock.json"), ("package.json", "pnpm-lock.yaml"),
         ("package.json", "yarn.lock"), ("package.json", "bun.lockb"),
         ("pyproject.toml", "poetry.lock"), ("pyproject.toml", "uv.lock"),
         ("Cargo.toml", "Cargo.lock"), ("go.mod", "go.sum"),
         ("Gemfile", "Gemfile.lock"), ("composer.json", "composer.lock")]
# A file name that says the file holds a credential. Matched against the file name alone: a path
# means nothing, the name is what tools and people agree on.
SECRET_NAME = re.compile(r"""(?x)
    ^\.env($|\.) | ^\.(envrc|netrc|npmrc|pypirc|pgpass)$ |
    ^id_(rsa|dsa|ecdsa|ed25519)$ |
    ^(secret|secrets|credential|credentials)(\.[a-z0-9]+)?$ |
    ^service[-_]account.*\.json$ |
    \.(pem|key|p12|pfx|jks|keystore|ppk|tfvars)$
""", re.I)
# The same names carrying a placeholder marker. A repository is supposed to hold `.env.example`,
# and a check that flags it teaches the reader to skip the check.
SECRET_PLACEHOLDER = re.compile(r"(example|sample|template|dist|default|\.pub$)", re.I)


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one repository grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def git(repo, *args, timeout=10):
    """Run one git command in repo. Returns stdout, or None when git fails or takes too long."""
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def untracked_secrets(repo, timeout):
    """Untracked files whose name says credential and that no ignore rule covers, newest ignore
    rules included: `--exclude-standard` applies the same rules `git add` would. The finding is
    the pair, not the name alone, because an ignored credential file is what an ignore file is
    for and a tracked one is already in the history, which is a different problem."""
    out = git(repo, "ls-files", "--others", "--exclude-standard", timeout=timeout)
    names = []
    for line in (out or "").splitlines():
        path = line.strip()
        name = path.rsplit("/", 1)[-1]
        if path and SECRET_NAME.search(name) and not SECRET_PLACEHOLDER.search(name):
            names.append(path)
    return sorted(names)


def find_repos(paths, depth):
    """Every repository at or under the given paths, deduplicated, in path order."""
    found = {}
    for p in paths:
        base = Path(p).expanduser()
        if not base.is_dir():
            continue
        if (base / ".git").exists():
            found[base.resolve()] = True
            continue
        stack = [(base, 0)]
        while stack:
            d, level = stack.pop()
            try:
                entries = sorted(d.iterdir())
            except OSError:
                continue
            if (d / ".git").exists():
                found[d.resolve()] = True
                continue          # a repository's own subdirectories are its business
            if level >= depth:
                continue
            for e in entries:
                if e.is_dir() and not e.is_symlink() and e.name not in SKIP and not e.name.startswith("."):
                    stack.append((e, level + 1))
    return sorted(found)


def default_branch(repo, timeout):
    head = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", timeout=timeout)
    if head:
        return head.rsplit("/", 1)[-1]
    for name in ("main", "master"):
        if git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}", timeout=timeout):
            return name
    return None


def read_repo(repo, now, stale_days, stash_days, timeout):
    """Everything one repository says about itself, without touching the network."""
    s = {"path": str(repo), "name": repo.name}
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD", timeout=timeout)
    s["branch"] = branch
    s["detached"] = branch == "HEAD"
    porcelain = git(repo, "status", "--porcelain", timeout=timeout)
    s["dirty"] = len([l for l in porcelain.splitlines() if l.strip()]) if porcelain is not None else 0
    s["remotes"] = [r for r in (git(repo, "remote", timeout=timeout) or "").splitlines() if r]
    s["upstream"] = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", timeout=timeout)

    # Commits that exist on no remote at all. A branch with no upstream still counts here,
    # which is the point: the question is whether the work survives losing this disk.
    # The source ref of each commit is counted too, because the work is rarely on the checked out
    # branch, and a count alone sends the reader looking for it by hand. A commit reachable from
    # several branches is attributed to one of them, so the branch counts sum to the total.
    s["unpushed"] = 0
    s["unpushed_branches"] = []
    if s["remotes"]:
        out = git(repo, "log", "--branches", "--not", "--remotes", "--source", "--format=%S", timeout=timeout)
        counted = {}
        for name in (out or "").splitlines():
            name = name.strip()
            if name:
                counted[name] = counted.get(name, 0) + 1
        s["unpushed"] = sum(counted.values())
        s["unpushed_branches"] = [{"branch": b, "commits": n}
                                  for b, n in sorted(counted.items(), key=lambda x: (-x[1], x[0]))]

    s["stashes"] = []
    for line in (git(repo, "stash", "list", "--format=%ct", timeout=timeout) or "").splitlines():
        if line.strip().isdigit():
            age = (now - int(line)) // 86400
            if age > stash_days:
                s["stashes"].append(age)

    s["stale_branches"] = []
    d = default_branch(repo, timeout)
    if d:
        out = git(repo, "for-each-ref", "--merged", d, "--format=%(refname:short)\t%(committerdate:unix)",
                  "refs/heads/", timeout=timeout)
        for line in (out or "").splitlines():
            name, _, ts = line.partition("\t")
            if name and name != d and ts.strip().isdigit():
                age = (now - int(ts)) // 86400
                if age > stale_days:
                    s["stale_branches"].append((name, age))
    s["default_branch"] = d

    # The effective address, so a repository that inherits the global one is judged by what a
    # commit would actually carry.
    s["email"] = git(repo, "config", "--get", "user.email", timeout=timeout) or ""
    s["secrets"] = untracked_secrets(repo, timeout)
    s["readme"] = any((repo / n).exists() for n in READMES)
    s["ignore"] = (repo / ".gitignore").exists()
    s["ci"] = any((repo / c).exists() for c in CI_PATHS)
    s["lock_drift"] = []
    for manifest, lock in LOCKS:
        m, l = repo / manifest, repo / lock
        if m.exists() and l.exists() and m.stat().st_mtime > l.stat().st_mtime:
            s["lock_drift"].append(lock)
    return s


def numeric(value):
    """A finding's value as a number: a count stays itself, a list becomes its length, a flag one."""
    if isinstance(value, bool):
        return 1
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, (int, float)):
        return value
    return 1


def collect(repos, rep, stale_days, expect_email=""):
    """One item per check id, listing the repositories it applies to. Never one item per path."""
    def group(cid, level, pick, message, extra=None):
        """`extra` adds fields a single check needs, such as which branches hold the work."""
        hits = [(s, pick(s)) for s in repos]
        hits = [(s, v) for s, v in hits if v]
        if not hits:
            rep.add("PASS", cid, f"no repository matches {cid}", measure=0)
            return
        rep.add(level, cid, message(len(hits)),
                [{"repo": s["path"], "value": v, **(extra(s) if extra else {})} for s, v in hits],
                measure=len(hits), by={s["path"]: numeric(v) for s, v in hits})

    group("repo.secret-exposed", "FAIL", lambda s: s["secrets"],
          lambda n: f"{plural(n, 'repository', 'repositories')} with an untracked credential file that nothing ignores")
    group("git.dirty", "FAIL", lambda s: s["dirty"] or 0,
          lambda n: f"{plural(n, 'repository', 'repositories')} with uncommitted changes")
    group("git.unpushed", "FAIL", lambda s: s["unpushed"] or 0,
          lambda n: f"{plural(n, 'repository', 'repositories')} with commits that exist on no remote",
          extra=lambda s: {"branches": s.get("unpushed_branches", [])})
    group("repo.no-remote", "WARN", lambda s: (not s["remotes"]) or None,
          lambda n: f"{plural(n, 'repository', 'repositories')} without a remote, so nothing off this disk holds that work")
    group("git.no-upstream", "WARN",
          lambda s: (not s["upstream"] and not s["detached"] and s["remotes"] and s["branch"]) or None,
          lambda n: f"{plural(n, 'repository', 'repositories')} on a branch with no upstream")
    group("git.detached", "WARN", lambda s: s["detached"] or None,
          lambda n: f"{plural(n, 'repository', 'repositories')} with a detached HEAD")
    # The count, not the age of the oldest: an age grows on its own, so it can never be graded.
    group("git.stash-old", "WARN", lambda s: len(s["stashes"]),
          lambda n: f"{plural(n, 'repository', 'repositories')} with a stash older than the retention")
    if expect_email:
        group("git.identity", "WARN", lambda s: s["email"] if s["email"] != expect_email else None,
              lambda n: f"{plural(n, 'repository', 'repositories')} that would commit under an address other than {expect_email}")
    group("git.stale-branch", "INFO", lambda s: len(s["stale_branches"]),
          lambda n: f"{plural(n, 'repository', 'repositories')} with merged branches older than {stale_days} days")
    group("repo.lock-drift", "WARN", lambda s: s["lock_drift"],
          lambda n: f"{plural(n, 'repository', 'repositories')} with a lock file older than its manifest")
    group("repo.no-readme", "INFO", lambda s: (not s["readme"]) or None,
          lambda n: f"{plural(n, 'repository', 'repositories')} without a README")
    group("repo.no-ignore", "INFO", lambda s: (not s["ignore"]) or None,
          lambda n: f"{plural(n, 'repository', 'repositories')} without an ignore file")
    group("repo.no-ci", "INFO", lambda s: (not s["ci"]) or None,
          lambda n: f"{plural(n, 'repository', 'repositories')} that {verb(n, 'run')} no checks on push")


def cell(value):
    """A finding's value as one short string; a list becomes its members, a flag becomes nothing."""
    if value is True:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(x) for x in value)
    return str(value)


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one row waits, two rows wait."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 repository(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def short(path):
    """A path with the home directory written as `~`, so a line stays readable in a terminal."""
    home = str(Path.home())
    text = str(path)
    if text == home:
        return "~"
    return "~" + text[len(home):] if text.startswith(home + "/") else text


def cost(item):
    """What the finding costs now, in words. Every check here counts repositories."""
    m = item.get("measure") or {}
    value = m.get("value")
    return "" if value is None else f"costs {plural(value, 'repository', 'repositories')}"


def detail(item):
    """The rows under one finding as (repository, what was found) pairs, at most five."""
    rows = []
    for d in item["data"][:5]:
        value = cell(d["value"])
        names = d.get("branches", [])
        if names:
            shown = ", ".join(f"{b['branch']} {plural(b['commits'], 'commit')}" for b in names[:2])
            rest = f", and {len(names) - 2} more" if len(names) > 2 else ""
            value = f"{shown}{rest}"
        if value.isdigit() and item["id"] in ROW_WORD:
            value = plural(int(value), *ROW_WORD[item["id"]])
        rows.append((short(d["repo"]), value or "yes"))
    return rows


def block(rows, indent="      "):
    """Name and value in two aligned columns, so the repositories can be compared by eye."""
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


def text_report(repos, rep, targets, standards):
    """The console report: what was scanned, what needs a decision, what is only a note."""
    c = rep.counts()
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    findings = [i for i in ranked if i["level"] in ("FAIL", "WARN")]
    notes = [i for i in ranked if i["level"] == "INFO"]
    passed = [i for i in ranked if i["level"] == "PASS"]
    out = [paint(f"repos  {plural(len(repos), 'repository', 'repositories')} under "
                 + ", ".join(short(t) for t in targets), "head"),
           f"measured against  {standards}", "",
           f"{plural(len(findings), 'finding')} to decide on, "
           f"{plural(len(notes), 'note')}, {plural(len(passed), 'check')} passed"]
    for i in findings:
        tag = paint(f"{i['level']:<4}", i["level"])
        price = paint(f"  ({cost(i)})" if cost(i) else "", "dim")
        out += ["", f"{tag}  {paint(i['id'], 'id')}{price}", f"      {i['message']}"]
        out += block(detail(i))
        if len(i["data"]) > 5:
            out.append(f"      and {len(i['data']) - 5} more, the full list is in the JSON")
    for i in notes:
        out += ["", f"{paint('note', 'INFO')}  {paint(i['id'], 'id')}", f"      {i['message']}"]
        out += block(detail(i))
        if len(i["data"]) > 5:
            out.append(f"      and {len(i['data']) - 5} more, the full list is in the JSON")
    if passed:
        out += ["", paint("passed  " + ", ".join(i["id"] for i in passed), "dim")]
    if findings:
        out += ["", paint("next", "head") + "  save the work a FAIL names before anything else, then look each id up "
                    "in the fixes table of jorekai-dx:dx for the fix and the risk class"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--depth", type=int, default=3, help="how deep under a path a repository is still found")
    ap.add_argument("--stale-days", type=int, default=90, help="a merged branch older than this is reported")
    ap.add_argument("--stash-days", type=int, default=None, help="a stash older than this is reported")
    ap.add_argument("--expect-email", default="", metavar="ADDRESS",
                    help="the address commits should carry; without it the check does not run")
    ap.add_argument("--timeout", type=float, default=10, help="seconds for one git call")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", type=int, default=None, help="unix seconds, for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    if not a.paths:
        ap.error("a PATH is required")
    now = a.now if a.now is not None else int(time.time())
    found = find_repos(a.paths, a.depth)
    stash_days = a.stale_days if a.stash_days is None else a.stash_days
    states = [read_repo(p, now, a.stale_days, stash_days, a.timeout) for p in found]
    rep = Report()
    collect(states, rep, a.stale_days, a.expect_email)
    if a.json:
        print(json.dumps({"tool": "repos", "target": [str(Path(p).expanduser()) for p in a.paths],
                          "generated": dt.datetime.fromtimestamp(now).date().isoformat(),
                          "counts": rep.counts(), "repos": states, "items": rep.items},
                         indent=2, ensure_ascii=False))
    else:
        standards = (f"merged branches over {plural(a.stale_days, 'day')} \u00b7 "
                     f"stashes over {plural(stash_days, 'day')}"
                     + (f" \u00b7 commits under {a.expect_email}" if a.expect_email else ""))
        print(text_report(states, rep, [str(Path(p).expanduser()) for p in a.paths], standards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
