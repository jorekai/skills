#!/usr/bin/env python3
"""Offline tests for access.py: sshd parsing, key sizes, and the checks built on them.

Run: python3 skills/ops/access/scripts/test_access.py
Builds a captured tree in a temp folder; no network, no ssh, nothing read from the real host.
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import access  # noqa: E402

SCRIPT = os.path.abspath(access.__file__)


def rsa_blob(bits):
    """An ssh-rsa public key blob of a given size, built by hand: no key generation in stdlib."""
    def field(b):
        return len(b).to_bytes(4, "big") + b
    modulus = (1 << (bits - 1)).to_bytes(bits // 8, "big")
    raw = field(b"ssh-rsa") + field((65537).to_bytes(3, "big")) + field(b"\x00" + modulus)
    return base64.b64encode(raw).decode()


class SshdConfigTest(unittest.TestCase):
    def test_the_first_value_of_a_keyword_wins(self):
        """sshd takes the first obtained value, so a later line is not the effective one."""
        s = access.sshd_settings("PermitRootLogin no\nPermitRootLogin yes\n")
        self.assertEqual(s["permitrootlogin"], ["no"])

    def test_comments_and_an_equals_separator_are_read(self):
        s = access.sshd_settings("# comment\nPort=2222\nMaxAuthTries 3   # inline\n")
        self.assertEqual(s["port"], ["2222"])
        self.assertEqual(s["maxauthtries"], ["3"])

    def test_an_include_wins_over_the_lines_below_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "etc/ssh/sshd_config.d").mkdir(parents=True)
            (root / "etc/ssh/sshd_config.d/50-cloud.conf").write_text(
                "PermitRootLogin yes\n", encoding="utf-8")
            cfg = root / "etc/ssh/sshd_config"
            cfg.write_text("Include /etc/ssh/sshd_config.d/*.conf\nPermitRootLogin no\n",
                           encoding="utf-8")
            s = access.sshd_settings(cfg.read_text(encoding="utf-8"), str(cfg.parent), root=str(root))
            self.assertEqual(s["permitrootlogin"], ["yes"])

    def test_an_absolute_include_stays_inside_the_given_root(self):
        """A pass against a captured tree must never read the running host's configuration."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "etc/ssh").mkdir(parents=True)
            cfg = root / "etc/ssh/sshd_config"
            cfg.write_text("Include /etc/ssh/nothing.d/*.conf\nPermitRootLogin no\n", encoding="utf-8")
            s = access.sshd_settings(cfg.read_text(encoding="utf-8"), str(cfg.parent), root=str(root))
            self.assertEqual(s["permitrootlogin"], ["no"])

    def test_a_match_block_that_reopens_passwords_is_found(self):
        text = "PasswordAuthentication no\nMatch Group deploy\n    PasswordAuthentication yes\n"
        self.assertIn(("Group deploy", "passwordauthentication", "yes"), access.match_blocks(text))

    def test_a_match_block_does_not_set_the_global_value(self):
        """A keyword under Match applies to that group alone, so the global default still holds."""
        text = "PermitRootLogin no\nMatch User backup\n    PasswordAuthentication no\n"
        self.assertNotIn("passwordauthentication", access.sshd_settings(text))
        self.assertEqual(access.sshd_settings(text)["permitrootlogin"], ["no"])


class KeyTest(unittest.TestCase):
    def test_the_bit_length_comes_from_the_modulus(self):
        self.assertEqual(access.key_bits(rsa_blob(2048)), 2048)
        self.assertEqual(access.key_bits(rsa_blob(1024)), 1024)

    def test_a_blob_that_is_not_base64_is_not_a_size(self):
        self.assertIsNone(access.key_bits("not base64 at all"))

    def test_options_in_front_of_the_key_do_not_shift_the_fields(self):
        line = 'command="/usr/bin/x",no-pty ssh-ed25519 AAAAC3Nz nils@mac'
        keys = access.parse_authorized_keys(line)
        self.assertEqual(keys[0]["type"], "ssh-ed25519")
        self.assertEqual(keys[0]["blob"], "AAAAC3Nz")
        self.assertEqual(keys[0]["comment"], "nils@mac")


def build(d, sshd="", passwd=None, keys=None, sudoers=""):
    """A captured host tree: sshd config, accounts, authorized keys, sudoers."""
    root = Path(d)
    (root / "etc/ssh").mkdir(parents=True)
    (root / "etc/ssh/sshd_config").write_text(sshd, encoding="utf-8")
    lines = passwd if passwd is not None else [
        "root:x:0:0:root:/root:/bin/bash",
        "ops-scan:x:1001:1001::/home/ops-scan:/bin/bash",
        "daemon:x:2:2:daemon:/usr/sbin:/usr/sbin/nologin",
    ]
    (root / "etc").mkdir(parents=True, exist_ok=True)
    (root / "etc/passwd").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for account, text in (keys or {}).items():
        home = root / ("root" if account == "root" else f"home/{account}") / ".ssh"
        home.mkdir(parents=True, exist_ok=True)
        (home / "authorized_keys").write_text(text, encoding="utf-8")
    if sudoers:
        (root / "etc/sudoers").write_text(sudoers, encoding="utf-8")
    return root


