#!/usr/bin/env python3
"""What this host offers the network, and what stands in front of it.

Usage:
  exposure.py [--expected-port SPEC ...] [--panel-port SPEC ...] [--ss-file FILE]
              [--fw-kind KIND] [--fw-file FILE] [--cert PATH ...] [--cert-dir DIR]
              [--enddate-dir DIR] [--tls-expiring-days N] [--intrusion-unit UNIT ...]
              [--show-dir DIR] [--root DIR] [--now YYYY-MM-DDTHH:MM:SS] [--json]
  exposure.py --explain RANK|ID       the chain behind one finding
  exposure.py --measures              the unit every check id is measured in

SPEC is `PORT[/tcp|/udp]`, one per port the standards say belongs here. KIND is one of `nft`,
`ufw`, `firewalld`, `none`, or `auto`, which asks the host in that order. `scaffold.py --flags`
in the setup skill prints every argument from the workspace.

Listening sockets come from `ss -H -ltunp`, or from `--ss-file` holding its output, which is what
makes the whole pass testable without a network stack. Certificate dates come from
`openssl x509 -noout -enddate -dateopt iso_8601`, or from `--enddate-dir` holding one
`<name>.enddate` file per certificate. Reads only: no port is closed, no rule is written.

A change under `fw.*`, `port.*` or `panel.*` passes gate 2 first, because closing a port or
restricting a panel by hand can close the connection reading this report, exactly as a firewall
rule can. See references/risk-classes.md beside the router.

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
MEASURES = {"port.world-open": "count", "port.unexpected": "count", "panel.exposed": "count",
            "fw.disabled": "count", "fw.rule-orphan": "count", "tls.expired": "count",
            "tls.expiring": "count", "intrusion.off": "count"}
# What the number in a row counts, per check id.
ROW_WORD = {"port.world-open": ("port open to anywhere", "ports open to anywhere"),
            "port.unexpected": ("port nobody named", "ports nobody named"),
            "panel.exposed": ("panel port open to anywhere", "panel ports open to anywhere"),
            "fw.disabled": ("host with nothing filtering", "hosts with nothing filtering"),
            "fw.rule-orphan": ("rule for a port nothing serves", "rules for ports nothing serves"),
            "tls.expired": ("certificate past its date", "certificates past their date"),
            "tls.expiring": ("certificate inside the window", "certificates inside the window"),
            "intrusion.off": ("unit that is not watching", "units that are not watching")}
# An address a socket binds to when it takes connections from anywhere, and one that only the
# host itself reaches. Anything else is one address on one interface.
ANYWHERE = {"0.0.0.0", "::", "*", "[::]", "0000:0000:0000:0000:0000:0000:0000:0000"}
LOOPBACK = ("127.", "::1", "[::1]", "localhost")
# `ss` prints an address and its port as one token, and the shape holds for both families:
# `0.0.0.0:22`, `[::]:22`, `*:111`. The first such token on a line is the local socket, the
# second is its peer. The column order itself is not documented, so this reads tokens.
SOCKET = re.compile(r"^(?P<addr>\[[^\]]*\]|[^\s]*?):(?P<port>\d+|\*)$")
PORT_SPEC = re.compile(r"^(?P<port>\d+)(?:/(?P<proto>tcp|udp))?$", re.I)
UFW_ACTIVE = re.compile(r"^Status:\s*active", re.I | re.M)
# The To column carries a port or a range, the Action column says what happens to it. Only what
# comes in counts: `ALLOW OUT` and `ALLOW FWD` are about traffic this host sends or forwards, and
# reading them as open ports invents rules nobody wrote.
UFW_RULE = re.compile(r"^\s*(?P<port>\d+(?::\d+)?)(?:/(?P<proto>tcp|udp))?\s+"
                      r"(?P<action>ALLOW|LIMIT)(?:\s+(?P<direction>IN|OUT|FWD))?\b", re.I | re.M)
FIREWALLD_PORT = re.compile(r"^\s*ports:\s*(?P<ports>.*)$", re.I | re.M)
FIREWALLD_SERVICE = re.compile(r"^\s*services:\s*(?P<services>.*)$", re.I | re.M)
NFT_INPUT = re.compile(r"type\s+filter\s+hook\s+input\b[^\n]*policy\s+(?P<policy>\w+)")
# One rule, read whole: the protocol in front of `dport`, the ports behind it as a number, a set,
# or a range, and the verdict at the end. A rule that drops a port is not a rule that opens it.
NFT_RULE = re.compile(r"\b(?P<proto>tcp|udp)\s+dport\s+(?:\{\s*(?P<set>[^}]*)\}|"
                      r"(?P<one>\d+(?:-\d+)?))(?P<rest>[^\n]*)")
RANGE = re.compile(r"^\d+[-:]\d+$")
ISO_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\s*(?P<zone>Z|[+-]\d{2}:?\d{2})?")


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, cid, message, data=None, measure=None, by=None):
        """One finding. `measure` is what it costs now, in the unit MEASURES gives the id, and
        `by` is the same cost per target, so a log row about one port grades against it."""
        unit = MEASURES.get(cid)
        self.items.append({"id": cid, "level": level, "message": message, "data": data or [],
                           "measure": {"value": measure, "unit": unit, "by": by or {}}
                           if unit and measure is not None else None})

    def counts(self):
        c = {}
        for i in self.items:
            c[i["level"]] = c.get(i["level"], 0) + 1
        return c


def parse_port(text):
    """`443/tcp` as (443, "tcp"). A spec without a protocol names the port on both."""
    m = PORT_SPEC.match(text.strip())
    if not m:
        sys.exit(f"not a port: {text!r}. Expected PORT or PORT/tcp or PORT/udp")
    return int(m.group("port")), (m.group("proto") or "").lower()


def wanted(port, proto, specs):
    """Whether a port the host serves stands in the list the standards give."""
    return any(p == port and (not sp or sp == proto) for p, sp in specs)


def run_command(argv, timeout=10):
    """One command's completed process, or `None` when its binary is not installed or the call
    times out. The caller reads `.returncode` and `.stdout` itself, because a status query can
    answer accurately through a non-zero exit (`firewall-cmd --state` says `not running` that
    way), and that answer is not the same as the binary being absent."""
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def output_of(argv, timeout=10):
    """The stdout of a command that only means something on a clean exit, or `None` otherwise."""
    r = run_command(argv, timeout=timeout)
    return r.stdout if r and r.returncode == 0 else None


REFUSED_WORDS = ("permission denied", "operation not permitted", "not authorized",
                  "access denied", "authentication required", "need to be root",
                  "must be root", "run as root")


def refused(text):
    """Whether a failed command's own wording says privilege was the reason, not absence.

    A judgement, not a documented interface (references/sources.md): the wording a refused
    firewall command prints is not standardised across `nft`, `ufw`, and `firewall-cmd`.
    """
    low = text.lower()
    return any(w in low for w in REFUSED_WORDS)


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def sockets(a):
    """Every listening socket as {proto, address, port}, from the host or from a captured file."""
    text = read(a.ss_file) if a.ss_file else output_of(["ss", "-H", "-ltunp"])
    if text is None:
        return None
    out = []
    for line in text.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        found = [m for m in (SOCKET.match(t) for t in tokens) if m]
        if not found:
            continue
        local = found[0]
        port = local.group("port")
        if not port.isdigit():
            continue
        proto = tokens[0].lower() if tokens[0].lower() in ("tcp", "udp") else ""
        out.append({"proto": proto, "address": local.group("addr") or "*", "port": int(port),
                    "process": tokens[-1] if tokens[-1].startswith("users:") else ""})
    return out


def reach(address):
    """Where a bound address takes connections from: `anywhere`, `here`, or one interface."""
    if address in ANYWHERE or address == "":
        return "anywhere"
    if address.startswith(LOOPBACK):
        return "here"
    return "an interface"


def status_text(kind):
    """What a firewall says about itself: the text, `None` when its binary is not installed, or
    `"refused"` when it ran and its own wording says privilege was the reason.

    A firewalld host answers in two halves: `--state` says whether the daemon is doing anything
    at all, `--list-all` says what it lets in. Reading only the second one would call a stopped
    daemon a firewall, because a zone still prints its rules when nothing enforces them. `--state`
    also answers `not running` through a non-zero exit, so a missing binary and a real "not
    running" answer are told apart by whether the command ran at all, never by its exit code alone.
    """
    if kind == "nft":
        r = run_command(["nft", "list", "ruleset"])
    elif kind == "ufw":
        r = run_command(["ufw", "status", "verbose"])
    elif kind == "firewalld":
        r = run_command(["firewall-cmd", "--state"])
        if r is None:
            return None
        if r.returncode != 0 and refused(r.stdout + r.stderr):
            return "refused"
        state = r.stdout.strip() or "not running"
        rules_r = run_command(["firewall-cmd", "--list-all"])
        rules = rules_r.stdout if rules_r and rules_r.returncode == 0 else ""
        return state + "\n" + rules
    else:
        return None
    if r is None:
        return None
    if r.returncode != 0 and refused(r.stdout + r.stderr):
        return "refused"
    return r.stdout if r.returncode == 0 else None


def firewall(a):
    """What filters this host: the kind, whether it is filtering, and the ports it lets in.

    The status text comes from the host or from `--fw-file`. Each kind is read on its own terms,
    and a kind this pass does not read says so instead of reporting a clean firewall.
    """
    kind, text = a.fw_kind, None
    if a.fw_file:
        if kind == "auto":
            sys.exit("--fw-file needs --fw-kind: a status text does not say which firewall wrote it")
        text = read(a.fw_file)
    elif kind == "auto":
        for candidate in ("nft", "ufw", "firewalld"):
            text = status_text(candidate)
            if text is not None:
                kind = candidate
                break
        else:
            kind = "none"
    elif kind != "none":
        text = status_text(kind)
    if kind == "none" or text is None or text == "refused":
        # A refusal is not an absence: the tool answered, and its wording said privilege was the
        # reason. Reading it as "none" would report a firewall gone that may still be standing
        # (decisions/0030): the row stays unread, with a note that says why.
        return {"kind": kind, "filtering": False, "ports": [], "read": False,
                "refused": text == "refused", "ranges": [], "services": [], "default_open": ""}
    ports, ranges, services, filtering, default_open = [], [], [], False, ""

    if kind == "ufw":
        filtering = bool(UFW_ACTIVE.search(text))
        for m in UFW_RULE.finditer(text):
            if (m.group("direction") or "IN").upper() != "IN":
                continue
            proto = (m.group("proto") or "").lower()
            if RANGE.match(m.group("port")):
                ranges.append(m.group("port") + (f"/{proto}" if proto else ""))
                continue
            ports.append((int(m.group("port")), proto))
    elif kind == "firewalld":
        filtering = "not running" not in text.lower()
        if re.search(r"^\s*target:\s*ACCEPT", text, re.I | re.M):
            default_open = "target ACCEPT"
        for m in FIREWALLD_PORT.finditer(text):
            for token in m.group("ports").split():
                port, _, proto = token.partition("/")
                if RANGE.match(port):
                    ranges.append(token)
                elif port.isdigit():
                    ports.append((int(port), proto.lower()))
        for m in FIREWALLD_SERVICE.finditer(text):
            services += m.group("services").split()
    elif kind == "nft":
        m = NFT_INPUT.search(text)
        drops = bool(re.search(r"\b(drop|reject)\b", text))
        # A chain that accepts by default and drops named traffic still filters. It filters less
        # than a chain that drops by default, and the note beside the finding says which it is.
        filtering = bool(m) and (m.group("policy").lower() != "accept" or drops)
        if m and m.group("policy").lower() == "accept" and drops:
            default_open = "policy accept"
        for hit in NFT_RULE.finditer(text):
            if "accept" not in hit.group("rest").lower():
                continue
            proto = hit.group("proto").lower()
            raw = hit.group("set") or hit.group("one") or ""
            for token in raw.replace(",", " ").split():
                token = token.strip()
                if RANGE.match(token):
                    ranges.append(f"{token}/{proto}")
                elif token.isdigit():
                    ports.append((int(token), proto))
    return {"kind": kind, "filtering": filtering, "ports": sorted(set(ports)), "read": True,
            "refused": False, "ranges": sorted(set(ranges)), "services": services,
            "default_open": default_open}


def enddate(path, a):
    """The notAfter date of a certificate, as a naive datetime, or None."""
    if a.enddate_dir:
        text = read(Path(a.enddate_dir) / (Path(path).stem + ".enddate"))
    else:
        text = output_of(["openssl", "x509", "-noout", "-enddate", "-dateopt", "iso_8601",
                         "-in", str(path)])
    m = ISO_DATE.search(text or "")
    if not m:
        return None
    try:
        stamp = dt.datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}")
    except ValueError:
        return None
    # A certificate date is in UTC and the host is usually not, so both sides of the comparison
    # carry a zone. Reading the date as local time moves it by the offset, which decides the
    # answer for every certificate inside one day of its end.
    zone = (m.group("zone") or "Z").replace(":", "")
    if zone == "Z":
        return stamp.replace(tzinfo=dt.timezone.utc)
    offset = dt.timedelta(hours=int(zone[1:3]), minutes=int(zone[3:5]))
    return stamp.replace(tzinfo=dt.timezone(-offset if zone[0] == "-" else offset))


def certificates(a):
    """Every certificate the workspace names, with the date it stops being valid."""
    paths = [Path(a.root) / str(c).lstrip("/") for c in a.cert or []]
    if a.cert_dir:
        d = Path(a.root) / str(a.cert_dir).lstrip("/")
        if d.is_dir():
            paths += [p for p in sorted(d.rglob("*")) if p.suffix in (".pem", ".crt", ".cert")]
    return [{"path": str(p), "exists": p.exists(), "until": enddate(p, a) if p.exists() else None}
            for p in paths]


def show(unit, show_dir, timeout=10):
    """`systemctl show <unit>` as {Key: Value}, from a captured file when one is given."""
    if show_dir:
        text = read(Path(show_dir) / f"{unit}.show")
    else:
        text = output_of(["systemctl", "show", unit], timeout=timeout)
    if text is None:
        return None
    out = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out.setdefault(key.strip(), value.strip())
    return out


def collect(open_ports, fw, certs, watchers, rep, a, now):
    """Every check, in ladder order. A finding is a fact; the fixes table decides what happens."""
    expected = [parse_port(p) for p in a.expected_port or []]
    panel = [parse_port(p) for p in a.panel_port or []]
    read_sockets = open_ports is not None
    if not read_sockets:
        rep.add("INFO", "port.world-open",
                "no socket list, so nothing here says what this host offers the network")
        open_ports = []
    elif not expected:
        rep.add("INFO", "port.world-open",
                f"{plural(len(open_ports), 'socket')} {verb(len(open_ports), 'listen')} here and the workspace names no "
                "expected port, so every one of them is a finding")
    listening = {(s["port"], s["proto"]) for s in open_ports}

    # An empty list that was actually read is an answer: it says nothing listens, and the zero it
    # writes is what settles a row about a port that was closed.
    if read_sockets:
        # A panel port has its own finding one line down, and no port is counted twice.
        outside = [s for s in open_ports
                   if reach(s["address"]) == "anywhere" and not wanted(s["port"], s["proto"], expected)
                   and not wanted(s["port"], s["proto"], panel)]
        if outside:
            by = {}
            for s in outside:
                by[f"{s['port']}/{s['proto'] or 'any'}"] = 1
            rep.add("FAIL", "port.world-open",
                    f"{plural(len(by), 'port')} {verb(len(by), 'take')} connections from anywhere and the standards name "
                    "none of them",
                    data=[{"target": f"{s['port']}/{s['proto'] or 'any'}", "value": s["address"]}
                          for s in outside],
                    measure=len(by), by=by)
        else:
            rep.add("PASS", "port.world-open", "every port open to anywhere is one the standards name",
                    measure=0)

        local = [s for s in open_ports
                 if reach(s["address"]) != "anywhere" and not wanted(s["port"], s["proto"], expected)
                 and not wanted(s["port"], s["proto"], panel)]
        if local:
            by = {}
            for s in local:
                by[f"{s['port']}/{s['proto'] or 'any'}"] = 1
            rep.add("WARN", "port.unexpected",
                    f"{plural(len(by), 'port')} nobody named {verb(len(by), 'listen')} on one address of this host",
                    data=[{"target": f"{s['port']}/{s['proto'] or 'any'}", "value": s["address"]}
                          for s in local],
                    measure=len(by), by=by)
        else:
            rep.add("PASS", "port.unexpected", "every port that listens is one the standards name",
                    measure=0)

    if panel and read_sockets:
        exposed = [s for s in open_ports
                   if reach(s["address"]) == "anywhere" and wanted(s["port"], s["proto"], panel)]
        if exposed:
            by = {str(s["port"]): 1 for s in exposed}
            rep.add("FAIL", "panel.exposed",
                    f"{plural(len(by), 'panel port')} {verb(len(by), 'take')} connections from anywhere, so the surface "
                    "that changes this host is on the open network",
                    data=[{"target": str(s["port"]), "value": s["address"]} for s in exposed],
                    measure=len(by), by=by)
        else:
            rep.add("PASS", "panel.exposed", "no panel port takes connections from anywhere", measure=0)

    if fw["kind"] == "none":
        rep.add("FAIL", "fw.disabled",
                "nothing on this host answers as a firewall, so every port that listens is reachable "
                "by whatever can route to it",
                data=[{"target": "firewall", "value": "none"}], measure=1, by={"firewall": 1})
    elif not fw["read"]:
        # Not reading a firewall is not the same as reading one that filters nothing. A measure
        # here would settle a row with a number nobody took. A refusal is a stronger, honester
        # answer than a silent one: the tool exists and said privilege was the reason (decisions/0030).
        if fw.get("refused"):
            rep.add("INFO", "fw.disabled",
                    f"the {fw['kind']} firewall refused to answer without more privilege, so this "
                    "pass cannot say whether it filters",
                    data=[{"target": fw["kind"], "value": "refused"}])
        else:
            rep.add("INFO", "fw.disabled",
                    f"the {fw['kind']} firewall did not answer, so this pass cannot say whether it filters",
                    data=[{"target": fw["kind"], "value": "no answer"}])
    elif not fw["filtering"]:
        rep.add("FAIL", "fw.disabled",
                f"the {fw['kind']} firewall on this host is not filtering, so the rules it holds "
                "do nothing",
                data=[{"target": fw["kind"], "value": "not filtering"}], measure=1,
                by={fw["kind"]: 1})
    else:
        rep.add("PASS", "fw.disabled", f"the firewall is filtering ({fw['kind']})", measure=0)
    if fw.get("default_open"):
        rep.add("INFO", "fw.disabled",
                f"the {fw['kind']} firewall takes everything it has no rule for, so what it filters "
                "is the list of rules and not the default",
                data=[{"target": fw["kind"], "value": fw["default_open"]}])

    if fw["filtering"] and fw["ports"]:
        orphans = [(port, proto) for port, proto in fw["ports"]
                   if not any(port == p and (not proto or not sp or proto == sp)
                              for p, sp in listening)]
        if orphans:
            by = {f"{port}/{proto or 'any'}": 1 for port, proto in orphans}
            rep.add("WARN", "fw.rule-orphan",
                    f"{plural(len(by), 'rule')} {verb(len(by), 'let')} a port in that nothing on this host serves",
                    data=[{"target": f"{port}/{proto or 'any'}", "value": "nothing listens"}
                          for port, proto in orphans],
                    measure=len(by), by=by)
        else:
            rep.add("PASS", "fw.rule-orphan", "every rule lets in a port something serves", measure=0)
    named = [(name, "service") for name in fw["services"]] + \
            [(r, "range") for r in fw.get("ranges", [])]
    if named:
        rep.add("INFO", "fw.rule-orphan",
                f"{plural(len(named), 'rule')} {verb(len(named), 'name')} a service or a range instead of one port, "
                "and this pass resolves neither to the ports behind it",
                data=[{"target": name, "value": what} for name, what in named])

    known = [c for c in certs if c["until"]]
    unreadable = [c for c in certs if not c["until"]]
    expired = [c for c in known if c["until"] < now]
    if expired:
        rep.add("FAIL", "tls.expired",
                f"{plural(len(expired), 'certificate')} {verb(len(expired), 'are', 'is')} past its date, so a client "
                "reaching this host is told the connection cannot be trusted",
                data=[{"target": c["path"], "value": c["until"].date().isoformat()} for c in expired],
                measure=len(expired), by={c["path"]: 1 for c in expired})
    elif known:
        rep.add("PASS", "tls.expired", "no certificate is past its date", measure=0)
    soon = [c for c in known if now <= c["until"] < now + dt.timedelta(days=a.tls_expiring_days)]
    if soon:
        rep.add("WARN", "tls.expiring",
                f"{plural(len(soon), 'certificate')} {verb(len(soon), 'run')} out inside the next "
                f"{plural(a.tls_expiring_days, 'day')}",
                data=[{"target": c["path"], "value": c["until"].date().isoformat()} for c in soon],
                measure=len(soon), by={c["path"]: 1 for c in soon})
    elif known:
        rep.add("PASS", "tls.expiring", "no certificate runs out inside the window", measure=0)
    if unreadable:
        rep.add("INFO", "tls.expired",
                f"{plural(len(unreadable), 'certificate')} {verb(len(unreadable), 'carry', 'carries')} no readable date",
                data=[{"target": c["path"], "value": "no date" if c["exists"] else "not there"}
                      for c in unreadable])

    if watchers:
        off = [w for w in watchers if w["state"] != "active"]
        if off:
            rep.add("WARN", "intrusion.off",
                    f"{plural(len(off), 'unit')} that should watch failed attempts {verb(len(off), 'are', 'is')} not "
                    "running, so a host on the open network is being tried without anyone counting",
                    data=[{"target": w["unit"], "value": w["state"]} for w in off],
                    measure=len(off), by={w["unit"]: 1 for w in off})
        else:
            rep.add("PASS", "intrusion.off", "every unit that watches failed attempts is running",
                    measure=0)
    return rep


def watchers_state(a):
    """The units the workspace names as watching failed attempts, with the state each reports."""
    out = []
    for unit in a.intrusion_unit or []:
        state = show(unit, a.show_dir)
        out.append({"unit": unit,
                    "state": (state or {}).get("ActiveState", "no state")})
    return out


def verb(n, form, one=None):
    """The verb that agrees with a count. English inverts the s: one port takes, two ports take."""
    return (one or form + "s") if n == 1 else form


def plural(n, one, many=None):
    """A count and its word, so a report never prints "1 port(s)"."""
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


# The report answers the questions a person asks, in the order they ask them (decisions/0031):
# what it is and how heavy it weighs stand in the list, the rest waits behind `--explain`. A report
# that prints the whole chain for every finding is a report nobody finishes.
FIXES_FILE = Path(__file__).resolve().parents[2] / "ops" / "references" / "fixes.md"
FIX_ROW = re.compile(r"\|\s*`([a-z]+\.[a-z-]+)`\s*\|([^|]*)\|\s*`([a-z]+)`\s*\|\s*(\d+)\s*\|")
FIX_HEAD = re.compile(r"^###\s+(.+)")
FIX_PLANE = re.compile(r"^#\s*([a-z][a-z0-9-]*)\b")


def load_fixes(path=None):
    """Check id to what it means, its risk class, and the planes the table holds a fix for."""
    try:
        text = Path(path or FIXES_FILE).read_text(encoding="utf-8")
    except OSError:
        return {}
    rows, ids, fence, first = {}, [], False, False
    for line in text.splitlines():
        m = FIX_ROW.match(line)
        if m:
            rows[m.group(1)] = {"means": m.group(2).strip(), "class": m.group(3),
                                "rung": int(m.group(4)), "planes": []}
            continue
        h = FIX_HEAD.match(line)
        if h:
            ids = [i.strip(" `") for i in h.group(1).split(",")]
            continue
        if line.startswith("```"):
            fence, first = not fence, True
            continue
        # Only the first comment of a block names its control plane; the rest explain the commands.
        if fence and first and line.startswith("#"):
            first = False
            m = FIX_PLANE.match(line)
            for cid in ids if m else []:
                if cid in rows and m.group(1) not in rows[cid]["planes"]:
                    rows[cid]["planes"].append(m.group(1))
    return rows


def previous_measures(path):
    """Every measure of an earlier findings JSON, so a line can carry a direction."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {i["id"]: (i.get("measure") or {}).get("value") for i in data.get("items", [])}


