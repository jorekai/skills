#!/usr/bin/env python3
"""What this host offers the network, and what stands in front of it.

Usage:
  exposure.py [--expected-port SPEC ...] [--panel-port SPEC ...] [--ss-file FILE]
              [--fw-kind KIND] [--fw-file FILE] [--cert PATH ...] [--cert-dir DIR]
              [--enddate-dir DIR] [--tls-expiring-days N] [--intrusion-unit UNIT ...]
              [--show-dir DIR] [--root DIR] [--now YYYY-MM-DDTHH:MM:SS] [--json]
  exposure.py --measures              the unit every check id is measured in

SPEC is `PORT[/tcp|/udp]`, one per port the standards say belongs here. KIND is one of `nft`,
`ufw`, `firewalld`, `none`, or `auto`, which asks the host in that order. `scaffold.py --flags`
in the setup skill prints every argument from the workspace.

Listening sockets come from `ss -H -ltunp`, or from `--ss-file` holding its output, which is what
makes the whole pass testable without a network stack. Certificate dates come from
`openssl x509 -noout -enddate -dateopt iso_8601`, or from `--enddate-dir` holding one
`<name>.enddate` file per certificate. Reads only: no port is closed, no rule is written.

A change under `fw.*` passes gate 2 first, because the rule that closes a port can close the
connection reading this report. See references/risk-classes.md beside the router.

Stdlib only. Exit code 0 always; findings are in the report, not the exit status.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
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
ISO_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")


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
    """One command, its stdout, or None when it is missing, fails, or takes too long."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def sockets(a):
    """Every listening socket as {proto, address, port}, from the host or from a captured file."""
    text = read(a.ss_file) if a.ss_file else run_command(["ss", "-H", "-ltunp"])
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
    """What a firewall says about itself, as one text.

    A firewalld host answers in two halves: `--state` says whether the daemon is doing anything
    at all, `--list-all` says what it lets in. Reading only the second one would call a stopped
    daemon a firewall, because a zone still prints its rules when nothing enforces them.
    """
    if kind == "nft":
        return run_command(["nft", "list", "ruleset"])
    if kind == "ufw":
        return run_command(["ufw", "status", "verbose"])
    if kind == "firewalld":
        state = run_command(["firewall-cmd", "--state"])
        if state is None:
            state = "not running"
        rules = run_command(["firewall-cmd", "--list-all"]) or ""
        return state + "\n" + rules
    return None


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
    if kind == "none" or text is None:
        return {"kind": kind, "filtering": False, "ports": [], "read": text is not None,
                "ranges": [], "services": []}
    ports, ranges, services, filtering = [], [], [], False
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
        filtering = bool(m) and m.group("policy").lower() != "accept"
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
            "ranges": sorted(set(ranges)), "services": services}


def enddate(path, a):
    """The notAfter date of a certificate, as a naive datetime, or None."""
    if a.enddate_dir:
        text = read(Path(a.enddate_dir) / (Path(path).stem + ".enddate"))
    else:
        text = run_command(["openssl", "x509", "-noout", "-enddate", "-dateopt", "iso_8601",
                            "-in", str(path)])
    m = ISO_DATE.search(text or "")
    if not m:
        return None
    try:
        return dt.datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}")
    except ValueError:
        return None


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
        text = run_command(["systemctl", "show", unit], timeout=timeout)
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
    if open_ports is None:
        rep.add("INFO", "port.world-open",
                "no socket list, so nothing here says what this host offers the network")
        open_ports = []
    elif not expected:
        rep.add("INFO", "port.world-open",
                f"{plural(len(open_ports), 'socket')} {verb(len(open_ports), 'listen')} here and the workspace names no "
                "expected port, so every one of them would be a finding")
    listening = {(s["port"], s["proto"]) for s in open_ports}

    if expected and open_ports:
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

    if panel and open_ports:
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

    if not fw["read"] and fw["kind"] == "none":
        rep.add("FAIL", "fw.disabled",
                "nothing on this host answers as a firewall, so every port that listens is reachable "
                "by whatever can route to it",
                data=[{"target": "firewall", "value": "none"}], measure=1, by={"firewall": 1})
    elif not fw["filtering"]:
        rep.add("FAIL", "fw.disabled",
                f"the {fw['kind']} firewall on this host is not filtering, so the rules it holds "
                "do nothing",
                data=[{"target": fw["kind"], "value": "not filtering"}], measure=1,
                by={fw["kind"]: 1})
    else:
        rep.add("PASS", "fw.disabled", f"the firewall is filtering ({fw['kind']})", measure=0)

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
    m = item.get("measure") or {}
    value = m.get("value")
    if value is None:
        return ""
    return "costs " + plural(value, *ROW_WORD.get(item["id"], ("finding", "findings")))


def block(rows, indent="      "):
    if not rows:
        return []
    width = min(max(len(name) for name, _ in rows), 46)
    return [f"{indent}{paint(name.ljust(width), 'dim')}  {value}" for name, value in rows]


def detail(item):
    return [(str(d.get("target", "")), str(d.get("value", "")) or "yes") for d in item["data"][:5]]


def text_report(open_ports, fw, rep, target, standards):
    """The console report: what was measured, what needs a decision, what is only a note."""
    ranked = sorted(rep.items, key=lambda x: (LEVEL_ORDER[x["level"]],
                                              -((x.get("measure") or {}).get("value") or 0), x["id"]))
    findings = [i for i in ranked if i["level"] in ("FAIL", "WARN")]
    notes = [i for i in ranked if i["level"] == "INFO"]
    passed = [i for i in ranked if i["level"] == "PASS"]
    out = [paint(f"exposure  {target}  {plural(len(open_ports or []), 'listening socket')}, "
                 f"firewall {fw['kind']}", "head"),
           f"measured against  {standards}", "",
           f"{plural(len(findings), 'finding')} to decide on, "
           f"{plural(len(notes), 'note')}, {plural(len(passed), 'check')} passed"]
    for i in findings + notes:
        tag = paint("note" if i["level"] == "INFO" else f"{i['level']:<4}", i["level"])
        price = f"  ({cost(i)})" if i["level"] != "INFO" and cost(i) else ""
        out += ["", f"{tag}  {paint(i['id'], 'id')}" + paint(price, "dim"),
                f"      {i['message']}"]
        out += block(detail(i))
        if len(i["data"]) > 5:
            out.append(f"      and {len(i['data']) - 5} more, the full list is in the JSON")
    if passed:
        out += ["", paint("passed  " + ", ".join(sorted({i["id"] for i in passed})), "dim")]
    if findings:
        out += ["", paint("next", "head") + "  close what is open to anywhere before what is only "
                "untidy, and pass gate 2 before a rule changes, then look each id up in the fixes "
                "table of jorekai-ops:ops for the fix per control plane and the risk class"]
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
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", default=None, metavar="YYYY-MM-DDTHH:MM:SS", help="for tests")
    ap.add_argument("--measures", action="store_true", help="print the unit of every check id")
    a = ap.parse_args(argv)
    if a.measures:
        for cid, unit in sorted(MEASURES.items()):
            print(f"{cid} {unit}")
        return 0
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()
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
    else:
        standards = (f"{plural(len(a.expected_port or []), 'expected port')}"
                     f" · a certificate more than {plural(a.tls_expiring_days, 'day')} from its date"
                     f" · {plural(len(a.intrusion_unit or []), 'unit')} watching failed attempts")
        print(text_report(open_ports, fw, rep, target, standards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
