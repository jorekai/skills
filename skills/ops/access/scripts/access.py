#!/usr/bin/env python3
"""Who can reach this host, with which keys, and under which sudo rules.

Usage:
  access.py [--root DIR] [--sshd-config FILE] [--passwd FILE] [--sudoers FILE]
            [--sudoers-dir DIR] [--allow-user NAME ...] [--allow-sudo-command CMD ...]
            [--min-key-bits N] [--key-rotation YYYY-MM-DD] [--path NAME ...] [--paths-bar N]
            [--weak-algorithm NAME ...] [--max-auth-tries N] [--json]
  access.py --measures                    the unit every check id is measured in

`scaffold.py --flags` in the setup skill prints these arguments from the workspace standards.

Reads only. Nothing is written, nothing is removed, no network. `--root` prefixes every default
path, so the whole pass runs against a captured tree in a test.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import os
import argparse
import base64
import binascii
import datetime as dt
import json
import re
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
MEASURES = {"ssh.root-login": "count", "ssh.password-auth": "count", "ssh.weak-crypto": "count",
            "ssh.no-limit": "count", "key.orphan": "count", "key.past-rotation": "count",
            "key.weak": "count", "key.duplicate": "count", "access.single-path": "count",
            "sudo.nopasswd": "count", "user.unlisted": "count"}
# What the number in a row counts, per check id. A bare number leaves the reader guessing whether
# it means keys, accounts, or settings.
ROW_WORD = {"key.orphan": ("key", "keys"), "key.past-rotation": ("key", "keys"),
            "key.weak": ("key", "keys"), "key.duplicate": ("account", "accounts"),
            "sudo.nopasswd": ("rule", "rules"), "ssh.weak-crypto": ("algorithm", "algorithms"),
            "ssh.no-limit": ("missing limit", "missing limits"),
            "ssh.root-login": ("open way in", "open ways in"),
            "ssh.password-auth": ("setting", "settings"),
            "access.single-path": ("missing way in", "missing ways in"),
            "user.unlisted": ("account", "accounts")}
# Algorithms OpenSSH itself no longer offers by default, or that rest on SHA-1 or a 64-bit block
# cipher. The list is a heuristic, not a standard: it is an argument, so a host can extend it.
WEAK_ALGORITHMS = ("diffie-hellman-group1-sha1", "diffie-hellman-group14-sha1",
                   "diffie-hellman-group-exchange-sha1", "ssh-dss", "ssh-rsa",
                   "hmac-sha1", "hmac-sha1-96", "hmac-md5", "hmac-md5-96", "umac-64@openssh.com",
                   "3des-cbc", "aes128-cbc", "aes192-cbc", "aes256-cbc", "arcfour",
                   "arcfour128", "arcfour256", "rijndael-cbc@lysator.liu.se")
# A key type that is weak whatever its size. DSA is fixed at 1024 bits and OpenSSH removed it.
WEAK_KEY_TYPES = ("ssh-dss",)
# The four limits in front of sshd this check looks for. Each one is a separate answer, so the
# measure counts how many are missing rather than reporting one yes or no.
LIMITS = ("allow-list", "max-auth-tries", "login-grace-time", "max-startups")
# A shell that is not a login shell. An account carrying one cannot be used to log in, so it is
# neither an unlisted account nor a way in.
NOLOGIN = re.compile(r"(nologin|/false|/sync|/shutdown|/halt)$")
SUDO_NOPASSWD = re.compile(r"\bNOPASSWD\s*:", re.I)


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


def read(path):
    """A file's text, or None when it is missing or unreadable. A missing source is a note."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def sshd_settings(text, base=None, seen=None, root="/"):
    """Effective sshd settings as {keyword: [values]}, first value wins, Include expanded in place.

    Accepts both a sshd_config and the output of `sshd -T`. sshd takes the first obtained value
    for each keyword, and Ubuntu ships an Include at the top of the file, so a dropped-in file
    under sshd_config.d wins over the defaults below it. Expanding the include in place is the
    only way to read what the daemon actually runs with.

    The first `Match` line ends the global section. Keywords below it apply only to connections
    that meet its criteria, so reading one here would report a setting the daemon does not use
    for everyone. `match_blocks` reads those instead.
    """
    out, seen = {}, seen if seen is not None else set()
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.replace("=", " ", 1).split()
        if parts and parts[0].lower() == "match":
            break
        if len(parts) < 2:
            continue
        key, values = parts[0].lower(), parts[1:]
        if key == "include" and base is not None:
            for pattern in values:
                # An absolute Include is resolved under the same root the configuration came
                # from, so a pass against a captured tree never reads the running host.
                target = Path(root) / pattern.lstrip("/") if pattern.startswith("/") \
                    else Path(base) / pattern
                for f in sorted(target.parent.glob(target.name)) if target.parent.is_dir() else []:
                    if str(f) in seen or not f.is_file():
                        continue
                    seen.add(str(f))
                    for k, v in sshd_settings(read(f), str(f.parent), seen, root).items():
                        out.setdefault(k, v)
            continue
        out.setdefault(key, values)
    return out


