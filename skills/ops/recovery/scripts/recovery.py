#!/usr/bin/env python3
"""What survives this host: the copies of its data, the secrets on it, and what its journal keeps.

Usage:
  recovery.py [--backup SPEC ...] [--secret PATH ...] [--root DIR] [--unit-dir DIR]
              [--journald-conf FILE] [--journald-dropin-dir DIR] [--rpo-hours N]
              [--restore-test-days N] [--log-share-percent N] [--filesystem-bytes N]
              [--now YYYY-MM-DDTHH:MM:SS] [--json]
  recovery.py --measures              the unit every check id is measured in

SPEC is `name=label,source=PATH[,copy=PATH][,copy=PATH][,tested=YYYY-MM-DD]`, one per thing the
standards say is backed up. A `copy` that names a host (`host:/path`) or carries a scheme is off
this host and this pass does not reach it; a plain path is read under `--root`. `scaffold.py
--flags` in the setup skill prints every argument from the workspace.

Reads names, modes, write times, and unit settings. It never reads the contents of a secret and
never writes one into its output, so a finding names the file and the unit, never the value.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import textwrap
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
MEASURES = {"backup.missing": "count", "backup.stale": "count", "backup.offsite": "count",
            "backup.untested": "count", "secret.missing": "count", "secret.mode": "count",
            "secret.in-repo": "count", "secret.plaintext": "count",
            "log.no-retention": "count", "log.growth": "percent"}
# What the number in a row counts, per check id.
ROW_WORD = {"backup.missing": ("target without a copy", "targets without a copy"),
            "backup.stale": ("target past its window", "targets past their window"),
            "backup.offsite": ("target with every copy here", "targets with every copy here"),
            "backup.untested": ("target without a restore test", "targets without a restore test"),
            "secret.missing": ("secret that is not there", "secrets that are not there"),
            "secret.mode": ("secret readable beyond its owner", "secrets readable beyond their owner"),
            "secret.in-repo": ("secret inside a work tree", "secrets inside a work tree"),
            "secret.plaintext": ("credential passed in a unit", "credentials passed in units"),
            "log.no-retention": ("bound nobody set", "bounds nobody set"),
            "log.growth": ("percentage point over the share", "percentage points over the share")}
SPEC_KEYS = ("source", "copy", "tested")
# A name that says the value beside it opens something. The names are the finding, never the
# values: systemd.exec says environment variables set for a unit reach unprivileged clients over
# D-Bus, so the name alone is enough to know a credential is passed the wrong way.
CREDENTIAL_NAME = re.compile(
    r"(PASS|PASSWD|PASSWORD|SECRET|TOKEN|APIKEY|API_KEY|PRIVATE_KEY|CREDENTIAL|_KEY|KEY_)", re.I)
ASSIGN = re.compile(r"^\s*(Environment|EnvironmentFile)\s*=\s*(.*)$")
SETTING = re.compile(r"^\s*([A-Za-z]+)\s*=\s*(.*?)\s*$")
# `host:/path` and `scheme://...` name a place this host is not. A plain path is on this host.
REMOTE = re.compile(r"^([A-Za-z][\w.+-]*://|[\w.-]+@|[\w.-]+:(?=[/~]))")
# The time units journald.conf accepts on MaxRetentionSec, in seconds.
TIME_UNIT = {"": 1, "s": 1, "sec": 1, "second": 1, "seconds": 1, "m": 60, "min": 60,
             "minute": 60, "minutes": 60, "h": 3600, "hour": 3600, "hours": 3600,
             "d": 86400, "day": 86400, "days": 86400, "w": 604800, "week": 604800,
             "weeks": 604800, "month": 2629800, "months": 2629800, "year": 31557600,
             "years": 31557600}


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one target grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def parse_spec(text):
    """`name=web,source=/srv/web,copy=/backup/web,tested=2026-09-01` as a dict.

    `copy` may stand several times, because a target with one copy and a target with three are
    the same shape. A field this function does not know is refused rather than dropped: a typo
    that is ignored turns a check off without saying so.
    """
    head, _, rest = text.partition(",")
    name, _, label = head.partition("=")
    if not name or not label:
        sys.exit(f"not a backup spec: {text!r}. Expected name=label,source=PATH[,copy=PATH]")
    spec = {"name": name.strip(), "label": label.strip(), "source": "", "copies": [], "tested": ""}
    for part in rest.split(",") if rest else []:
        key, _, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if not key:
            continue
        if key not in SPEC_KEYS:
            sys.exit(f"unknown field {key!r} in {text!r}. One of {', '.join(SPEC_KEYS)}")
        if key == "copy":
            spec["copies"].append(value)
        else:
            spec[key] = value
    return spec


def under(root, path):
    """A path from the workspace, read under `--root`. Absolute paths make the fixtures work."""
    return Path(root) / str(path).lstrip("/")


def newest(path):
    """The newest write time under a path, as a naive datetime, or None when nothing is there.

    A backup is a directory of files as often as it is one file, and the age of the directory
    itself says nothing: a copy written into it leaves the directory's own time behind.
    """
    p = Path(path)
    times = []
    if p.is_file():
        times.append(p.stat().st_mtime)
    elif p.is_dir():
        for child in p.rglob("*"):
            try:
                if child.is_file():
                    times.append(child.stat().st_mtime)
            except OSError:
                continue
    if not times:
        return None
    return dt.datetime.fromtimestamp(max(times))


def is_remote(copy):
    return bool(REMOTE.match(copy))


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def read_backups(specs, a):
    """What every backup target says about itself. One read pass, no decisions."""
    out = []
    for spec in specs:
        t = dict(spec)
        t["remote"] = [c for c in spec["copies"] if is_remote(c)]
        t["local"] = []
        for c in spec["copies"]:
            if is_remote(c):
                continue
            p = under(a.root, c)
            when = newest(p)
            # A directory that exists and holds nothing is not a copy. Only a file inside it is,
            # which is the same thing that dates the copy, so both answers come from one read.
            t["local"].append({"path": c, "exists": when is not None, "newest": when})
        t["source_exists"] = bool(spec["source"]) and under(a.root, spec["source"]).exists()
        out.append(t)
    return out


def secret_files(paths, root):
    """Every file the recorded secret paths name. A directory contributes the files inside it."""
    out = []
    for raw in paths:
        p = under(root, raw)
        if p.is_dir():
            out += [{"recorded": raw, "path": c, "exists": True}
                    for c in sorted(p.rglob("*")) if c.is_file()]
        else:
            out.append({"recorded": raw, "path": p, "exists": p.is_file()})
    return out


def git(repo, *args, timeout=10):
    """One git command in repo. Returns stdout, or None when git fails or takes too long."""
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                           timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def work_tree(path):
    """The nearest directory above `path` that holds a .git, or None."""
    for parent in Path(path).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return None


def in_repository(path):
    """How a file sits in a work tree: `tracked`, `not ignored`, or an empty string.

    Ignored is the answer that ends the finding: a secret git was told to leave alone is not on
    its way into a history. Tracked is the worst of the three, because a history keeps it.
    """
    repo = work_tree(path)
    if repo is None:
        return "", None
    if git(repo, "ls-files", "--error-unmatch", str(path)) is not None:
        return "tracked", repo
    if subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", str(path)],
                      capture_output=True).returncode == 0:
        return "", repo
    return "not ignored", repo


def unit_files(a):
    """Every unit file this pass reads, newest location last so a later one wins its name."""
    seen = {}
    dirs = [Path(a.unit_dir)] if a.unit_dir else [under(a.root, d) for d in
                                                 ("usr/lib/systemd/system", "etc/systemd/system")]
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix in (".service", ".socket", ".timer", ".conf"):
                # The key is the path under the unit directory, never the file name: a unit in
                # /etc replaces the one in /usr/lib, while every drop-in is called override.conf
                # and keying by name would drop all but one of them.
                seen[str(p.relative_to(d))] = p
    return [seen[name] for name in sorted(seen)]


def credentials_in_units(files):
    """Names passed to a unit as environment variables, and the files it loads them from.

    The value is never read and never stored. A name is enough: systemd.exec says environment
    variables set for a unit are exposed to unprivileged clients over D-Bus IPC.
    """
    inline, loaded = [], []
    for p in files:
        for line in (read(p) or "").splitlines():
            m = ASSIGN.match(line.split("#", 1)[0])
            if not m:
                continue
            if m.group(1) == "EnvironmentFile":
                loaded.append({"unit": p.name, "file": m.group(2).strip().lstrip("-")})
                continue
            for token in re.findall(r'"?([A-Za-z_][A-Za-z0-9_]*)=', m.group(2)):
                if CREDENTIAL_NAME.search(token):
                    inline.append({"unit": p.name, "name": token})
    return inline, loaded


def journald_settings(a):
    """Settings from journald.conf and its drop-ins, plus every file that carried one.

    `man 5 journald.conf` lists the main file and `journald.conf.d/*.conf` beside it, so a value
    set in a drop-in is the value that counts, and a check that reads only the main file reports
    a default the host does not run.
    """
    files = []
    if a.journald_conf:
        files.append(Path(a.journald_conf))
    else:
        files.append(under(a.root, "etc/systemd/journald.conf"))
    dropin = Path(a.journald_dropin_dir) if a.journald_dropin_dir else \
        under(a.root, "etc/systemd/journald.conf.d")
    if dropin.is_dir():
        files += sorted(p for p in dropin.iterdir() if p.suffix == ".conf")
    out, source = {}, {}
    for p in files:
        text = read(p)
        if text is None:
            continue
        for line in text.splitlines():
            stripped = line.split("#", 1)[0].split(";", 1)[0]
            m = SETTING.match(stripped)
            if m and m.group(2) != "":
                out[m.group(1)] = m.group(2)
                source[m.group(1)] = p.name
    return out, source


def seconds(value):
    """A journald time value as seconds, or None. `30d`, `2 week`, `900` all parse."""
    total, found = 0, False
    for number, unit in re.findall(r"(\d+)\s*([A-Za-z]*)", value or ""):
        if unit.lower() not in TIME_UNIT:
            return None
        total += int(number) * TIME_UNIT[unit.lower()]
        found = True
    return total if found else None


def journal_usage(a):
    """What the journal holds and what its filesystem holds, in bytes.

    Only files ending in .journal or .journal~ count, which is what journalctl and
    systemd-journald do when they add up their own usage, so this number is the one the size
    caps act on. An archived file carries the second suffix and takes the same space.
    """
    directory = under(a.root, "var/log/journal")
    if not directory.is_dir():
        return None, None, directory
    used = 0
    for p in list(directory.rglob("*.journal")) + list(directory.rglob("*.journal~")):
        try:
            used += p.stat().st_size
        except OSError:
            continue
    if a.filesystem_bytes:
        return used, a.filesystem_bytes, directory
    try:
        st = os.statvfs(directory)
        return used, st.f_blocks * st.f_frsize, directory
    except OSError:
        return used, None, directory


def collect(targets, secrets, rep, a, now):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    if targets:
        no_copy = [t for t in targets
                   if not t["remote"] and not any(c["exists"] for c in t["local"])]
        if no_copy:
            rep.add("FAIL", "backup.missing",
                    f"{plural(len(no_copy), 'target')} the standards name {verb(len(no_copy), 'have', 'has')} no copy "
                    "on this host and none recorded anywhere else",
                    data=[{"target": t["name"], "value": t["label"] or t["source"]} for t in no_copy],
                    measure=len(no_copy), by={t["name"]: 1 for t in no_copy})
        else:
            rep.add("PASS", "backup.missing", "every target the standards name has a copy", measure=0)

        window = dt.timedelta(hours=a.rpo_hours)
        stale, by = [], {}
        for t in targets:
            times = [c["newest"] for c in t["local"] if c["newest"]]
            if not times:
                continue
            age = now - max(times)
            if age > window:
                stale.append((t, max(times)))
                by[t["name"]] = 1
        datable = [t for t in targets if any(c["newest"] for c in t["local"])]
        if stale:
            rep.add("FAIL", "backup.stale",
                    f"{plural(len(stale), 'target')} {verb(len(stale), 'carry', 'carries')} a newest copy older than the "
                    f"window of {plural(a.rpo_hours, 'hour')}",
                    data=[{"target": t["name"], "value": when.date().isoformat()} for t, when in stale],
                    measure=len(stale), by=by)
        elif datable:
            # The zero is about the targets this pass could date. A target whose only copy is off
            # this host has no date here, so it is named in the note below and not passed.
            rep.add("PASS", "backup.stale", "every copy this pass can date is inside the window",
                    measure=0, by={t["name"]: 0 for t in datable})

        undated = [t for t in targets if not any(c["newest"] for c in t["local"])]
        if undated:
            rep.add("INFO", "backup.stale",
                    f"{plural(len(undated), 'target')} {verb(len(undated), 'carry', 'carries')} no copy this pass can "
                    "date, so nothing here says how old it is",
                    data=[{"target": t["name"], "value": ", ".join(t["remote"]) or "no copy on this host"}
                          for t in undated])

        here = [t for t in targets if not t["remote"]]
        if here:
            rep.add("FAIL", "backup.offsite",
                    f"{plural(len(here), 'target')} {verb(len(here), 'keep')} every copy on this host, so what takes the "
                    "host takes the copy with it",
                    data=[{"target": t["name"],
                           "value": ", ".join(c["path"] for c in t["local"]) or "no copy at all"}
                          for t in here],
                    measure=len(here), by={t["name"]: 1 for t in here})
        else:
            rep.add("PASS", "backup.offsite", "every target has a copy off this host", measure=0)

        limit = dt.timedelta(days=a.restore_test_days)
        untested, by = [], {}
        for t in targets:
            when = date(t["tested"])
            if when is None or (now - when) > limit:
                untested.append((t, t["tested"] or "never"))
                by[t["name"]] = 1
        if untested:
            rep.add("WARN", "backup.untested",
                    f"{plural(len(untested), 'target')} {verb(len(untested), 'have', 'has')} no restore test inside the "
                    f"last {plural(a.restore_test_days, 'day')}",
                    data=[{"target": t["name"], "value": when} for t, when in untested],
                    measure=len(untested), by=by)
        else:
            rep.add("PASS", "backup.untested", "every target was restored inside the window", measure=0)
    else:
        rep.add("INFO", "backup.missing",
                "no backup target is recorded for this host, so nothing says what should survive it")

    if secrets:
        gone = [s for s in secrets if not s["exists"]]
        if gone:
            rep.add("WARN", "secret.missing",
                    f"{plural(len(gone), 'secret')} the standards name {verb(len(gone), 'are', 'is')} not on this host",
                    data=[{"target": str(s["recorded"]), "value": "not there"} for s in gone],
                    measure=len(gone), by={str(s["recorded"]): 1 for s in gone})
        else:
            rep.add("PASS", "secret.missing", "every secret the standards name is on this host", measure=0)

        open_mode, by = [], {}
        for s in secrets:
            if not s["exists"]:
                continue
            try:
                mode = Path(s["path"]).stat().st_mode & 0o777
            except OSError:
                continue
            if mode & 0o077:
                open_mode.append((s, mode))
                by[str(s["path"])] = 1
        if open_mode:
            rep.add("FAIL", "secret.mode",
                    f"{plural(len(open_mode), 'secret')} {verb(len(open_mode), 'are', 'is')} readable or writable by more "
                    "than the account that owns it",
                    data=[{"target": str(s["path"]), "value": oct(mode)[2:].rjust(3, '0')}
                          for s, mode in open_mode],
                    measure=len(open_mode), by=by)
        else:
            rep.add("PASS", "secret.mode", "every secret is reachable by its owner alone", measure=0)

        inside, by = [], {}
        for s in secrets:
            if not s["exists"]:
                continue
            how, repo = in_repository(s["path"])
            if how:
                inside.append((s, how, repo))
                by[str(s["path"])] = 1
        if inside:
            rep.add("FAIL", "secret.in-repo",
                    f"{plural(len(inside), 'secret')} {verb(len(inside), 'sit')} inside a work tree without being ignored, "
                    "so a commit can take one into a history that keeps it",
                    data=[{"target": str(s["path"]), "value": f"{how} in {repo.name}"}
                          for s, how, repo in inside],
                    measure=len(inside), by=by)
        else:
            rep.add("PASS", "secret.in-repo", "no secret sits in a work tree that could commit it",
                    measure=0)
    else:
        rep.add("INFO", "secret.mode",
                "no secret path is recorded for this host, so these checks are off")

    inline, loaded = credentials_in_units(unit_files(a))
    if inline:
        by = {}
        for row in inline:
            by[row["unit"]] = by.get(row["unit"], 0) + 1
        rep.add("FAIL", "secret.plaintext",
                f"{plural(len(inline), 'credential')} {verb(len(inline), 'reach', 'reaches')} a service as an "
                "environment variable, "
                "which unprivileged clients can read back over D-Bus",
                data=[{"target": row["unit"], "value": row["name"]} for row in inline],
                measure=len(inline), by=by)
    else:
        rep.add("PASS", "secret.plaintext", "no unit passes a credential as an environment variable",
                measure=0)
    if loaded:
        rep.add("INFO", "secret.plaintext",
                f"{plural(len(loaded), 'unit')} {verb(len(loaded), 'load')} an environment file, whose names this pass "
                "does not read because reading it would mean reading the values",
                data=[{"target": row["unit"], "value": row["file"]} for row in loaded])

    settings, source = journald_settings(a)
    unbound = [name for name in ("MaxRetentionSec", "SystemMaxUse") if name not in settings]
    short = seconds(settings.get("MaxRetentionSec", ""))
    if unbound:
        rep.add("WARN", "log.no-retention",
                f"{plural(len(unbound), 'bound')} on the journal {verb(len(unbound), 'are', 'is')} nobody's decision, so "
                "what happens to a log here is whatever the build chose",
                data=[{"target": name, "value": "not set"} for name in unbound],
                measure=len(unbound), by={name: 1 for name in unbound})
    else:
        rep.add("PASS", "log.no-retention",
                f"both bounds are set: {settings['MaxRetentionSec']} in {source['MaxRetentionSec']}, "
                f"{settings['SystemMaxUse']} in {source['SystemMaxUse']}", measure=0)
    if short is not None and short == 0:
        rep.add("INFO", "log.no-retention",
                "MaxRetentionSec is 0, which turns age-based deletion off: only the size caps "
                "decide how far back the journal reaches",
                data=[{"target": "MaxRetentionSec", "value": "0"}])
    persistent = settings.get("Storage", "").strip()
    journal_dir = under(a.root, "var/log/journal")
    if persistent != "persistent" and not journal_dir.is_dir():
        rep.add("INFO", "log.no-retention",
                "the journal is volatile: Storage is not persistent and /var/log/journal does not "
                "exist, so a reboot takes every entry with it",
                data=[{"target": "Storage", "value": persistent or "not set"}])

    used, total, directory = journal_usage(a)
    if used is None:
        rep.add("INFO", "log.growth", "no journal directory on disk, so there is nothing to grow")
    elif not total:
        rep.add("INFO", "log.growth", "the filesystem under the journal did not report a size")
    else:
        share = round(used * 100.0 / total, 1)
        over = round(share - a.log_share_percent, 1)
        if over > 0:
            rep.add("WARN", "log.growth",
                    f"the journal holds {share} percent of its filesystem, over the "
                    f"{a.log_share_percent} percent the standards allow",
                    data=[{"target": str(directory), "value": f"{used} bytes of {total}"}],
                    measure=over, by={str(directory): over})
        else:
            rep.add("PASS", "log.growth",
                    f"the journal holds {share} percent of its filesystem", measure=0)
    return rep


def date(value):
    try:
        return dt.datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one target keeps, two keep."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 target(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def cost(item):
    """The cost of a finding as one number and one unit, the column the eye lands on."""
    m = item.get("measure") or {}
    value = m.get("value")
    if value is None:
        return ""
    return plural(value, *ROW_WORD.get(item["id"], ("finding", "findings")))


def block(rows, indent="      "):
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


def detail(item):
    return [(str(d.get("target", "")), str(d.get("value", "")) or "yes") for d in item["data"][:5]]


ID_WIDTH = 28


def bar(fails, warns, notes, passed):
    """Four counts in one line, a zero dimmed, a count above zero in the colour of its word."""
    cells = [(fails, "FAIL", "FAIL"), (warns, "WARN", "WARN"),
             (notes, plural(notes, "note").split()[1], "INFO"),
             (passed, "passed", "PASS")]
    return " · ".join(paint(f"{n} {word}", key if n else "dim") for n, word, key in cells)


def finding_line(item):
    """Level, id padded to one width, cost: three columns, so the eye reads down them.

    A note carries no cost, so its id stands unpadded: padding a column that never comes only
    to strip it again would depend on whether colour wraps the trailing spaces or not.
    """
    tag = paint("note" if item["level"] == "INFO" else f"{item['level']:<4}", item["level"])
    price = cost(item) if item["level"] != "INFO" else ""
    if not price:
        return f"{tag}  {paint(item['id'], 'id')}"
    return f"{tag}  {paint(item['id'].ljust(ID_WIDTH), 'id')}  {paint(price, 'dim')}"


def wrapped(label, words, width=80):
    """A dimmed list that wraps at the terminal's width, the label once."""
    lines = textwrap.wrap(", ".join(words), width=width - len(label) - 2, break_on_hyphens=False)
    indent = " " * (len(label) + 2)
    return [paint(f"{label}  {lines[0]}", "dim")] + [paint(indent + l, "dim") for l in lines[1:]]