def run(root, *extra):
    r = subprocess.run([sys.executable, SCRIPT, "--root", str(root), "--json",
                        "--today", "2026-09-07", *extra], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def item(out, cid):
    return next(i for i in out["items"] if i["id"] == cid)


class ChecksTest(unittest.TestCase):
    def test_root_login_open_is_a_finding_and_closed_measures_zero(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(build(d, sshd="PermitRootLogin yes\n"))
            i = item(out, "ssh.root-login")
            self.assertEqual(i["level"], "FAIL")
            self.assertEqual(i["measure"]["value"], 1)
        with tempfile.TemporaryDirectory() as d:
            out = run(build(d, sshd="PermitRootLogin no\n"))
            i = item(out, "ssh.root-login")
            self.assertEqual(i["level"], "PASS")
            self.assertEqual(i["measure"]["value"], 0)

    def test_a_match_block_counts_as_a_place_that_permits_a_password(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(build(d, sshd="PasswordAuthentication no\nKbdInteractiveAuthentication no\n"
                                    "Match Group deploy\n    PasswordAuthentication yes\n"))
            i = item(out, "ssh.password-auth")
            self.assertEqual(i["measure"]["value"], 1)
            self.assertEqual(i["data"][0]["target"], "Match Group deploy")

    def test_a_password_setting_under_match_leaves_the_global_default_open(self):
        """The only `no` sits under Match, so both global switches are still at their default."""
        with tempfile.TemporaryDirectory() as d:
            out = run(build(d, sshd="PermitRootLogin no\nMatch User backup\n"
                                    "    PasswordAuthentication no\n"))
            i = item(out, "ssh.password-auth")
            self.assertEqual(i["level"], "FAIL")
            self.assertEqual(i["measure"]["value"], 2)
            self.assertEqual(sorted(r["target"] for r in i["data"]),
                             ["KbdInteractiveAuthentication", "PasswordAuthentication"])

    def test_a_key_on_an_account_the_standards_do_not_name_is_an_orphan(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d, keys={"root": f"ssh-rsa {rsa_blob(4096)} old-laptop\n"})
            out = run(root, "--allow-user", "ops-scan")
            i = item(out, "key.orphan")
            self.assertEqual(i["level"], "FAIL")
            self.assertEqual(i["measure"]["value"], 1)
            self.assertEqual(i["measure"]["by"], {"root": 1})

    def test_a_short_rsa_key_falls_under_the_bar(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d, keys={"ops-scan": f"ssh-rsa {rsa_blob(1024)} small\n"})
            out = run(root, "--min-key-bits", "3072")
            self.assertEqual(item(out, "key.weak")["measure"]["value"], 1)
            out = run(root, "--min-key-bits", "0")
            self.assertEqual(item(out, "key.weak")["measure"]["value"], 0)

    def test_one_key_on_two_accounts_is_counted_once_per_account(self):
        with tempfile.TemporaryDirectory() as d:
            blob = rsa_blob(4096)
            root = build(d, keys={"root": f"ssh-rsa {blob} shared\n",
                                  "ops-scan": f"ssh-rsa {blob} shared\n"})
            i = item(run(root), "key.duplicate")
            self.assertEqual(i["measure"]["value"], 2)

    def test_single_path_measures_what_is_missing_from_the_bar(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d)
            self.assertEqual(item(run(root, "--path", "ops-admin"), "access.single-path")
                             ["measure"]["value"], 1)
            out = run(root, "--path", "ops-admin", "--path", "console")
            self.assertEqual(item(out, "access.single-path")["level"], "PASS")
            self.assertEqual(item(out, "access.single-path")["measure"]["value"], 0)

    def test_a_passwordless_sudo_rule_the_table_names_is_not_a_finding(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d, sudoers="ops-admin ALL=(root) NOPASSWD: /usr/bin/systemctl\n")
            self.assertEqual(item(run(root), "sudo.nopasswd")["measure"]["value"], 1)
            out = run(root, "--allow-sudo-command", "/usr/bin/systemctl")
            self.assertEqual(item(out, "sudo.nopasswd")["level"], "PASS")

    def test_a_commented_sudo_line_is_not_a_rule(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d, sudoers="# ops-admin ALL=(root) NOPASSWD: /bin/sh\n")
            self.assertEqual(item(run(root), "sudo.nopasswd")["measure"]["value"], 0)

    def test_a_missing_source_is_a_note_and_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "etc").mkdir(parents=True)
            out = run(root)
            self.assertEqual(item(out, "ssh.root-login")["level"], "INFO")
            self.assertIsNone(item(out, "ssh.root-login")["measure"])


class ContractTest(unittest.TestCase):
    def test_measures_prints_one_id_and_unit_per_line(self):
        r = subprocess.run([sys.executable, SCRIPT, "--measures"], capture_output=True, text=True)
        pairs = dict(line.split() for line in r.stdout.splitlines() if line.strip())
        self.assertEqual(pairs, access.MEASURES)

    def test_every_measured_finding_carries_value_unit_and_by(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(build(d, sshd="PermitRootLogin yes\n"))
            self.assertEqual(out["tool"], "access")
            self.assertIn("counts", out)
            for i in out["items"]:
                if i["measure"] is not None:
                    self.assertIn("value", i["measure"])
                    self.assertEqual(i["measure"]["unit"], access.MEASURES[i["id"]])
                    self.assertIsInstance(i["measure"]["by"], dict)

    def test_the_text_report_ends_on_a_next_step(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d, sshd="PermitRootLogin yes\n")
            r = subprocess.run([sys.executable, SCRIPT, "--root", str(root)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("measured against", r.stdout)
            self.assertIn("\nnext  ", r.stdout)

    def test_the_next_step_names_the_gate_only_while_the_gate_is_shut(self):
        """A passing check must never be the next step, or the ladder points at nothing."""
        with tempfile.TemporaryDirectory() as d:
            root = build(d, sshd="PermitRootLogin yes\n")
            shut = subprocess.run([sys.executable, SCRIPT, "--root", str(root)],
                                  capture_output=True, text=True).stdout
            open_ = subprocess.run([sys.executable, SCRIPT, "--root", str(root),
                                    "--path", "a", "--path", "b"],
                                   capture_output=True, text=True).stdout
            self.assertIn("next  close `access.single-path`", shut)
            self.assertNotIn("next  close `access.single-path`", open_)
            self.assertIn("\nnext  ", open_)

    def test_no_finding_disagrees_with_its_own_count(self):
        """Every message that opens on a count carries the verb form that count takes."""
        with tempfile.TemporaryDirectory() as d:
            root = build(d, keys={"root": f"ssh-rsa {rsa_blob(1024)} one\n"})
            one = run(root, "--min-key-bits", "3072")
            self.assertIn("1 key uses a retired type or falls under",
                          item(one, "key.weak")["message"])
        with tempfile.TemporaryDirectory() as d:
            root = build(d, keys={"root": f"ssh-rsa {rsa_blob(1024)} one\n",
                                  "ops-scan": f"ssh-rsa {rsa_blob(2048)} two\n"})
            two = run(root, "--min-key-bits", "3072")
            self.assertIn("2 keys use a retired type or fall under",
                          item(two, "key.weak")["message"])

    def test_a_verb_agrees_with_the_count_in_front_of_it(self):
        self.assertEqual(access.verb(1, "permit"), "permits")
        self.assertEqual(access.verb(2, "permit"), "permit")
        self.assertEqual(access.verb(1, "are", "is"), "is")
        self.assertEqual(access.verb(0, "are", "is"), "are")


class ColourTest(unittest.TestCase):
    """Colour is a hint on a report that reads the same without it (decisions/0022)."""

    def run_report(self, root, env=None):
        e = dict(os.environ)
        e.pop("FORCE_COLOR", None)
        e.pop("NO_COLOR", None)
        e.update(env or {})
        return subprocess.run([sys.executable, SCRIPT, "--root", str(root)], capture_output=True,
                              text=True, env=e).stdout

    def test_a_pipe_reads_plain_text(self):
        """Nothing here runs on a terminal: a redirect, a test and a subagent see no escape."""
        with tempfile.TemporaryDirectory() as d:
            self.assertNotIn("\033", self.run_report(build(d, sshd="PermitRootLogin yes\n")))

    def test_no_colour_wins_over_force_colour(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.run_report(build(d, sshd="PermitRootLogin yes\n"), {"FORCE_COLOR": "1", "NO_COLOR": "1"})
            self.assertNotIn("\033", out)

    def test_every_escape_removed_leaves_the_same_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = build(d, sshd="PermitRootLogin yes\n")
            plain = self.run_report(root)
            painted = self.run_report(root, {"FORCE_COLOR": "1"})
            self.assertIn("\033", painted)
            self.assertEqual(re.sub(r"\033\[[0-9;]*m", "", painted), plain)


if __name__ == "__main__":
    unittest.main(verbosity=1)