def change_of(item, previous):
    """The direction since that pass: `=`, a signed number, or `new` for an id it never held."""
    now = (item.get("measure") or {}).get("value")
    if now is None:
        return "-"
    old = previous.get(item["id"])
    if old is None:
        return "new"
    return "=" if old == now else f"{now - old:+d}"


def where_of(item, width=20):
    """The first place the finding names, and how many more places the JSON holds.

    It reads the same rows the long form prints, so the column and `--explain` never disagree.
    """
    rows = detail(item)
    if not rows:
        return "-"
    more = len(item["data"]) - 1
    text = str(rows[0][0]) + (f" +{more}" if more > 0 else "")
    return text if len(text) <= width else text[:width - 2] + ".."

def ranked_findings(rep, fixes=None):
    """Findings and notes in ladder order: the rank is the address `--explain` takes.

    The rung comes from the fixes table, so one order runs through the report, the fixes table and
    `jorekai-ops:and-now`. Without that file the pass still ranks, by level and cost alone.
    """
    fixes = fixes or {}
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              fixes.get(x["id"], {}).get("rung", 9),
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    return ([i for i in ranked if i["level"] in ("FAIL", "WARN")],
            [i for i in ranked if i["level"] == "INFO"],
            [i for i in ranked if i["level"] == "PASS"])


