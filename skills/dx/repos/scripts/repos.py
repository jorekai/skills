#!/usr/bin/env python3
"""State of every local repository under one or more paths: unsaved work first, then hygiene.

Usage:
  repos.py PATH [PATH ...] [--depth N] [--stale-days N] [--stash-days N]
           [--expect-email ADDRESS] [--timeout S] [--json]

`scaffold.py --flags` in the setup skill prints these arguments from the workspace standards.

A PATH is either a repository or a directory to scan for repositories. Every check runs
locally: no fetch, no push, no network. Nothing is written and nothing is removed.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

LEVEL_ORDER = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
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


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None):
        self.items.append({"id": cid, "level": level, "message": message, "data": data or []})

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
    s["unpushed"] = 0
    if s["remotes"]:
        out = git(repo, "log", "--branches", "--not", "--remotes", "--format=%H", timeout=timeout)
        s["unpushed"] = len([l for l in (out or "").splitlines() if l])

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
    s["readme"] = any((repo / n).exists() for n in READMES)
    s["ignore"] = (repo / ".gitignore").exists()
    s["ci"] = any((repo / c).exists() for c in CI_PATHS)
    s["lock_drift"] = []
    for manifest, lock in LOCKS:
        m, l = repo / manifest, repo / lock
        if m.exists() and l.exists() and m.stat().st_mtime > l.stat().st_mtime:
            s["lock_drift"].append(lock)
    return s


def collect(repos, rep, stale_days, expect_email=""):
    """One item per check id, listing the repositories it applies to. Never one item per path."""
    def group(cid, level, pick, message):
        hits = [(s, pick(s)) for s in repos]
        hits = [(s, v) for s, v in hits if v]
        if not hits:
            rep.add("PASS", cid, f"no repository matches {cid}")
            return
        rep.add(level, cid, message(len(hits)),
                [{"repo": s["path"], "value": v} for s, v in hits])

    group("git.dirty", "FAIL", lambda s: s["dirty"] or 0,
          lambda n: f"{n} repository(s) hold uncommitted changes")
    group("git.unpushed", "FAIL", lambda s: s["unpushed"] or 0,
          lambda n: f"{n} repository(s) hold commits that exist on no remote")
    group("repo.no-remote", "WARN", lambda s: (not s["remotes"]) or None,
          lambda n: f"{n} repository(s) have no remote, so nothing off this disk holds them")
    group("git.no-upstream", "WARN",
          lambda s: (not s["upstream"] and not s["detached"] and s["remotes"] and s["branch"]) or None,
          lambda n: f"{n} repository(s) sit on a branch with no upstream")
    group("git.detached", "WARN", lambda s: s["detached"] or None,
          lambda n: f"{n} repository(s) have a detached HEAD")
    group("git.stash-old", "WARN", lambda s: max(s["stashes"]) if s["stashes"] else 0,
          lambda n: f"{n} repository(s) carry a stash older than the retention")
    if expect_email:
        group("git.identity", "WARN", lambda s: s["email"] if s["email"] != expect_email else None,
              lambda n: f"{n} repository(s) would commit under an address other than {expect_email}")
    group("git.stale-branch", "INFO", lambda s: len(s["stale_branches"]),
          lambda n: f"{n} repository(s) keep merged branches older than {stale_days} days")
    group("repo.lock-drift", "WARN", lambda s: s["lock_drift"],
          lambda n: f"{n} repository(s) have a lock file older than its manifest")
    group("repo.no-readme", "INFO", lambda s: (not s["readme"]) or None,
          lambda n: f"{n} repository(s) have no README")
    group("repo.no-ignore", "INFO", lambda s: (not s["ignore"]) or None,
          lambda n: f"{n} repository(s) have no ignore file")
    group("repo.no-ci", "INFO", lambda s: (not s["ci"]) or None,
          lambda n: f"{n} repository(s) run no checks on push")


def cell(value):
    """A finding's value as one short string; a list becomes its members, a flag becomes nothing."""
    if value is True:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(x) for x in value)
    return str(value)


def text_report(repos, rep):
    c = rep.counts()
    out = [f"# repos: {len(repos)} repository(s)",
           f"FAIL {c.get('FAIL', 0)} · WARN {c.get('WARN', 0)} · INFO {c.get('INFO', 0)} · PASS {c.get('PASS', 0)}", ""]
    for i in sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]], x["id"])):
        if i["level"] == "PASS":
            continue
        out.append(f"- **{i['level']}** `{i['id']}`: {i['message']}")
        for d in i["data"][:5]:
            v = cell(d["value"])
            out.append(f"    - {d['repo']}" + (f": {v}" if v else ""))
        if len(i["data"]) > 5:
            out.append(f"    - and {len(i['data']) - 5} more, full list in the JSON")
    if not any(i["level"] != "PASS" for i in rep.items):
        out.append("- nothing open")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--depth", type=int, default=3, help="how deep under a path a repository is still found")
    ap.add_argument("--stale-days", type=int, default=90, help="a merged branch older than this is reported")
    ap.add_argument("--stash-days", type=int, default=None, help="a stash older than this is reported")
    ap.add_argument("--expect-email", default="", metavar="ADDRESS",
                    help="the address commits should carry; without it the check does not run")
    ap.add_argument("--timeout", type=float, default=10, help="seconds for one git call")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", type=int, default=None, help="unix seconds, for tests")
    a = ap.parse_args(argv)
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
        print(text_report(states, rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