def text_report(targets, secrets, rep, target_name, standards):
    """The console report: what was measured, what needs a decision, what is only a note."""
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    findings = [i for i in ranked if i["level"] in ("FAIL", "WARN")]
    notes = [i for i in ranked if i["level"] == "INFO"]
    passed = [i for i in ranked if i["level"] == "PASS"]
    fails = sum(1 for i in findings if i["level"] == "FAIL")
    out = [paint(f"recovery  {target_name}  {plural(len(targets), 'backup target')}, "
                 f"{plural(len(secrets), 'secret')}", "head"),
           f"measured against  {standards}", "",
           bar(fails, len(findings) - fails, len(notes), len(passed))]
    for i in findings + notes:
        out += ["", finding_line(i), f"      {i['message']}"]
        out += block(detail(i))
        if len(i["data"]) > 5:
            out.append(paint(f"      +{len(i['data']) - 5} more in the JSON", "dim"))
    if passed:
        out += [""] + wrapped("passed", sorted({i["id"] for i in passed}))
    if findings:
        out += ["", paint("next", "head") + "  a copy that exists somewhere else comes before a "
                "secret that is only readable too widely, and both come before the journal, then "
                "look each id up in the fixes table of jorekai-ops:ops for the fix per control "
                "plane and the risk class"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backup", action="append", metavar="SPEC",
                    help="name=label,source=PATH[,copy=PATH][,tested=YYYY-MM-DD]")
    ap.add_argument("--secret", action="append", metavar="PATH",
                    help="a file or directory holding a credential this host needs")
    ap.add_argument("--root", default="/", help="filesystem root every path is read under")
    ap.add_argument("--unit-dir", default="", metavar="DIR",
                    help="unit files to read instead of the ones under --root")
    ap.add_argument("--journald-conf", default="", metavar="FILE")
    ap.add_argument("--journald-dropin-dir", default="", metavar="DIR")
    ap.add_argument("--rpo-hours", type=int, default=24,
                    help="how old the newest copy of a target may be")
    ap.add_argument("--restore-test-days", type=int, default=90,
                    help="how long a restore test counts for")
    ap.add_argument("--log-share-percent", type=float, default=10.0,
                    help="share of its filesystem the journal may hold")
    ap.add_argument("--filesystem-bytes", type=int, default=0,
                    help="size of the filesystem under the journal, for tests")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", default=None, metavar="YYYY-MM-DDTHH:MM:SS", help="for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()
    targets = read_backups([parse_spec(s) for s in a.backup or []], a)
    secrets = secret_files(a.secret or [], a.root)
    rep = collect(targets, secrets, Report(), a, now)
    target_name = a.root if a.root != "/" else "this host"
    if a.json:
        print(json.dumps({"tool": "recovery", "target": target_name,
                          "generated": now.date().isoformat(), "counts": rep.counts(),
                          "backups": [{"name": t["name"], "label": t["label"],
                                       "source": t["source"], "tested": t["tested"],
                                       "remote": t["remote"],
                                       "local": [{"path": c["path"], "exists": c["exists"],
                                                  "newest": c["newest"].isoformat() if c["newest"] else ""}
                                                 for c in t["local"]]} for t in targets],
                          "secrets": [str(s["recorded"]) for s in secrets],
                          "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        standards = (f"a copy no older than {plural(a.rpo_hours, 'hour')}"
                     f" · a restore test inside {plural(a.restore_test_days, 'day')}"
                     f" · a journal under {a.log_share_percent} percent of its filesystem")
        print(text_report(targets, secrets, rep, target_name, standards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