def columns(head, rows, paints, under=None):
    """Fixed columns, padded on the plain text, painted after, so colour never moves a column."""
    under = under or {}
    widths = [max([len(h)] + [len(r[c]) for r in rows]) for c, h in enumerate(head)]
    out = [paint("  ".join(h.ljust(w) for h, w in zip(head, widths)).rstrip(), "dim")]
    indent = " " * (widths[0] + 2 + widths[1] + 2)
    for n, (row, keys) in enumerate(zip(rows, paints)):
        # The padding stays outside the escape, or a line with colour and a line without it would
        # end on a different number of spaces and the report would read differently in a pipe.
        line = "  ".join((paint(v, k) if k else v) + " " * (w - len(v))
                         for v, w, k in zip(row, widths, keys))
        out.append(line.rstrip())
        if under.get(n):
            out.append(paint(indent + under[n], "dim"))
    return out


def said(item, width=70):
    """The sentence a line with no cost carries, because a note's content is its sentence."""
    text = " ".join(item.get("message", "").split())
    return text if len(text) <= width else text[:width - 2] + ".."


def listing(findings, notes, fixes, previous):
    """One line per finding: rank, level, check, measure, change, where, class."""
    head = ["  #", "level", "check", "measure"] + (["change"] if previous is not None else []) \
        + ["where", "class"]
    rows, paints, notes_under = [], [], {}
    for n, i in enumerate(findings + notes, 1):
        level = "note" if i["level"] == "INFO" else i["level"]
        row = [f"{n:>3}", level, i["id"], cost(i) or "-"]
        keys = [None, i["level"], "id", "dim"]
        if previous is not None:
            direction = change_of(i, previous)
            row.append(direction)
            keys.append({"=": "dim", "-": "dim", "new": "WARN"}.get(direction)
                        or ("WARN" if direction.startswith("+") else "PASS"))
        row += [where_of(i), fixes.get(i["id"], {}).get("class", "-")]
        keys += ["dim", "INFO"]
        rows.append(row)
        paints.append(keys)
        # A finding without a cost has nothing in the column the eye reads, so its sentence goes
        # under it, dimmed. Every other line stays one line.
        notes_under[len(rows) - 1] = None if cost(i) else said(i)
    return columns(head, rows, paints, notes_under)


