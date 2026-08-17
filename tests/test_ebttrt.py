#!/usr/bin/env python3
"""Stdlib tests for ebttrt. Run: python3 tests/test_ebttrt.py"""

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

import ebttrt  # noqa: E402
import ebttrt_loop  # noqa: E402
import ebttrt_prove  # noqa: E402


class TmpHome(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["GROK_HOME"] = str(self.home)
        os.environ["EBTTRT_HOME"] = str(self.home / "ebttrt")
        os.environ["GROK_PLUGIN_ROOT"] = str(ROOT)

    def tearDown(self) -> None:
        self.tmp.cleanup()


class ShieldTests(TmpHome):
    def test_denies_dump_keychain(self) -> None:
        reason = ebttrt.deny_reason("security dump-keychain -d")
        self.assertIsNotNone(reason)

    def test_denies_rm_rf_root(self) -> None:
        self.assertIsNotNone(ebttrt.deny_reason("rm -rf /"))
        self.assertIsNotNone(ebttrt.deny_reason("sudo rm -rf /"))

    def test_allows_normal_rm(self) -> None:
        self.assertIsNone(ebttrt.deny_reason("rm -rf ./build"))

    def test_denies_cookie_theft(self) -> None:
        self.assertIsNotNone(ebttrt.deny_reason("python -c 'import pycookiecheat'"))

    def test_scan_flags_secret_assignment_without_echoing_it(self) -> None:
        target = self.home / "leak.py"
        target.write_text('API_KEY = "sk-this-is-not-real-but-long"\n', encoding="utf-8")
        findings = ebttrt.scan_file(target)
        self.assertTrue(any(f["rule"] == "assignment-looks-like-secret" for f in findings))
        dumped = json.dumps(findings)
        self.assertNotIn("sk-this-is-not-real-but-long", dumped)

    def test_markdown_mention_is_not_a_command(self) -> None:
        target = self.home / "README.md"
        target.write_text("Never run security dump-keychain.\n", encoding="utf-8")
        self.assertEqual(ebttrt.scan_file(target), [])

    def test_shell_script_command_is_flagged(self) -> None:
        target = self.home / "bad.sh"
        target.write_text("security dump-keychain -d\n", encoding="utf-8")
        findings = ebttrt.scan_file(target)
        self.assertTrue(any(f["rule"] == "dangerous-command" for f in findings))

    def test_grade_critical_is_f(self) -> None:
        self.assertEqual(ebttrt.grade([{"severity": "critical"}]), "F")
        self.assertEqual(ebttrt.grade([]), "A")


class ReceiptTests(TmpHome):
    def test_receipt_roundtrip(self) -> None:
        cwd = self.home / "proj"
        cwd.mkdir()
        rc = ebttrt.cmd_receipt_write("ship ebttrt", "python3 tests/test_ebttrt.py", ["verify"], cwd)
        self.assertEqual(rc, 0)
        receipts = list((self.home / "ebttrt" / "receipts").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        rec = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual(rec["goal"], "ship ebttrt")
        self.assertEqual(rec["source"]["cwd"], str(cwd))
        self.assertIsNone(rec["source"]["dirty_digest"])
        self.assertEqual(ebttrt.cmd_receipt_last(), 0)

    def test_context_filters_foreign_workspace_receipts(self) -> None:
        here = self.home / "here"
        there = self.home / "there"
        here.mkdir()
        there.mkdir()
        ebttrt.cmd_receipt_write("foreign", "true", ["verify"], there)
        ebttrt.cmd_receipt_write("local", "true", ["verify"], here)
        ebttrt.hook_session_start({"workspaceRoot": str(here), "cwd": str(here), "sessionId": "s"})
        ctx = (self.home / "ebttrt" / "current-context.md").read_text(encoding="utf-8")
        self.assertIn("local", ctx)
        self.assertNotIn("foreign", ctx)

    def test_remember_instinct(self) -> None:
        self.assertEqual(ebttrt.cmd_remember("prefer safari", "*", 0.8, self.home, force=True), 0)
        rows = ebttrt.read_jsonl(self.home / "ebttrt" / "instincts.jsonl")
        self.assertEqual(rows[-1]["text"], "prefer safari")
        self.assertLessEqual(rows[-1]["confidence"], 0.5)


class LoopTests(TmpHome):
    def test_begin_phase_next_done(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        old = Path.cwd()
        os.chdir(cwd)
        try:
            (cwd / ".ebttrt.json").write_text(
                '{"prove": "python3 -c \\"print(1)\\""}\n', encoding="utf-8"
            )
            self.assertEqual(ebttrt_loop.cmd_begin("add auth", cwd, "implement"), 0)
            self.assertEqual(ebttrt_loop.cmd_phase("verify", cwd, "pytest 3/3"), 0)
            self.assertTrue(ebttrt_loop.load_active(cwd)["verified"])
            self.assertEqual(ebttrt_prove.cmd_prove(cwd), 0)
            self.assertEqual(ebttrt.cmd_done("pytest 3/3", cwd), 0)
            self.assertIsNone(ebttrt_loop.load_active(cwd))
            recs = list((self.home / "ebttrt" / "receipts").glob("*.json"))
            self.assertEqual(len(recs), 1)
        finally:
            os.chdir(old)

    def test_cannot_skip_verify(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        ebttrt_loop.cmd_begin("x", cwd, "implement")
        self.assertEqual(ebttrt_loop.cmd_phase("remember", cwd), 1)

    def test_done_from_plan_without_implement_fails(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        ebttrt_loop.cmd_begin("x", cwd, "plan")
        self.assertEqual(ebttrt.cmd_done("true", cwd), 1)

    def test_second_begin_blocked_while_open(self) -> None:
        cwd = self.home / "app"
        cwd.mkdir()
        self.assertEqual(ebttrt_loop.cmd_begin("one", cwd), 0)
        self.assertEqual(ebttrt_loop.cmd_begin("two", cwd), 1)


class HookTests(TmpHome):
    def test_session_start_writes_capped_context(self) -> None:
        event = {"workspaceRoot": str(self.home), "sessionId": "sess-1", "cwd": str(self.home)}
        self.assertEqual(ebttrt.hook_session_start(event), 0)
        ctx = (self.home / "ebttrt" / "current-context.md").read_text(encoding="utf-8")
        self.assertIn("plan → test → implement", ctx)
        self.assertLessEqual(len(ctx), ebttrt.MAX_CONTEXT_CHARS)

    def test_pretool_deny_json(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrt.hook_pretool({"toolInput": {"command": "security dump-keychain"}})
        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["decision"], "deny")
        self.assertNotIn("password", payload.get("reason", "").lower())

    def test_pretool_allow(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrt.hook_pretool({"toolInput": {"command": "python3 tests/test_ebttrt.py"}})
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["decision"], "allow")

    def test_stop_nudge_on_done_claim(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        cwd = self.home / "app"
        cwd.mkdir()
        ebttrt_loop.cmd_begin("auth", cwd, "implement")
        ebttrt_loop.note_edit({"toolName": "search_replace", "cwd": str(cwd), "workspaceRoot": str(cwd)})
        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrt.hook_stop(
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
            rc = ebttrt.hook_stop(
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
        ebttrt_loop.cmd_begin("auth", cwd, "implement")
        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrt.hook_stop(
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
        ebttrt_loop.cmd_begin("auth", cwd, "implement")
        ebttrt.hook_session_start({"workspaceRoot": str(cwd), "cwd": str(cwd), "sessionId": "s2"})
        ctx = (self.home / "ebttrt" / "current-context.md").read_text(encoding="utf-8")
        self.assertIn("auth", ctx)
        self.assertIn("implement", ctx)


class InstallTests(TmpHome):
    def test_install_links_plugin_and_rule(self) -> None:
        rc = ebttrt.cmd_install()
        self.assertEqual(rc, 0)
        link = self.home / "plugins" / "ebttrt"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), ROOT)
        self.assertTrue((self.home / "rules" / "ebttrt-loop.md").exists())
        self.assertTrue((self.home / "bin" / "ebttrt").exists())
        self.assertEqual(ebttrt.cmd_doctor(), 0)

    def test_install_is_idempotent(self) -> None:
        self.assertEqual(ebttrt.cmd_install(), 0)
        self.assertEqual(ebttrt.cmd_install(), 0)

    def test_append_enabled_does_not_duplicate(self) -> None:
        cfg = self.home / "config.toml"
        cfg.write_text("[plugins]\nenabled = [\n    \"ruflo-core\",\n]\n", encoding="utf-8")
        ebttrt.append_enabled_plugin()
        ebttrt.append_enabled_plugin()
        text = cfg.read_text(encoding="utf-8")
        self.assertEqual(text.count('"ebttrt"'), 1)

    def test_world_writable_flagged(self) -> None:
        target = self.home / "open.sh"
        target.write_text("echo hi\n", encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IWOTH)
        findings = ebttrt.scan_file(target)
        self.assertTrue(any(f["rule"] == "world-writable" for f in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