def match_blocks(text):
    """Keywords re-enabled inside a Match block, as (condition, keyword, value) triples.

    A Match block is where a global `no` quietly becomes a `yes` for one group, and the top level
    of the file says nothing about it.
    """
    found, condition = [], None
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if parts[0].lower() == "match":
            condition = " ".join(parts[1:])
            continue
        if condition and len(parts) >= 2:
            found.append((condition, parts[0].lower(), parts[1].lower()))
    return found


def key_bits(blob):
    """Bit length of an RSA key from its base64 blob, or None for any other type.

    The wire format is a sequence of length-prefixed fields: type, then the public exponent, then
    the modulus. The modulus decides the size, and its leading zero byte is padding, not size.
    """
    try:
        raw = base64.b64decode(blob, validate=True)
    except (binascii.Error, ValueError):
        return None
    fields, i = [], 0
    while i + 4 <= len(raw) and len(fields) < 3:
        size = int.from_bytes(raw[i:i + 4], "big")
        i += 4
        if size > len(raw) - i:
            return None
        fields.append(raw[i:i + size])
        i += size
    if len(fields) < 3 or fields[0] != b"ssh-rsa":
        return None
    modulus = fields[2].lstrip(b"\x00")
    return len(modulus) * 8 if modulus else None


def parse_authorized_keys(text):
    """Keys in one authorized_keys file as {type, blob, comment, options}."""
    keys = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        # An options field comes first and holds no spaces outside quotes; the key type is the
        # first field that looks like one, so a line with options parses the same way.
        start = next((i for i, p in enumerate(parts)
                      if p.startswith(("ssh-", "ecdsa-", "sk-"))), None)
        if start is None or start + 1 >= len(parts):
            continue
        keys.append({"type": parts[start], "blob": parts[start + 1],
                     "comment": " ".join(parts[start + 2:]),
                     "options": " ".join(parts[:start])})
    return keys


def parse_passwd(text):
    """Accounts from a passwd file as {name, uid, home, shell}."""
    accounts = []
    for line in (text or "").splitlines():
        parts = line.split(":")
        if len(parts) < 7:
            continue
        try:
            uid = int(parts[2])
        except ValueError:
            continue
        accounts.append({"name": parts[0], "uid": uid, "home": parts[5], "shell": parts[6]})
    return accounts


def sudo_nopasswd_rules(files):
    """Every NOPASSWD line, with the file it came from. A comment is not a rule."""
    rules = []
    for path in files:
        for n, line in enumerate((read(path) or "").splitlines(), 1):
            stripped = line.split("#", 1)[0].strip()
            if stripped and SUDO_NOPASSWD.search(stripped):
                rules.append({"file": str(path), "line": n, "rule": stripped})
    return rules


