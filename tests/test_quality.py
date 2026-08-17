#!/usr/bin/env python3
"""Q1–Q5 quality gates: prove chain, instincts, review, inject, versions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ebttrl  # noqa: E402
import ebttrl_lib  # noqa: E402
import ebttrl_loop  # noqa: E402
import ebttrl_prove  # noqa: E402
import ebttrl_review  # noqa: E402


class Tmp(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["GROK_HOME"] = str(self.home)
        os.environ["EBTTRL_HOME"] = str(self.home / "ebttrl")
        os.environ["GROK_PLUGIN_ROOT"] = str(ROOT)
        os.environ.pop("EBTTRL_ROOT", None)
        os.environ["HOHEIT_ROOT"] = str(self.home / "missing-hoheit")
        self.cwd = self.home / "app"
        self.cwd.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def git_init(self) -> None:
        subprocess.run(["git", "init"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.cwd, check=True, capture_output=True)

    def commit(self, name: str, body: str) -> None:
        (self.cwd / name).write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", name], cwd=self.cwd, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", name],
            cwd=self.cwd,
            check=True,
            capture_output=True,
        )


class ProveQuality(Tmp):
    def test_multi_command_chain(self) -> None:
        (self.cwd / ".ebttrl.json").write_text(
            json.dumps({"prove": ['python3 -c "print(1)"', 'python3 -c "print(2)"']}),
            encoding="utf-8",
        )
        chain, via = ebttrl_prove.discover_prove(self.cwd)
        self.assertEqual(via, ".ebttrl.json")
        self.assertEqual(len(chain), 2)
        rec = ebttrl_prove.run_prove(self.cwd)
        self.assertTrue(rec["ok"])
        self.assertEqual(len(rec["steps"]), 2)

    def test_chain_stops_on_fail(self) -> None:
        (self.cwd / ".ebttrl.json").write_text(
            json.dumps({"prove": ['python3 -c "raise SystemExit(2)"', 'python3 -c "print(1)"']}),
            encoding="utf-8",
        )
        rec = ebttrl_prove.run_prove(self.cwd)
        self.assertFalse(rec["ok"])
        self.assertEqual(len(rec["steps"]), 1)

    def test_stale_digest_blocks_done(self) -> None:
        self.git_init()
        self.commit("a", "1\n")
        (self.cwd / ".ebttrl.json").write_text(
            '{"prove": "python3 -c \\"print(1)\\""}\n', encoding="utf-8"
        )
        ebttrl_loop.cmd_begin("y", self.cwd, "implement")
        self.assertEqual(ebttrl_prove.cmd_prove(self.cwd), 0)
        (self.cwd / "a").write_text("2\n", encoding="utf-8")
        err = StringIO()
        with redirect_stderr(err):
            rc = ebttrl.cmd_done("", self.cwd)
        self.assertEqual(rc, 1)
        self.assertIn("fresh passing", err.getvalue())

    def test_missing_prove_blocks_done(self) -> None:
        ebttrl_loop.cmd_begin("x", self.cwd, "implement")
        err = StringIO()
        with redirect_stderr(err):
            rc = ebttrl.cmd_done("hand-waved", self.cwd)
        self.assertEqual(rc, 1)
        self.assertIn("fresh passing", err.getvalue())

    def test_consult_warns_weak_prove(self) -> None:
        (self.cwd / ".ebttrl.json").write_text('{"prove": "true"}\n', encoding="utf-8")
        buf = StringIO()
        with redirect_stdout(buf):
            ebttrl_prove.cmd_consult("plan oauth", self.cwd)
        self.assertIn("no-op", buf.getvalue())


class InstinctQuality(Tmp):
    def test_remember_without_receipt_fails(self) -> None:
        rc = ebttrl.cmd_remember("keep safari default", "*", 0.8, self.cwd, force=False)
        self.assertEqual(rc, 1)

    def test_first_low_second_promotes(self) -> None:
        ebttrl.cmd_receipt_write("one", "true", ["verify"], self.cwd)
        ebttrl.cmd_receipt_write("two", "true", ["verify"], self.cwd)
        self.assertEqual(ebttrl.cmd_remember("keep safari default", "*", 0.8, self.cwd), 0)
        rows = ebttrl.read_jsonl(self.home / "ebttrl" / "instincts.jsonl")
        self.assertLessEqual(rows[-1]["confidence"], 0.5)
        self.assertEqual(ebttrl.cmd_remember("keep safari default", "*", 0.8, self.cwd), 0)
        rows = ebttrl.read_jsonl(self.home / "ebttrl" / "instincts.jsonl")
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]["confidence"], 0.5)
        buf = StringIO()
        with redirect_stdout(buf):
            ebttrl.cmd_improve(self.cwd)
        self.assertIn("keep safari default", buf.getvalue())

    def test_secret_instinct_refused(self) -> None:
        rc = ebttrl.cmd_remember('API_KEY = "sk-not-a-real-key-xx"', "*", 0.5, self.cwd, force=True)
        self.assertEqual(rc, 2)


class ReviewQuality(Tmp):
    def test_revise_high_blocks_done(self) -> None:
        self.git_init()
        self.commit("a.py", "x\n")
        self.commit("b.py", "y\n")
        (self.cwd / "a.py").write_text("xx\n", encoding="utf-8")
        (self.cwd / "b.py").write_text("yy\n", encoding="utf-8")
        (self.cwd / ".ebttrl.json").write_text(
            '{"prove": "python3 -c \\"print(1)\\""}\n', encoding="utf-8"
        )
        ebttrl_loop.cmd_begin("multi", self.cwd, "implement")
        self.assertEqual(ebttrl_prove.cmd_prove(self.cwd), 0)
        self.assertTrue(ebttrl_review.review_required(self.cwd))
        ebttrl_review.cmd_review(self.cwd, "revise", ["high:a.py:leak"])
        err = StringIO()
        with redirect_stderr(err):
            rc = ebttrl.cmd_done("", self.cwd)
        self.assertEqual(rc, 1)
        self.assertIn("revise", err.getvalue())

    def test_approve_same_digest_allows(self) -> None:
        self.git_init()
        self.commit("a.py", "x\n")
        self.commit("b.py", "y\n")
        (self.cwd / "a.py").write_text("xx\n", encoding="utf-8")
        (self.cwd / "b.py").write_text("yy\n", encoding="utf-8")
        (self.cwd / ".ebttrl.json").write_text(
            '{"prove": "python3 -c \\"print(1)\\""}\n', encoding="utf-8"
        )
        ebttrl_loop.cmd_begin("multi", self.cwd, "implement")
        self.assertEqual(ebttrl_prove.cmd_prove(self.cwd), 0)
        ebttrl_review.cmd_review(self.cwd, "approve", [])
        self.assertEqual(ebttrl.cmd_done("", self.cwd), 0)

    def test_dirty_after_review_is_drift(self) -> None:
        self.git_init()
        self.commit("a.py", "x\n")
        self.commit("b.py", "y\n")
        (self.cwd / "a.py").write_text("xx\n", encoding="utf-8")
        (self.cwd / "b.py").write_text("yy\n", encoding="utf-8")
        ebttrl_review.cmd_review(self.cwd, "approve", [])
        (self.cwd / "a.py").write_text("xxx\n", encoding="utf-8")
        self.assertIsNotNone(ebttrl_review.review_blocker(self.cwd))
        self.assertIn("drifted", ebttrl_review.review_blocker(self.cwd) or "")


class ContextQuality(Tmp):
    def test_inject_caps_and_omits_journal(self) -> None:
        ebttrl_loop.cmd_begin("auth", self.cwd, "implement")
        for i in range(20):
            ebttrl_loop.journal(self.cwd, "phase", phase="implement", n=i)
        event = {"workspaceRoot": str(self.cwd), "cwd": str(self.cwd), "sessionId": "s"}
        full = ebttrl_loop.write_session_context(event)
        inject = ebttrl_loop.inject_session_context(event)
        self.assertIn("## Journal", full)
        self.assertNotIn("## Journal", inject)
        self.assertNotIn("## Instincts", inject)
        self.assertLessEqual(len(inject), ebttrl_lib.INJECT_CONTEXT_CHARS)
        self.assertIn("auth", inject)
        meta = json.loads((self.home / "ebttrl" / "last-context.json").read_text(encoding="utf-8"))
        self.assertLessEqual(int(meta["inject_bytes"]), ebttrl_lib.INJECT_CONTEXT_CHARS)


class VersionQuality(Tmp):
    def test_declared_versions_match(self) -> None:
        file_v, plug_v, code_v = ebttrl_lib.declared_versions(ROOT)
        self.assertEqual(file_v, plug_v)
        self.assertEqual(file_v, code_v)
        self.assertEqual(code_v, "0.8.0")

    def test_doctor_symlink_and_version(self) -> None:
        self.assertEqual(ebttrl.cmd_install(), 0)
        self.assertEqual(ebttrl.cmd_doctor(), 0)
        link = self.home / "plugins" / "ebttrl"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), ROOT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
