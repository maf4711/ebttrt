#!/usr/bin/env python3
"""Stdlib tests for ebttrl. Run: python3 tests/test_ebttrl.py"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ebttrl  # noqa: E402
import ebttrl_loop  # noqa: E402
import ebttrl_prove  # noqa: E402


class TmpHome(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["GROK_HOME"] = str(self.home)
        os.environ["EBTTRL_HOME"] = str(self.home / "ebttrl")
        os.environ["GROK_PLUGIN_ROOT"] = str(ROOT)

    def tearDown(self) -> None:
        self.tmp.cleanup()


class ShieldTests(TmpHome):
    def test_denies_dump_keychain(self) -> None:
        reason = ebttrl.deny_reason("security dump-keychain -d")
        self.assertIsNotNone(reason)

    def test_denies_rm_rf_root(self) -> None:
        self.assertIsNotNone(ebttrl.deny_reason("rm -rf /"))
        self.assertIsNotNone(ebttrl.deny_reason("sudo rm -rf /"))

    def test_allows_normal_rm(self) -> None:
        self.assertIsNone(ebttrl.deny_reason("rm -rf ./build"))

    def test_denies_cookie_theft(self) -> None:
        self.assertIsNotNone(ebttrl.deny_reason("python -c 'import pycookiecheat'"))

    def test_scan_flags_secret_assignment_without_echoing_it(self) -> None:
        target = self.home / "leak.py"
        target.write_text('API_KEY = "sk-this-is-not-real-but-long"\n', encoding="utf-8")
        findings = ebttrl.scan_file(target)
        self.assertTrue(any(f["rule"] == "assignment-looks-like-secret" for f in findings))
        dumped = json.dumps(findings)
        self.assertNotIn("sk-this-is-not-real-but-long", dumped)

    def test_markdown_mention_is_not_a_command(self) -> None:
        target = self.home / "README.md"
        target.write_text("Never run security dump-keychain.\n", encoding="utf-8")
        self.assertEqual(ebttrl.scan_file(target), [])

    def test_shell_script_command_is_flagged(self) -> None:
        target = self.home / "bad.sh"
        target.write_text("security dump-keychain -d\n", encoding="utf-8")
        findings = ebttrl.scan_file(target)
        self.assertTrue(any(f["rule"] == "dangerous-command" for f in findings))

    def test_grade_critical_is_f(self) -> None:
        self.assertEqual(ebttrl.grade([{"severity": "critical"}]), "F")
        self.assertEqual(ebttrl.grade([]), "A")


class ReceiptTests(TmpHome):
    def test_receipt_roundtrip(self) -> None:
        cwd = self.home / "proj"
        cwd.mkdir()
        rc = ebttrl.cmd_receipt_write("ship ebttrl", "python3 tests/test_ebttrl.py", ["verify"], cwd)
        self.assertEqual(rc, 0)
        receipts = list((self.home / "ebttrl" / "receipts").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        rec = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual(rec["goal"], "ship ebttrl")
        self.assertEqual(rec["source"]["cwd"], str(cwd))
        self.assertIsNone(rec["source"]["dirty_digest"])
        self.assertEqual(ebttrl.cmd_receipt_last(), 0)

    def test_context_filters_foreign_workspace_receipts(self) -> None:
        here = self.home / "here"
        there = self.home / "there"
        here.mkdir()
        there.mkdir()
        ebttrl.cmd_receipt_write("foreign", "true", ["verify"], there)
        ebttrl.cmd_receipt_write("local", "true", ["verify"], here)
        ebttrl.hook_session_start({"workspaceRoot": str(here), "cwd": str(here), "sessionId": "s"})
        ctx = (self.home / "ebttrl" / "current-context.md").read_text(encoding="utf-8")
        self.assertIn("local", ctx)
        self.assertNotIn("foreign", ctx)

    def test_remember_instinct(self) -> None:
        self.assertEqual(ebttrl.cmd_remember("prefer safari", "*", 0.8, self.home, force=True), 0)
        rows = ebttrl.read_jsonl(self.home / "ebttrl" / "instincts.jsonl")
        self.assertEqual(rows[-1]["text"], "prefer safari")
        self.assertLessEqual(rows[-1]["confidence"], 0.5)


class LoopTests(TmpHome):
    def test_begin_phase_next_done(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        old = Path.cwd()
        os.chdir(cwd)
        try:
            (cwd / ".ebttrl.json").write_text(
                '{"prove": "python3 -c \\"print(1)\\""}\n', encoding="utf-8"
            )
            self.assertEqual(ebttrl_loop.cmd_begin("add auth", cwd, "implement"), 0)
            self.assertEqual(ebttrl_loop.cmd_phase("verify", cwd, "pytest 3/3"), 0)
            self.assertTrue(ebttrl_loop.load_active(cwd)["verified"])
            self.assertEqual(ebttrl_prove.cmd_prove(cwd), 0)
            self.assertEqual(ebttrl.cmd_done("pytest 3/3", cwd), 0)
            self.assertIsNone(ebttrl_loop.load_active(cwd))
            recs = list((self.home / "ebttrl" / "receipts").glob("*.json"))
            self.assertEqual(len(recs), 1)
        finally:
            os.chdir(old)

    def test_cannot_skip_verify(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        ebttrl_loop.cmd_begin("x", cwd, "implement")
        self.assertEqual(ebttrl_loop.cmd_phase("remember", cwd), 1)

    def test_done_from_plan_without_implement_fails(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        ebttrl_loop.cmd_begin("x", cwd, "plan")
        self.assertEqual(ebttrl.cmd_done("true", cwd), 1)

    def test_second_begin_blocked_while_open(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        self.assertEqual(ebttrl_loop.cmd_begin("one", cwd), 0)
        self.assertEqual(ebttrl_loop.cmd_begin("two", cwd), 1)


class HookTests(TmpHome):
    def test_session_start_writes_capped_context(self) -> None:
        event = {"workspaceRoot": str(self.home), "sessionId": "sess-1", "cwd": str(self.home)}
        self.assertEqual(ebttrl.hook_session_start(event), 0)
        ctx = (self.home / "ebttrl" / "current-context.md").read_text(encoding="utf-8")
        self.assertIn("plan → test → implement", ctx)
        self.assertLessEqual(len(ctx), ebttrl.MAX_CONTEXT_CHARS)

    def test_pretool_deny_json(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrl.hook_pretool({"toolInput": {"command": "security dump-keychain"}})
        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["decision"], "deny")
        self.assertNotIn("password", payload.get("reason", "").lower())

    def test_pretool_allow(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrl.hook_pretool({"toolInput": {"command": "python3 tests/test_ebttrl.py"}})
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["decision"], "allow")

    def test_stop_nudge_on_done_claim(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        cwd = self.home / "app"
        cwd.mkdir()
        ebttrl_loop.cmd_begin("auth", cwd, "implement")
        ebttrl_loop.note_edit({"toolName": "search_replace", "cwd": str(cwd), "workspaceRoot": str(cwd)})
        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrl.hook_stop(
                {
                    "reason": "end_turn",
                    "cwd": str(cwd),
                    "workspaceRoot": str(cwd),
                    "lastAssistantMessage": "Done. All tests pass.",
                }
            )
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("not verified", payload["hookSpecificOutput"]["additionalContext"])

    def test_stop_silent_without_loop(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrl.hook_stop(
                {
                    "reason": "end_turn",
                    "cwd": str(self.home),
                    "workspaceRoot": str(self.home),
                    "lastAssistantMessage": "Done.",
                }
            )
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), "")

    def test_stop_silent_when_already_nudged(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        cwd = self.home / "app"
        cwd.mkdir()
        ebttrl_loop.cmd_begin("auth", cwd, "implement")
        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrl.hook_stop(
                {
                    "reason": "end_turn",
                    "stopHookActive": True,
                    "cwd": str(cwd),
                    "workspaceRoot": str(cwd),
                    "lastAssistantMessage": "Done.",
                }
            )
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), "")

    def test_session_start_includes_active_loop(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        ebttrl_loop.cmd_begin("auth", cwd, "implement")
        ebttrl.hook_session_start({"workspaceRoot": str(cwd), "cwd": str(cwd), "sessionId": "s2"})
        ctx = (self.home / "ebttrl" / "current-context.md").read_text(encoding="utf-8")
        self.assertIn("auth", ctx)
        self.assertIn("implement", ctx)


class InstallTests(TmpHome):
    def test_install_links_plugin_and_rule(self) -> None:
        rc = ebttrl.cmd_install()
        self.assertEqual(rc, 0)
        link = self.home / "plugins" / "ebttrl"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), ROOT)
        self.assertTrue((self.home / "rules" / "ebttrl-loop.md").exists())
        self.assertTrue((self.home / "bin" / "ebttrl").exists())
        self.assertEqual(ebttrl.cmd_doctor(), 0)

    def test_install_is_idempotent(self) -> None:
        self.assertEqual(ebttrl.cmd_install(), 0)
        self.assertEqual(ebttrl.cmd_install(), 0)

    def test_append_enabled_does_not_duplicate(self) -> None:
        cfg = self.home / "config.toml"
        cfg.write_text("[plugins]\nenabled = [\n    \"ruflo-core\",\n]\n", encoding="utf-8")
        ebttrl.append_enabled_plugin()
        ebttrl.append_enabled_plugin()
        text = cfg.read_text(encoding="utf-8")
        self.assertEqual(text.count('"ebttrl"'), 1)

    def test_world_writable_flagged(self) -> None:
        target = self.home / "open.sh"
        target.write_text("echo hi\n", encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IWOTH)
        findings = ebttrl.scan_file(target)
        self.assertTrue(any(f["rule"] == "world-writable" for f in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