def read_host(a):
    """Everything the host says about who can reach it. One read pass, no decisions."""
    root = Path(a.root)
    cfg = Path(a.sshd_config) if a.sshd_config else root / "etc/ssh/sshd_config"
    text = read(cfg)
    s = {"sshd_config": str(cfg), "sshd_found": text is not None,
         "sshd": sshd_settings(text, str(cfg.parent), root=str(root)),
         "matches": match_blocks(text)}

    passwd = Path(a.passwd) if a.passwd else root / "etc/passwd"
    ptext = read(passwd)
    s["passwd_file"] = str(passwd)
    s["passwd_found"] = ptext is not None
    s["accounts"] = parse_passwd(ptext)

    s["keys"] = []
    for acc in s["accounts"]:
        if NOLOGIN.search(acc["shell"] or ""):
            continue
        home = acc["home"].lstrip("/")
        path = root / home / ".ssh/authorized_keys" if home else None
        ktext = read(path) if path else None
        for k in parse_authorized_keys(ktext):
            k = dict(k, account=acc["name"], file=str(path))
            k["bits"] = key_bits(k["blob"]) if k["type"] == "ssh-rsa" else None
            try:
                k["mtime"] = dt.date.fromtimestamp(Path(path).stat().st_mtime).isoformat()
            except OSError:
                k["mtime"] = ""
            s["keys"].append(k)

    files = []
    main = Path(a.sudoers) if a.sudoers else root / "etc/sudoers"
    if read(main) is not None:
        files.append(main)
    sdir = Path(a.sudoers_dir) if a.sudoers_dir else root / "etc/sudoers.d"
    files += sorted(p for p in sdir.glob("*") if p.is_file()) if sdir.is_dir() else []
    s["sudoers_files"] = [str(p) for p in files]
    s["nopasswd"] = sudo_nopasswd_rules(files)
    return s