def field(label, lines, width=6, wrap=80):
    """One field of the chain: the label once, dimmed, its lines wrapped under it."""
    if not lines:
        return []
    pad = " " * (width + 2)
    flowed = []
    for line in lines:
        flowed += textwrap.wrap(line, width=wrap - len(pad), break_long_words=False,
                                break_on_hyphens=False) or [""]
    return [f"{paint(label.ljust(width), 'dim')}  {flowed[0]}"] + [pad + l for l in flowed[1:]]


def undo_line(cid, klass):
    """The way back, read from the class the id runs under (references/risk-classes.md)."""
    if cid.startswith(GATE_PREFIXES):
        return ("restore the backup copy gate 2 wrote, then prove a fresh connection "
                "before the rollback timer elapses")
    if klass == "confirm":
        return "the dry run names every path it writes, and the copy it writes first is the way back"
    if klass == "safe":
        return "the class is safe, so the change reports what it did and setting the old value again is the way back"
    if klass == "ask":
        return "the class is ask, so nothing runs from here: copy what you touch before you touch it"
    return ""


def pick(ranked, which):
    """A finding by its rank in this pass or by its check id, whichever the argument holds."""
    if which.isdigit() and 1 <= int(which) <= len(ranked):
        return ranked[int(which) - 1]
    return next((i for i in ranked if i["id"] == which), None)


