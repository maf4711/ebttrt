#!/usr/bin/env python3
"""Activate on a fresh Mac: discovery, portable MCP, no foreign /Users paths."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ebttrt  # noqa: E402
import ebttrt_activate as act  # noqa: E402


class Tmp(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            key: os.environ.get(key)
            for key in (
                "GROK_HOME",
                "EBTTRT_HOME",
                "GROK_PLUGIN_ROOT",
                "EBTTRT_ROOT",
                "HOHEIT_ROOT",
                "EBTTRT_ZSHRC",
            )
        }
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["GROK_HOME"] = str(self.home)
        os.environ["EBTTRT_HOME"] = str(self.home / "ebttrt")
        os.environ["GROK_PLUGIN_ROOT"] = str(ROOT)
        os.environ.pop("EBTTRT_ROOT", None)
        self.hoheit = self.home / "hoheit"
        (self.hoheit / "scripts").mkdir(parents=True)
        (self.hoheit / "apps" / "kernel").mkdir(parents=True)
        (self.hoheit / "scripts" / "hoheit").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.hoheit / "scripts" / "hoheit-mcp").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.hoheit / "scripts" / "hoheit-prove").write_text("#!/bin/sh\n", encoding="utf-8")
        os.environ["HOHEIT_ROOT"] = str(self.hoheit)
        os.environ["EBTTRT_ZSHRC"] = str(self.home / "zshrc")

    def tearDown(self) -> None:
        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        self.tmp.cleanup()


class DiscoveryTests(Tmp):
    def test_env_override_exclusive_miss(self) -> None:
        os.environ["EBTTRT_ROOT"] = str(self.home / "missing")
        self.assertIsNone(act.find_ebttrt())

    def test_env_override_hit(self) -> None:
        os.environ["EBTTRT_ROOT"] = str(ROOT)
        self.assertEqual(act.find_ebttrt(), ROOT)

    def test_hoheit_env_exclusive_miss(self) -> None:
        os.environ["HOHEIT_ROOT"] = str(self.home / "nope")
        self.assertIsNone(act.find_hoheit())

    def test_looks_like(self) -> None:
        self.assertTrue(act.looks_like_ebttrt(ROOT))
        self.assertTrue(act.looks_like_hoheit(self.hoheit))
        self.assertFalse(act.looks_like_hoheit(self.home))


class PortableTests(Tmp):
    def test_home_relative_uses_dollar_home(self) -> None:
        path = Path.home() / "Developer" / "hoheit" / "scripts" / "hoheit-mcp"
        self.assertEqual(
            act.portable_command(path),
            "${HOME}/Developer/hoheit/scripts/hoheit-mcp",
        )

    def test_outside_home_stays_absolute(self) -> None:
        path = self.hoheit / "scripts" / "hoheit-mcp"
        cmd = act.portable_command(path)
        self.assertTrue(cmd.startswith("/"))
        self.assertNotIn("/Users/a321", cmd)

    def test_project_mcp_is_relative(self) -> None:
        note = act.write_hoheit_project_mcp(self.hoheit)
        text = (self.hoheit / ".grok" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('command = "scripts/hoheit-mcp"', text)
        self.assertNotIn("/Users/", text)
        self.assertTrue("updated" in note or "wrote" in note, note)


class ActivateTests(Tmp):
    def test_missing_repo_exits_2(self) -> None:
        os.environ["EBTTRT_ROOT"] = str(self.home / "missing")
        err = StringIO()
        with redirect_stderr(err):
            rc = act.cmd_activate()
        self.assertEqual(rc, 2)
        self.assertIn("not found", err.getvalue())

    def test_activate_wires_plugin_skill_path_hoheit(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            rc = ebttrt.main(["activate"])
        self.assertEqual(rc, 0, out.getvalue())
        self.assertTrue((self.home / "plugins" / "ebttrt").is_symlink())
        self.assertTrue((self.home / "rules" / "ebttrt-loop.md").is_file())
        self.assertTrue((self.home / "bin" / "ebttrt").exists())
        skill = self.home / "skills" / "ebttrt-activate" / "SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertIn("ebttrt-activate", skill.read_text(encoding="utf-8"))
        zsh = (self.home / "zshrc").read_text(encoding="utf-8")
        self.assertIn(act.ZSH_PATH_LINE, zsh)
        project = (self.hoheit / ".grok" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('command = "scripts/hoheit-mcp"', project)
        user = (self.home / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.hoheit]", user)
        self.assertIn("hoheit-mcp", user)
        self.assertNotIn("/Users/a321", user)
        self.assertTrue(os.access(self.hoheit / "scripts" / "hoheit-prove", os.X_OK))
        self.assertTrue((self.hoheit / ".ebttrt.json").is_file())

    def test_activate_is_idempotent(self) -> None:
        self.assertEqual(act.cmd_activate(), 0)
        self.assertEqual(act.cmd_activate(), 0)
        zsh = (self.home / "zshrc").read_text(encoding="utf-8")
        self.assertEqual(zsh.count(act.ZSH_PATH_LINE), 1)

    def test_isolated_home_skips_real_zshrc(self) -> None:
        os.environ.pop("EBTTRT_ZSHRC", None)
        note = act.ensure_zsh_path()
        self.assertIn("isolated", note)

    def test_source_has_no_hardcoded_user(self) -> None:
        text = (ROOT / "scripts" / "ebttrt_activate.py").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", text)
        skill = (ROOT / "skills" / "ebttrt-activate" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("/Users/a321", skill)
        self.assertNotIn("/Users/", skill)


if __name__ == "__main__":
    unittest.main(verbosity=2)