def collect(s, rep, a):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    weak = [w.lower() for w in (a.weak_algorithm or list(WEAK_ALGORITHMS))]
    allowed = set(a.allow_user or [])
    sshd, found = s["sshd"], s["sshd_found"]

    if not found:
        rep.add("INFO", "ssh.root-login", f"no sshd configuration at {s['sshd_config']}, "
                                          "so every ssh check is unmeasured on this host")
    else:
        root_login = " ".join(sshd.get("permitrootlogin", ["prohibit-password"])).lower()
        if root_login == "no":
            rep.add("PASS", "ssh.root-login", "direct root login is closed", measure=0)
        else:
            level = "FAIL" if root_login == "yes" else "WARN"
            rep.add(level, "ssh.root-login", f"PermitRootLogin is {root_login}, so root is reachable "
                                             "over ssh and the account that measures can also change",
                    data=[{"target": "sshd", "value": root_login}], measure=1,
                    by={"sshd": 1})

        # A password login is permitted by the global switch or re-enabled per group in a Match
        # block. Each place that permits one is counted, because each is a separate edit.
        permits = []
        if " ".join(sshd.get("passwordauthentication", ["yes"])).lower() == "yes":
            permits.append({"target": "PasswordAuthentication", "value": "yes"})
        if " ".join(sshd.get("kbdinteractiveauthentication", ["yes"])).lower() == "yes":
            permits.append({"target": "KbdInteractiveAuthentication", "value": "yes"})
        for condition, key, value in s["matches"]:
            if key in ("passwordauthentication", "kbdinteractiveauthentication") and value == "yes":
                permits.append({"target": f"Match {condition}", "value": key})
        if permits:
            rep.add("FAIL", "ssh.password-auth",
                    f"{plural(len(permits), 'setting')} {verb(len(permits), 'permit')} a password login, so a guessed "
                    "password is a way in beside every key",
                    data=permits, measure=len(permits),
                    by={p["target"]: 1 for p in permits})
        else:
            rep.add("PASS", "ssh.password-auth", "only keys are accepted", measure=0)

        offered = []
        for keyword in ("ciphers", "kexalgorithms", "macs", "hostkeyalgorithms",
                        "pubkeyacceptedalgorithms", "pubkeyacceptedkeytypes"):
            for value in sshd.get(keyword, []):
                for name in value.split(","):
                    name = name.lstrip("+-^").strip().lower()
                    if name in weak:
                        offered.append({"target": keyword, "value": name})
        if offered:
            rep.add("WARN", "ssh.weak-crypto",
                    f"{plural(len(offered), 'offered algorithm')} {verb(len(offered), 'rest')} on SHA-1, a 64-bit block "
                    "cipher, or a key type OpenSSH no longer offers by default",
                    data=offered, measure=len(offered),
                    by=count_by(offered, "target"))
        else:
            rep.add("PASS", "ssh.weak-crypto", "no algorithm from the weak list is offered", measure=0)

        missing = []
        if not (sshd.get("allowusers") or sshd.get("allowgroups")):
            missing.append({"target": "allow-list", "value": "no AllowUsers or AllowGroups"})
        tries = first_int(sshd.get("maxauthtries"))
        if a.max_auth_tries and (tries is None or tries > a.max_auth_tries):
            missing.append({"target": "max-auth-tries", "value": f"{tries if tries is not None else 'default'} "
                                                                 f"over the bar of {a.max_auth_tries}"})
        if first_int(sshd.get("logingracetime")) is None:
            missing.append({"target": "login-grace-time", "value": "left at the default"})
        if not sshd.get("maxstartups") and not sshd.get("persourcemaxstartups"):
            missing.append({"target": "max-startups", "value": "no per-source limit"})
        if missing:
            rep.add("WARN", "ssh.no-limit",
                    f"{plural(len(missing), 'limit')} of {len(LIMITS)} in front of sshd {verb(len(missing), 'are', 'is')} not set, "
                    "so an attempt costs an attacker nothing",
                    data=missing, measure=len(missing),
                    by={m["target"]: 1 for m in missing})
        else:
            rep.add("PASS", "ssh.no-limit", "every limit in front of sshd is set", measure=0)

    keys = s["keys"]
    if not s["passwd_found"]:
        rep.add("INFO", "key.orphan", f"no account list at {s['passwd_file']}, "
                                      "so keys and accounts are unmeasured on this host")
    else:
        if allowed:
            orphans = [k for k in keys if k["account"] not in allowed]
            if orphans:
                rep.add("FAIL", "key.orphan",
                        f"{plural(len(orphans), 'key')} {verb(len(orphans), 'sit')} on an account the standards do not name, "
                        "so nobody owns the way in",
                        data=[key_row(k) for k in orphans], measure=len(orphans),
                        by=count_by([key_row(k) for k in orphans], "target"))
            else:
                rep.add("PASS", "key.orphan", "every key sits on a named account", measure=0)
        else:
            rep.add("INFO", "key.orphan", "no allowed accounts are recorded, so an orphan key "
                                          "cannot be told from a wanted one")

        if a.key_rotation:
            old = [k for k in keys if k["mtime"] and k["mtime"] < a.key_rotation]
            if old:
                rep.add("WARN", "key.past-rotation",
                        f"{plural(len(old), 'key')} {verb(len(old), 'sit')} in a file last written before "
                        f"{a.key_rotation}, the rotation date the profile sets",
                        data=[key_row(k) for k in old], measure=len(old),
                        by=count_by([key_row(k) for k in old], "target"))
            else:
                rep.add("PASS", "key.past-rotation", "every key file was written after the "
                                                     "rotation date", measure=0)
        else:
            rep.add("INFO", "key.past-rotation", "no rotation date is recorded, so this check is off")

        weak_keys = [k for k in keys
                     if k["type"] in WEAK_KEY_TYPES
                     or (a.min_key_bits and k["bits"] is not None and k["bits"] < a.min_key_bits)]
        if weak_keys:
            rep.add("FAIL", "key.weak",
                    f"{plural(len(weak_keys), 'key')} {verb(len(weak_keys), 'use')} a retired type or {verb(len(weak_keys), 'fall')} under "
                    f"{a.min_key_bits or 'the bar'} bits",
                    data=[key_row(k) for k in weak_keys], measure=len(weak_keys),
                    by=count_by([key_row(k) for k in weak_keys], "target"))
        else:
            rep.add("PASS", "key.weak", "no key uses a retired type or falls under the bar", measure=0)

        by_blob = {}
        for k in keys:
            by_blob.setdefault(k["blob"], []).append(k["account"])
        shared = {b: sorted(set(accs)) for b, accs in by_blob.items() if len(set(accs)) > 1}
        if shared:
            rows = [{"target": ", ".join(accs), "value": f"one key on {len(accs)} accounts"}
                    for accs in shared.values()]
            total = sum(len(accs) for accs in shared.values())
            rep.add("WARN", "key.duplicate",
                    f"{plural(total, 'account')} {verb(total, 'share')} a key, so revoking one person's access "
                    "takes access from everyone who holds it",
                    data=rows, measure=total,
                    by={r["target"]: len(r["target"].split(", ")) for r in rows})
        else:
            rep.add("PASS", "key.duplicate", "no key is shared between accounts", measure=0)

        listed = [acc for acc in s["accounts"]
                  if not NOLOGIN.search(acc["shell"] or "") and acc["name"] not in allowed]
        if allowed and listed:
            rep.add("WARN", "user.unlisted",
                    f"{plural(len(listed), 'account')} {verb(len(listed), 'carry', 'carries')} a login shell and the standards do not "
                    "name them",
                    data=[{"target": acc["name"], "value": acc["shell"]} for acc in listed],
                    measure=len(listed), by={acc["name"]: 1 for acc in listed})
        elif allowed:
            rep.add("PASS", "user.unlisted", "every account with a login shell is named", measure=0)

    paths = list(a.path or [])
    missing_paths = max(0, a.paths_bar - len(paths))
    if missing_paths:
        rep.add("FAIL", "access.single-path",
                f"{plural(len(paths), 'way')} in {verb(len(paths), 'are', 'is')} recorded and the bar is {a.paths_bar}, so a "
                "change to access has nothing to fall back on",
                data=[{"target": p, "value": "recorded"} for p in paths],
                measure=missing_paths, by={"host": missing_paths})
    else:
        rep.add("PASS", "access.single-path",
                f"{plural(len(paths), 'independent way')} in {verb(len(paths), 'are', 'is')} recorded", measure=0)

    permitted = set(a.allow_sudo_command or [])
    rules = [r for r in s["nopasswd"]
             if not any(cmd in r["rule"] for cmd in permitted)]
    if rules:
        rep.add("WARN", "sudo.nopasswd",
                f"{plural(len(rules), 'sudo rule')} {verb(len(rules), 'run')} without a password and {verb(len(rules), 'name')} a command the "
                "fixes table does not",
                data=[{"target": f"{Path(r['file']).name}:{r['line']}", "value": r["rule"][:60]}
                      for r in rules], measure=len(rules),
                by={f"{Path(r['file']).name}:{r['line']}": 1 for r in rules})
    elif s["sudoers_files"]:
        rep.add("PASS", "sudo.nopasswd", "every passwordless sudo rule is one the fixes table names",
                measure=0)
    else:
        rep.add("INFO", "sudo.nopasswd", "no sudoers file was readable, so sudo is unmeasured")
    return rep