def explain_report(rep, target, fixes, which, previous):
    """The chain for one finding: what, weight, means, cause, fix, undo, verify."""
    findings, notes, _ = ranked_findings(rep, fixes)
    ranked = findings + notes
    item = pick(ranked, which)
    if item is None:
        return (f"no finding called {which} in this pass. The list prints a rank per finding, "
                "and --explain takes that rank or the check id.")
    n, row = ranked.index(item) + 1, fixes.get(item["id"], {})
    klass = row.get("class", "")
    out = [f"{paint(item['id'], 'head')}  {paint(f'rank {n} of {len(ranked)}', 'dim')}  "
           f"{paint('note' if item['level'] == 'INFO' else item['level'], item['level'])}  "
           f"{paint(target, 'dim')}", ""]
    out += field("what", [item["message"]])
    out += block(detail(item), indent=" " * 8)

    weight = [cost(item) or "nothing measurable", item["level"].lower()]
    if previous is not None:
        weight.append(f"change {change_of(item, previous)}")
    if item["id"].startswith(GATE_PREFIXES):
        weight.append("gate 2 namespace")
    out += field("weight", [" · ".join(weight)])
    out += field("means", [row.get("means") or
                           "no row in the fixes table of jorekai-ops:ops, so nothing explains this id yet"])
    # A cause is printed only where the pass proved one. A finding that carries no signal carries
    # no line here, because a guessed cause costs more trust than it saves time.
    if item.get("cause"):
        out += field("cause", [item["cause"]])

    fix = [" · ".join(filter(None, [klass or "no class",
                                    "gate 2" if item["id"].startswith(GATE_PREFIXES) else "",
                                    "fixes table of jorekai-ops:ops"]))]
    if row.get("planes"):
        fix.append("the table holds a block per control plane: " + ", ".join(row["planes"]))
    out += field("fix", fix)
    out += field("undo", [undo_line(item["id"], klass)] if undo_line(item["id"], klass) else [])
    unit = MEASURES.get(item["id"], "count")
    out += field("verify", [f"{item['id']}  0 {unit}  recomputed by this pass",
                            "the verify date goes in the log row that carries the change"])
    return "\n".join(out)


