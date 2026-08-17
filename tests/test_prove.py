#!/usr/bin/env python3
"""Prove, consult, receipt-check, memory, session inject."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ebttrl  # noqa: E402
import ebttrl_loop  # noqa: E402
import ebttrl_prove  # noqa: E402


class Tmp(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["GROK_HOME"] = str(self.home)
        os.environ["EBTTRL_HOME"] = str(self.home / "ebttrl")
        os.environ["GROK_PLUGIN_ROOT"] = str(ROOT)
        self.cwd = self.home / "app"
        self.cwd.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()


class DiscoverTests(Tmp):
    def test_config_file_wins(self) -> None:
        (self.cwd / ".ebttrl.json").write_text('{"prove": "python3 -c \'print(1)\'"}\n', encoding="utf-8")
        argv, via = ebttrl_prove.discover_prove(self.cwd)
        self.assertEqual(via, ".ebttrl.json")
        self.assertEqual(argv[0][:1], ["python3"])

    def test_package_json_test_script(self) -> None:
        (self.cwd / "package.json").write_text('{"scripts": {"test": "node test.js"}}\n', encoding="utf-8")
        argv, via = ebttrl_prove.discover_prove(self.cwd)
        self.assertEqual(argv, [["npm", "test"]])
        self.assertIn("package.json", via)

    def test_tests_directory(self) -> None:
        tests = self.cwd / "tests"
        tests.mkdir()
        (tests / "test_x.py").write_text("import unittest\n", encoding="utf-8")
        argv, via = ebttrl_prove.discover_prove(self.cwd)
        self.assertEqual(via, "tests/")
        self.assertIn("unittest", argv[0])

    def test_missing_prove_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            ebttrl_prove.discover_prove(self.cwd)


class ProveRunTests(Tmp):
    def test_prove_ok_and_record(self) -> None:
        (self.cwd / ".ebttrl.json").write_text(
            '{"prove": "python3 -c \\"print(\'ok\')\\""}\n',
            encoding="utf-8",
        )
        ebttrl_loop.cmd_begin("demo", self.cwd, "implement")
        buf = StringIO()
        with redirect_stdout(buf):
            rc = ebttrl_prove.cmd_prove(self.cwd, record=True)
        self.assertEqual(rc, 0)
        rec = ebttrl_prove.load_last_prove(self.cwd)
        assert rec is not None
        self.assertTrue(rec["ok"])
        self.assertTrue(ebttrl_prove.prove_is_fresh(self.cwd, rec))
        active = ebttrl_loop.load_active(self.cwd)
        assert active is not None
        self.assertTrue(active["verified"])
        self.assertEqual(active["phase"], "verify")

    def test_prove_fail(self) -> None:
        (self.cwd / ".ebttrl.json").write_text(
            '{"prove": "python3 -c \\"raise SystemExit(2)\\""}\n',
            encoding="utf-8",
        )
        rc = ebttrl_prove.cmd_prove(self.cwd)
        self.assertEqual(rc, 1)
        rec = ebttrl_prove.load_last_prove(self.cwd)
        assert rec is not None
        self.assertFalse(rec["ok"])

    def test_done_reuses_fresh_prove(self) -> None:
        (self.cwd / ".ebttrl.json").write_text(
            '{"prove": "python3 -c \\"print(1)\\""}\n',
            encoding="utf-8",
        )
        ebttrl_loop.cmd_begin("demo", self.cwd, "implement")
        self.assertEqual(ebttrl_prove.cmd_prove(self.cwd), 0)
        self.assertEqual(ebttrl.cmd_done("", self.cwd), 0)
        self.assertIsNone(ebttrl_loop.load_active(self.cwd))
        mem = self.home / "ebttrl" / "MEMORY.md"
        self.assertTrue(mem.exists())
        self.assertIn("demo", mem.read_text(encoding="utf-8"))

    def test_consult_bug_starts_at_test(self) -> None:
        (self.cwd / ".ebttrl.json").write_text('{"prove": "true"}\n', encoding="utf-8")
        buf = StringIO()
        with redirect_stdout(buf):
            ebttrl_prove.cmd_consult("fix the login bug", self.cwd)
        self.assertIn("start:   test", buf.getvalue())


class ReceiptCheckTests(Tmp):
    def test_match_then_drift(self) -> None:
        subprocess.run(["git", "init"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.cwd, check=True, capture_output=True)
        (self.cwd / "f").write_text("a\n", encoding="utf-8")
        subprocess.run(["git", "add", "f"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "i"],
            cwd=self.cwd,
            check=True,
            capture_output=True,
        )
        ebttrl.cmd_receipt_write("snap", "true", ["verify"], self.cwd)
        self.assertEqual(ebttrl_prove.cmd_receipt_check(self.cwd), 0)
        (self.cwd / "f").write_text("b\n", encoding="utf-8")
        self.assertEqual(ebttrl_prove.cmd_receipt_check(self.cwd), 1)


class InjectTests(Tmp):
    def test_session_start_emits_additional_context(self) -> None:
        buf = StringIO()
        with redirect_stdout(buf):
            ebttrl.hook_session_start(
                {"workspaceRoot": str(self.cwd), "cwd": str(self.cwd), "sessionId": "s"}
            )
        payload = json.loads(buf.getvalue())
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ebttrl context", ctx)
        self.assertNotIn("## Journal", ctx)
        self.assertNotIn("## Instincts", ctx)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")


if __name__ == "__main__":
    unittest.main(verbosity=2)