def first_int(values):
    """The first value of a keyword as an integer, or None when it is absent or not a number."""
    for v in values or []:
        try:
            return int(v)
        except ValueError:
            return None
    return None


def key_row(k):
    comment = k["comment"] or "no comment"
    size = f", {k['bits']} bits" if k.get("bits") else ""
    return {"target": k["account"], "value": f"{k['type']}{size}, {comment}"}


def count_by(rows, field):
    out = {}
    for r in rows:
        out[r[field]] = out.get(r[field], 0) + 1
    return out


def cell(value):
    """A finding's value as one short string; a list becomes its members, a flag becomes nothing."""
    if value is True:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(x) for x in value)
    return str(value)


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 key(s)"."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one key sits, two keys sit."""
    return (one or form + "s") if n == 1 else form


def cost(item):
    """The cost of a finding as one number and one unit, the column the eye lands on."""
    m = item.get("measure") or {}
    value = m.get("value")
    if value is None:
        return ""
    word = ROW_WORD.get(item["id"], ("finding", "findings"))
    return plural(value, *word)


def block(rows, indent="      "):
    """Name and value in two aligned columns, so the targets can be compared by eye."""
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


def detail(item):
    return [(str(d.get("target", "")), cell(d.get("value")) or "yes") for d in item["data"][:5]]


ID_WIDTH = 28
# The namespaces gate 2 covers (decisions/0016): a change under one of these needs two proved
# ways in, a backup copy, and a rollback timer before it runs. references/risk-classes.md.
GATE_PREFIXES = ("ssh.", "key.", "fw.", "sudo.", "user.")


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


def gate_line(ids):
    """The dimmed gate line under `next`, naming only the namespaces gate 2 covers among `ids`."""
    hit = sorted({p + "*" for p in GATE_PREFIXES for i in ids if i.startswith(p)})
    return paint("      gate: " + ", ".join(hit) + " in the fixes table of jorekai-ops:ops",
                "dim") if hit else None


def text_report(s, rep, target, standards):
    """The console report: what was measured, what needs a decision, what is only a note."""
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    findings = [i for i in ranked if i["level"] in ("FAIL", "WARN")]
    notes = [i for i in ranked if i["level"] == "INFO"]
    passed = [i for i in ranked if i["level"] == "PASS"]
    fails = sum(1 for i in findings if i["level"] == "FAIL")
    out = [paint(f"access  {target}  {plural(len(s['accounts']), 'account')}, "
                 f"{plural(len(s['keys']), 'key')}", "head"),
           f"measured against  {standards}", "",
           bar(fails, len(findings) - fails, len(notes), len(passed))]
    for i in findings + notes:
        out += ["", finding_line(i), f"      {i['message']}"]
        out += block(detail(i))
        if len(i["data"]) > 5:
            out.append(paint(f"      +{len(i['data']) - 5} more in the JSON", "dim"))
    if passed:
        out += [""] + wrapped("passed", [i["id"] for i in passed])
    if any(i["id"] == "access.single-path" for i in findings):
        out += ["", paint("next", "head") + "  close access.single-path before anything else, because "
                    "every other fix here needs a second way in, then look each id up in the fixes "
                    "table of jorekai-ops:ops for the fix per control plane and the risk class"]
    elif findings:
        out += ["", paint("next", "head") + "  take the findings in ladder order and look each id up in the fixes table "
                    "of jorekai-ops:ops for the fix per control plane and the risk class"]
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    if findings:
        g = gate_line([i["id"] for i in findings])
        if g:
            out.append(g)
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="/", help="filesystem root every default path is read under")
    ap.add_argument("--sshd-config", default="", help="sshd_config, or the output of sshd -T")
    ap.add_argument("--passwd", default="")
    ap.add_argument("--sudoers", default="")
    ap.add_argument("--sudoers-dir", default="")
    ap.add_argument("--allow-user", action="append", metavar="NAME",
                    help="an account the standards name; without any, key.orphan does not run")
    ap.add_argument("--allow-sudo-command", action="append", metavar="CMD",
                    help="a command a passwordless sudo rule may name")
    ap.add_argument("--min-key-bits", type=int, default=0, help="0 turns the key size check off")
    ap.add_argument("--key-rotation", default="", metavar="YYYY-MM-DD",
                    help="a key file older than this date is past its rotation")
    ap.add_argument("--path", action="append", metavar="NAME",
                    help="one recorded independent way in; repeat it")
    ap.add_argument("--paths-bar", type=int, default=2, help="how many ways in the host must have")
    ap.add_argument("--weak-algorithm", action="append", metavar="NAME",
                    help="replaces the built-in weak list when given")
    ap.add_argument("--max-auth-tries", type=int, default=0, help="0 turns that limit check off")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    s = read_host(a)
    rep = collect(s, Report(), a)
    target = a.root if a.root != "/" else "this host"
    if a.json:
        print(json.dumps({"tool": "access", "target": target, "generated": today.isoformat(),
                          "counts": rep.counts(), "accounts": s["accounts"], "keys": s["keys"],
                          "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        standards = (f"{plural(a.paths_bar, 'way')} in"
                     + (f" · keys over {a.min_key_bits} bits" if a.min_key_bits else "")
                     + (f" · rotated since {a.key_rotation}" if a.key_rotation else "")
                     + (f" · {plural(len(a.allow_user), 'named account')}" if a.allow_user else ""))
        print(text_report(s, rep, target, standards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