# The namespaces gate 2 covers (decisions/0016, decisions/0039): a change under one of these
# needs two proved ways in, a backup copy, and a rollback timer before it runs. A port closed or a
# panel restricted by hand can take away the way in exactly as a firewall rule can, which is why
# port.* and panel.* are here too. references/risk-classes.md.
GATE_PREFIXES = ("ssh.", "key.", "fw.", "sudo.", "user.", "port.", "panel.")


def bar(fails, warns, notes, passed):
    """Four counts in one line, a zero dimmed, a count above zero in the colour of its word."""
    cells = [(fails, "FAIL", "FAIL"), (warns, "WARN", "WARN"),
             (notes, plural(notes, "note").split()[1], "INFO"),
             (passed, "passed", "PASS")]
    return " · ".join(paint(f"{n} {word}", key if n else "dim") for n, word, key in cells)


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


def text_report(open_ports, fw, rep, target, standards, fixes=None, previous=None):
    """The console report: what was measured, then one line per finding, then the next step."""
    fixes = {} if fixes is None else fixes
    findings, notes, passed = ranked_findings(rep, fixes)
    fails = sum(1 for i in findings if i["level"] == "FAIL")
    out = [paint(f"exposure  {target}  {plural(len(open_ports or []), 'listening socket')}, "
                 f"firewall {fw['kind']}", "head"),
           f"measured against  {standards}", "",
           bar(fails, len(findings) - fails, len(notes), len(passed))]
    if findings or notes:
        out += [""] + listing(findings, notes, fixes, previous)
    if passed:
        out += [""] + wrapped("passed", sorted({i["id"] for i in passed}))
    if findings:
        out += ["", paint("next", "head") + "  close what is open to anywhere before what is only "
                "untidy, and pass gate 2 before a rule changes, then `--explain RANK` for the chain "
                "behind a line"]
        g = gate_line([i["id"] for i in findings])
        if g:
            out.append(g)
    else:
        out += ["", paint("next", "head") + "  nothing to act on, measure again when this audit ages out"]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--expected-port", action="append", metavar="SPEC",
                    help="PORT[/tcp|/udp] the standards say belongs on this host")
    ap.add_argument("--panel-port", action="append", metavar="SPEC",
                    help="PORT[/tcp|/udp] the control plane answers on")
    ap.add_argument("--ss-file", default="", metavar="FILE",
                    help="captured `ss -H -ltunp` output instead of the running host")
    ap.add_argument("--fw-kind", default="auto", choices=("auto", "nft", "ufw", "firewalld", "none"))
    ap.add_argument("--fw-file", default="", metavar="FILE",
                    help="captured firewall status instead of the running host")
    ap.add_argument("--cert", action="append", metavar="PATH")
    ap.add_argument("--cert-dir", default="", metavar="DIR")
    ap.add_argument("--enddate-dir", default="", metavar="DIR",
                    help="captured end dates, one <name>.enddate file per certificate")
    ap.add_argument("--tls-expiring-days", type=int, default=21,
                    help="how close a certificate may come to its date")
    ap.add_argument("--intrusion-unit", action="append", metavar="UNIT",
                    help="a unit that watches failed attempts")
    ap.add_argument("--show-dir", default="", metavar="DIR",
                    help="captured `systemctl show` output, one <unit>.show file per unit")
    ap.add_argument("--root", default="/", help="filesystem root every path is read under")
    ap.add_argument("--explain", default="", metavar="RANK|ID",
                    help="the chain behind one finding: what, weight, means, fix, undo, verify")
    ap.add_argument("--previous", default="", metavar="FILE",
                    help="an earlier findings JSON, which adds the change column")
    ap.add_argument("--fixes", default="", metavar="FILE",
                    help="the fixes table to read the class and the meaning from")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", default=None, metavar="YYYY-MM-DDTHH:MM:SS", help="for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    # `--now` is read as a time on this host, the way a person reads a clock, and carries the
    # host's zone from there. Without it the pass takes the moment it runs.
    now = (dt.datetime.fromisoformat(a.now).astimezone() if a.now
           else dt.datetime.now(dt.timezone.utc))
    open_ports = sockets(a)
    fw = firewall(a)
    certs = certificates(a)
    watchers = watchers_state(a)
    rep = collect(open_ports, fw, certs, watchers, Report(), a, now)
    target = a.root if a.root != "/" else "this host"
    if a.json:
        print(json.dumps({"tool": "exposure", "target": target,
                          "generated": now.date().isoformat(), "counts": rep.counts(),
                          "sockets": open_ports or [], "firewall": fw,
                          "certificates": [{"path": c["path"], "exists": c["exists"],
                                            "until": c["until"].isoformat() if c["until"] else ""}
                                           for c in certs],
                          "watchers": watchers, "items": rep.items}, indent=2, ensure_ascii=False))
    elif a.explain:
        print(explain_report(rep, target, load_fixes(a.fixes or None), a.explain,
                             previous_measures(a.previous) if a.previous else None))
    else:
        standards = (f"{plural(len(a.expected_port or []), 'expected port')}"
                     f" · a certificate more than {plural(a.tls_expiring_days, 'day')} from its date"
                     f" · {plural(len(a.intrusion_unit or []), 'unit')} watching failed attempts")
        print(text_report(open_ports, fw, rep, target, standards, load_fixes(a.fixes or None),
                          previous_measures(a.previous) if a.previous else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
