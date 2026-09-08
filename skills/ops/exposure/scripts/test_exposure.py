#!/usr/bin/env python3
"""Offline tests for exposure.py: listening sockets, firewalls, certificates, watchers.

Run: python3 skills/ops/exposure/scripts/test_exposure.py
Uses captured `ss`, firewall status, `systemctl show` and end-date files. No network stack, no
firewall, no openssl, no systemd.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exposure  # noqa: E402

SCRIPT = os.path.abspath(exposure.__file__)
NOW = "2026-09-08T12:00:00"
SS = """tcp   LISTEN 0      128          0.0.0.0:22         0.0.0.0:*    users:(("sshd",pid=1,fd=3))
tcp   LISTEN 0      511             [::]:443              [::]:*    users:(("nginx",pid=2,fd=6))
tcp   LISTEN 0      244        127.0.0.1:5432         0.0.0.0:*    users:(("postgres",pid=3,fd=5))
udp   UNCONN 0      0                *:111                 *:*      users:(("rpcbind",pid=4,fd=4))
"""


def write(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def run(d, extra=(), ss=SS, ports=("22/tcp", "443/tcp")):
    args = [sys.executable, SCRIPT, "--json", "--now", NOW, "--root", str(d)]
    if ss is not None:
        args += ["--ss-file", str(write(Path(d) / "ss.txt", ss))]
    for p in ports:
        args += ["--expected-port", p]
    if "--fw-kind" not in extra:
        args += ["--fw-kind", "none"]
    r = subprocess.run(args + list(extra), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def item(out, cid, level=None):
    for i in out["items"]:
        if i["id"] == cid and (level is None or i["level"] == level):
            return i
    raise AssertionError(f"no {cid} ({level}) in {[(i['id'], i['level']) for i in out['items']]}")


class PortTest(unittest.TestCase):
    def test_a_port_spec_carries_an_optional_protocol(self):
        self.assertEqual(exposure.parse_port("443/tcp"), (443, "tcp"))
        self.assertEqual(exposure.parse_port("53"), (53, ""))

    def test_a_spec_that_is_not_a_port_is_refused(self):
        with self.assertRaises(SystemExit):
            exposure.parse_port("http")

    def test_both_address_families_are_read_as_open_to_anywhere(self):
        self.assertEqual(exposure.reach("0.0.0.0"), "anywhere")
        self.assertEqual(exposure.reach("[::]"), "anywhere")
        self.assertEqual(exposure.reach("*"), "anywhere")
        self.assertEqual(exposure.reach("127.0.0.1"), "here")
        self.assertEqual(exposure.reach("10.1.2.3"), "an interface")


class SocketTest(unittest.TestCase):
    def test_every_listening_socket_is_read_from_the_captured_output(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d)
            self.assertEqual(sorted(s["port"] for s in out["sockets"]), [22, 111, 443, 5432])

    def test_a_port_open_to_anywhere_that_nobody_named_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            got = item(run(d), "port.world-open", "FAIL")
            self.assertEqual(got["measure"]["value"], 1)
            self.assertEqual(got["data"][0]["target"], "111/udp")

    def test_a_port_bound_to_one_address_is_untidy_and_not_open(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d)
            self.assertEqual(item(out, "port.unexpected", "WARN")["data"][0]["target"], "5432/tcp")
            self.assertNotIn("5432", json.dumps(item(out, "port.world-open", "FAIL")["data"]))

    def test_a_host_that_serves_only_what_it_should_passes_both(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, ss=SS.splitlines(keepends=True)[0])
            self.assertEqual(item(out, "port.world-open", "PASS")["measure"]["value"], 0)
            self.assertEqual(item(out, "port.unexpected", "PASS")["measure"]["value"], 0)

    def test_a_panel_port_open_to_anywhere_is_its_own_finding(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, ports=("22/tcp", "443/tcp", "8443/tcp"),
                      ss=SS + "tcp   LISTEN 0  128   0.0.0.0:8443   0.0.0.0:*\n",
                      extra=["--panel-port", "8443/tcp"])
            self.assertEqual(item(out, "panel.exposed", "FAIL")["measure"]["value"], 1)

    def test_a_panel_port_is_counted_once_and_not_in_the_other_two(self):
        """A port in two rows is one action counted twice, and the log would carry both."""
        with tempfile.TemporaryDirectory() as d:
            out = run(d, ss="tcp LISTEN 0 128 0.0.0.0:8443 0.0.0.0:*\n",
                      extra=["--panel-port", "8443/tcp"])
            self.assertEqual(item(out, "panel.exposed", "FAIL")["measure"]["value"], 1)
            self.assertEqual(item(out, "port.world-open", "PASS")["measure"]["value"], 0)
            self.assertEqual(item(out, "port.unexpected", "PASS")["measure"]["value"], 0)

    def test_no_socket_list_is_a_note_and_not_a_clean_host(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, ss=None, extra=["--ss-file", str(Path(d) / "missing.txt")])
            self.assertEqual(item(out, "port.world-open", "INFO")["measure"], None)


class FirewallTest(unittest.TestCase):
    def fw(self, d, kind, text, extra=()):
        path = write(Path(d) / "fw.txt", text)
        return run(d, extra=["--fw-kind", kind, "--fw-file", str(path), *extra])

    def test_an_inactive_ufw_is_a_firewall_that_filters_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.fw(d, "ufw", "Status: inactive\n")
            self.assertEqual(item(out, "fw.disabled", "FAIL")["measure"]["value"], 1)

    def test_an_active_ufw_passes_and_its_rules_are_read(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.fw(d, "ufw", "Status: active\n\nTo    Action  From\n--    ------  ----\n"
                                    "22/tcp   ALLOW   Anywhere\n443/tcp  ALLOW   Anywhere\n")
            self.assertEqual(item(out, "fw.disabled", "PASS")["measure"]["value"], 0)
            self.assertEqual(item(out, "fw.rule-orphan", "PASS")["measure"]["value"], 0)

    def test_a_rule_for_a_port_nothing_serves_is_an_orphan(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.fw(d, "ufw", "Status: active\n\n8080/tcp  ALLOW  Anywhere\n")
            got = item(out, "fw.rule-orphan", "WARN")
            self.assertEqual(got["measure"]["value"], 1)
            self.assertEqual(got["data"][0]["target"], "8080/tcp")

    def test_firewalld_ports_are_read_and_its_services_are_a_note(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.fw(d, "firewalld", "public (active)\n  services: ssh http\n  ports: 8080/tcp\n")
            self.assertEqual(item(out, "fw.disabled", "PASS")["measure"]["value"], 0)
            self.assertEqual(item(out, "fw.rule-orphan", "WARN")["data"][0]["target"], "8080/tcp")
            self.assertEqual(item(out, "fw.rule-orphan", "INFO")["data"][0]["target"], "ssh")

    def test_a_firewalld_that_is_not_running_filters_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.fw(d, "firewalld", "not running\n")
            self.assertEqual(item(out, "fw.disabled", "FAIL")["measure"]["value"], 1)

    def test_an_nftables_input_chain_that_drops_is_filtering(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.fw(d, "nft", "table inet filter {\n  chain input {\n"
                                    "    type filter hook input priority 0; policy drop;\n"
                                    "    tcp dport { 22, 443 } accept\n  }\n}\n")
            self.assertEqual(item(out, "fw.disabled", "PASS")["measure"]["value"], 0)
            self.assertEqual(item(out, "fw.rule-orphan", "PASS")["measure"]["value"], 0)

    def test_an_nftables_input_chain_that_accepts_everything_filters_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.fw(d, "nft", "table inet filter {\n  chain input {\n"
                                    "    type filter hook input priority 0; policy accept;\n  }\n}\n")
            self.assertEqual(item(out, "fw.disabled", "FAIL")["measure"]["value"], 1)

    def test_a_status_file_without_a_kind_is_refused(self):
        """A status text does not say which firewall wrote it, and guessing would misread it."""
        with tempfile.TemporaryDirectory() as d:
            path = write(Path(d) / "fw.txt", "Status: active\n")
            r = subprocess.run([sys.executable, SCRIPT, "--fw-file", str(path)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("--fw-kind", r.stderr)


class CertificateTest(unittest.TestCase):
    def prepare(self, d, until):
        write(Path(d) / "etc/ssl/site.pem", "certificate\n")
        write(Path(d) / "dates/site.enddate", f"notAfter={until}\n")
        return ["--cert", "/etc/ssl/site.pem", "--enddate-dir", str(Path(d) / "dates")]

    def test_a_certificate_past_its_date_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, extra=self.prepare(d, "2026-09-01 00:00:00Z"))
            self.assertEqual(item(out, "tls.expired", "FAIL")["measure"]["value"], 1)

    def test_a_certificate_inside_the_window_warns_once(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, extra=self.prepare(d, "2026-09-20 00:00:00Z") + ["--tls-expiring-days", "21"])
            self.assertEqual(item(out, "tls.expiring", "WARN")["measure"]["value"], 1)
            self.assertEqual(item(out, "tls.expired", "PASS")["measure"]["value"], 0)

    def test_a_certificate_far_from_its_date_passes_both(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d, extra=self.prepare(d, "2027-01-01 00:00:00Z"))
            self.assertEqual(item(out, "tls.expired", "PASS")["measure"]["value"], 0)
            self.assertEqual(item(out, "tls.expiring", "PASS")["measure"]["value"], 0)

    def test_a_certificate_with_no_readable_date_is_a_note(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/ssl/site.pem", "certificate\n")
            write(Path(d) / "dates/site.enddate", "nothing here\n")
            out = run(d, extra=["--cert", "/etc/ssl/site.pem", "--enddate-dir", str(Path(d) / "dates")])
            self.assertEqual(item(out, "tls.expired", "INFO")["data"][0]["value"], "no date")

    def test_a_directory_of_certificates_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "etc/ssl/a.pem", "certificate\n")
            write(Path(d) / "etc/ssl/b.crt", "certificate\n")
            write(Path(d) / "dates/a.enddate", "notAfter=2026-09-01 00:00:00Z\n")
            write(Path(d) / "dates/b.enddate", "notAfter=2026-09-02 00:00:00Z\n")
            out = run(d, extra=["--cert-dir", "/etc/ssl", "--enddate-dir", str(Path(d) / "dates")])
            self.assertEqual(item(out, "tls.expired", "FAIL")["measure"]["value"], 2)


class WatcherTest(unittest.TestCase):
    def test_a_watcher_that_is_not_running_is_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "show/watch.service.show", "ActiveState=inactive\n")
            out = run(d, extra=["--intrusion-unit", "watch.service", "--show-dir", str(Path(d) / "show")])
            self.assertEqual(item(out, "intrusion.off", "WARN")["measure"]["value"], 1)

    def test_a_running_watcher_passes(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d) / "show/watch.service.show", "ActiveState=active\n")
            out = run(d, extra=["--intrusion-unit", "watch.service", "--show-dir", str(Path(d) / "show")])
            self.assertEqual(item(out, "intrusion.off", "PASS")["measure"]["value"], 0)

    def test_a_unit_with_no_state_counts_as_not_watching(self):
        """A unit systemd does not know is not a unit that is running."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "show").mkdir(parents=True)
            out = run(d, extra=["--intrusion-unit", "watch.service", "--show-dir", str(Path(d) / "show")])
            self.assertEqual(item(out, "intrusion.off", "WARN")["data"][0]["value"], "no state")


class ReportTest(unittest.TestCase):
    def test_every_measured_id_carries_the_unit_the_table_names(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(d)
            for i in out["items"]:
                if i["measure"]:
                    self.assertEqual(i["measure"]["unit"], exposure.MEASURES[i["id"]])

    def test_the_verb_agrees_with_the_count_in_front_of_it(self):
        with tempfile.TemporaryDirectory() as d:
            one = item(run(d), "port.world-open", "FAIL")["message"]
            self.assertIn("1 port takes", one)
            many = item(run(d, ports=("22/tcp",)), "port.world-open", "FAIL")["message"]
            self.assertIn("2 ports take", many)

    def test_the_console_report_carries_no_escape_when_nothing_is_a_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--fw-kind", "none",
                                "--now", NOW], capture_output=True, text=True)
            self.assertNotIn("\033[", r.stdout)

    def test_a_terminal_gets_the_same_report_in_colour(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, FORCE_COLOR="1")
            env.pop("NO_COLOR", None)
            r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--fw-kind", "none",
                                "--now", NOW], capture_output=True, text=True, env=env)
            self.assertIn("\033[", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
