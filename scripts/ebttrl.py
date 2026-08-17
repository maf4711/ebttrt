#!/usr/bin/env python3
"""ebttrl CLI — even better than the real thing."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ebttrl_lib import (  # noqa: F401 — re-export for tests
    LOOP,
    MAX_CONTEXT_CHARS,
    VERSION,
    cmd_improve,
    cmd_instincts,
    cmd_receipt_last,
    cmd_receipt_write,
    cmd_remember,
    cmd_shield,
    declared_versions,
    data_home,
    deny_reason,
    ensure_dirs,
    grade,
    grok_home,
    hook_posttool,
    hook_precompact,
    hook_pretool,
    hook_session_end,
    hook_session_start,
    hook_stop,
    load_event,
    plugin_root,
    read_jsonl,
    scan_file,
)
from ebttrl_loop import (
    append_memory,
    clear_active,
    cmd_abort,
    cmd_begin,
    cmd_next,
    cmd_phase,
    format_loop,
    journal,
    load_active,
    receipts_for,
    workspace_slug,
)
from ebttrl_activate import cmd_activate
from ebttrl_review import cmd_review, review_blocker
from ebttrl_prove import (
    DEFAULT_TIMEOUT,
    cmd_consult,
    cmd_prove,
    cmd_receipt_check,
    evidence_line,
    load_last_prove,
    prove_is_fresh,
)

MIN_SKILLS = 10
MIN_GROK_SKILLS = 9


def cmd_status() -> int:
    home = ensure_dirs()
    root = plugin_root()
    rule = grok_home() / "rules" / "ebttrl-loop.md"
    plugin_link = grok_home() / "plugins" / "ebttrl"
    cwd = Path.cwd()
    print(f"ebttrl {VERSION}")
    print(f"plugin:   {root}")
    print(f"data:     {home}")
    print(f"rule:     {'yes' if rule.exists() else 'MISSING'} ({rule})")
    print(f"link:     {'yes' if plugin_link.exists() else 'MISSING'} ({plugin_link})")
    print(f"receipts: {len(list((home / 'receipts').glob('*.json')))}")
    print(f"instincts:{len(read_jsonl(home / 'instincts.jsonl'))}")
    print("loop:     " + " → ".join(LOOP))
    active = load_active(cwd)
    if active:
        print(format_loop(active))
    else:
        print("active:   none")
    ctx = home / "current-context.md"
    if ctx.exists():
        print(f"context:  {ctx} ({ctx.stat().st_size} bytes)")
    return 0


def cmd_dashboard() -> int:
    cmd_status()
    print()
    return cmd_next(Path.cwd())


def inspect_plugin() -> dict | None:
    try:
        out = subprocess.run(
            ["grok", "inspect", "--json"],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    for plugin in data.get("plugins") or []:
        if plugin.get("name") == "ebttrl":
            return plugin
    return None


def cmd_doctor() -> int:
    root = plugin_root()
    issues: list[str] = []
    for rel in (
        "plugin.json",
        "skills/ebttrl/SKILL.md",
        "hooks/hooks.json",
        "rules/ebttrl-loop.md",
        "scripts/ebttrl.py",
        "scripts/ebttrl_loop.py",
        "scripts/ebttrl_prove.py",
        "scripts/ebttrl_activate.py",
        "scripts/ebttrl_review.py",
        "skills/ebttrl-activate/SKILL.md",
    ):
        if not (root / rel).exists():
            issues.append(f"missing {rel}")
    disk_skills = 0
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        disk_skills = sum(
            1 for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()
        )
    if disk_skills < MIN_SKILLS:
        issues.append(f"plugin has {disk_skills} skills, expected >= {MIN_SKILLS}")
    rule = grok_home() / "rules" / "ebttrl-loop.md"
    if not rule.exists():
        issues.append(f"always-on rule not installed: {rule}")
    link = grok_home() / "plugins" / "ebttrl"
    if not link.exists():
        issues.append(f"plugin not linked at {link}")
    cli = grok_home() / "bin" / "ebttrl"
    if not cli.exists():
        issues.append(f"CLI not on PATH via {cli}")
    file_v, plug_v, code_v = declared_versions(root)
    if not file_v or {file_v, plug_v, code_v} != {file_v}:
        issues.append(f"version drift VERSION={file_v!r} plugin.json={plug_v!r} code={code_v!r}")
    if link.exists() and not link.is_symlink():
        issues.append(f"plugin at {link} is not a symlink")
    elif link.is_symlink() and link.resolve() != root.resolve():
        issues.append(f"plugin symlink {link} → {link.resolve()} != {root}")
    isolated = Path(os.environ.get("GROK_HOME") or grok_home()) != (Path.home() / ".grok")
    plugin = None if isolated else inspect_plugin()
    if not isolated:
        if plugin is None:
            issues.append("grok inspect did not list plugin ebttrl (new session / press r)")
        else:
            if not plugin.get("enabled", True):
                issues.append("plugin ebttrl is disabled")
            skills = (plugin.get("provides") or {}).get("skills")
            if isinstance(skills, int) and skills < MIN_GROK_SKILLS:
                issues.append(f"grok sees {skills} ebttrl skills, expected {MIN_GROK_SKILLS}+")
    if issues:
        print("ebttrl doctor: FAIL")
        for item in issues:
            print(f"  - {item}")
        print("fix:  ebttrl activate")
        return 1
    print("ebttrl doctor: OK")
    print(f"  plugin {root}")
    print(f"  data   {data_home()}")
    print(f"  rule   {rule}")
    print(f"  skills {disk_skills}")
    print(f"  version {code_v}")
    meta = data_home() / "last-context.json"
    if meta.is_file():
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
            print(f"  card    {info.get('at')} inject={info.get('inject_bytes')} disk={info.get('disk_bytes')}")
        except json.JSONDecodeError:
            pass
    if plugin:
        print(f"  grok   enabled, {plugin.get('provides')}")
        seen = (plugin.get("provides") or {}).get("skills")
        if isinstance(seen, int) and seen < disk_skills:
            print(f"  note   grok inspect sees {seen} skills, disk has {disk_skills} — press r")
    return 0


def cmd_loop() -> int:
    print("even better than the real thing")
    print(" → ".join(LOOP))
    print()
    print("plan     write the blueprint before code")
    print("test     failing test first when behavior changes")
    print("implement smallest change that satisfies the test")
    print("review   fresh-context review of the actual diff")
    print("verify   run the project's prove command; evidence before claims")
    print("remember write a receipt bound to HEAD or a dirty snapshot")
    print("improve  promote a repeated win into a skill, not another rule line")
    return 0


def cmd_context() -> int:
    cwd = Path.cwd()
    scoped = data_home() / "workspaces" / workspace_slug(cwd) / "context.md"
    path = scoped if scoped.exists() else data_home() / "current-context.md"
    if not path.exists():
        print("(no ebttrl context yet — start a Grok session or run ebttrl begin)")
        return 0
    sys.stdout.write(path.read_text(encoding="utf-8"))
    return 0


def cmd_done(evidence: str, cwd: Path) -> int:
    active = load_active(cwd)
    if not active:
        print("no open loop — ebttrl begin \"goal\"", file=sys.stderr)
        return 1
    last = load_last_prove(cwd)
    if not last or not last.get("ok") or not prove_is_fresh(cwd, last):
        print("need a fresh passing `ebttrl prove`", file=sys.stderr)
        return 1
    block = review_blocker(cwd)
    if block:
        print(block, file=sys.stderr)
        return 1
    ev = evidence or str(active.get("evidence") or "") or evidence_line(last)
    phase = str(active.get("phase") or "")
    if phase in {"plan", "test", "implement", "review"}:
        if cmd_phase("verify", cwd, ev) != 0:
            return 1
    elif phase == "verify":
        cmd_phase("verify", cwd, ev)
    active = load_active(cwd) or active
    goal = str(active.get("goal") or "loop")
    rc = cmd_receipt_write(goal, ev, ["verify", "remember"], cwd)
    if rc != 0:
        return rc
    journal(cwd, "done", goal=goal, evidence=ev)
    append_memory(cwd, goal, ev)
    clear_active(cwd)
    print("loop closed")
    return 0


def cmd_eval() -> int:
    root = plugin_root()
    tests = root / "tests"
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-q"],
        cwd=root,
        check=False,
    )
    print(f"eval: {'OK' if proc.returncode == 0 else 'FAIL'}  unittest discover -s tests")
    return proc.returncode


def append_enabled_plugin() -> None:
    cfg = grok_home() / "config.toml"
    if not cfg.exists():
        cfg.write_text('[plugins]\nenabled = ["ebttrl"]\n', encoding="utf-8")
        return
    text = cfg.read_text(encoding="utf-8")
    if re.search(r'(?m)^\s*"ebttrl"\s*,?\s*$', text):
        return
    if "[plugins]" not in text:
        cfg.write_text(text.rstrip() + '\n\n[plugins]\nenabled = ["ebttrl"]\n', encoding="utf-8")
        return
    updated, n = re.subn(
        r"(\[plugins\][^\[]*enabled\s*=\s*\[)",
        r'\1\n    "ebttrl",',
        text,
        count=1,
    )
    if n:
        cfg.write_text(updated, encoding="utf-8")


def cmd_install() -> int:
    root = plugin_root()
    home = grok_home()
    (home / "plugins").mkdir(parents=True, exist_ok=True)
    (home / "rules").mkdir(parents=True, exist_ok=True)
    (home / "bin").mkdir(parents=True, exist_ok=True)
    ensure_dirs()
    link = home / "plugins" / "ebttrl"
    if link.is_symlink() or link.exists():
        if link.is_symlink() or link.is_file():
            link.unlink()
        else:
            print(f"refusing to replace non-symlink {link}", file=sys.stderr)
            return 1
    link.symlink_to(root)
    rule_dst = home / "rules" / "ebttrl-loop.md"
    rule_dst.write_text((root / "rules" / "ebttrl-loop.md").read_text(encoding="utf-8"), encoding="utf-8")
    cli = home / "bin" / "ebttrl"
    if cli.is_symlink() or cli.exists():
        cli.unlink()
    cli.symlink_to(root / "scripts" / "ebttrl.py")
    cli.chmod(cli.stat().st_mode | stat.S_IXUSR)
    append_enabled_plugin()
    print(f"installed plugin → {link}")
    print(f"installed rule   → {rule_dst}")
    print(f"installed cli    → {cli}")
    print("reload Grok plugins (r in Plugins tab) or start a new session")
    return cmd_doctor()


def cmd_uninstall() -> int:
    home = grok_home()
    for path in (home / "plugins" / "ebttrl", home / "bin" / "ebttrl", home / "rules" / "ebttrl-loop.md"):
        if path.is_symlink() or path.is_file():
            path.unlink()
            print(f"removed {path}")
        elif path.exists():
            print(f"left in place (not a file/symlink): {path}")
    print("data kept at", data_home(), "(delete manually if you want it gone)")
    return 0


def cmd_receipt_last_workspace(cwd: Path) -> int:
    rows = receipts_for(workspace_slug(cwd), 1)
    if rows:
        rec = {k: v for k, v in rows[0].items() if k != "_path"}
        sys.stdout.write(json.dumps(rec, indent=2) + "\n")
        return 0
    return cmd_receipt_last()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ebttrl", description="Even Better Than The Real Thing")
    p.add_argument("--version", action="version", version=f"ebttrl {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=False)
    for name, help_ in (
        ("status", "show install + open loop"),
        ("doctor", "check plugin, rule, CLI, grok inspect"),
        ("loop", "print the engineering loop"),
        ("context", "print workspace context card"),
        ("install", "link plugin + rule + CLI into ~/.grok"),
        ("activate", "install + PATH + activate skill + Hoheit wiring"),
        ("uninstall", "remove plugin link, rule, CLI"),
        ("instincts", "list stored instincts"),
        ("improve", "list earned instincts only"),
        ("next", "show the next legal phase"),
        ("abort", "drop the open loop without a receipt"),
        ("eval", "run the ebttrl unit suite"),
    ):
        sub.add_parser(name, help=help_)
    beg = sub.add_parser("begin", help="open a loop")
    beg.add_argument("goal", nargs="+")
    beg.add_argument("--phase", default="plan")
    ph = sub.add_parser("phase", help="advance the open loop")
    ph.add_argument("name", choices=list(LOOP))
    ph.add_argument("--evidence", default="")
    prv = sub.add_parser("prove", help="discover and run the workspace test command")
    prv.add_argument("--record", action="store_true", help="mark verify on success")
    prv.add_argument("--timeout", type=int, default=0)
    con = sub.add_parser("consult", help="recommend start phase, skill, prove command")
    con.add_argument("text", nargs="+")
    dn = sub.add_parser("done", help="verify + receipt + close")
    dn.add_argument("--evidence", default="")
    rem = sub.add_parser("remember", help="store an instinct")
    rem.add_argument("text", nargs="+")
    rem.add_argument("--workspace", default="*")
    rem.add_argument("--confidence", type=float, default=0.6)
    rem.add_argument("--force", action="store_true")
    rev = sub.add_parser("review", help="write a review snapshot for this tree")
    rev.add_argument("--verdict", choices=("approve", "revise"), default="approve")
    rev.add_argument("--finding", action="append", default=[])
    rec = sub.add_parser("receipt", help="bind a completed loop to source state")
    rec_sub = rec.add_subparsers(dest="receipt_cmd", required=True)
    rec_sub.add_parser("last")
    rec_sub.add_parser("check")
    rec_w = rec_sub.add_parser("write")
    rec_w.add_argument("--goal", required=True)
    rec_w.add_argument("--evidence", default="")
    rec_w.add_argument("--phases", default="")
    rec_w.add_argument("--cwd", default=".")
    sh = sub.add_parser("shield", help="scan a tree for secrets and dangerous commands")
    sh.add_argument("path", nargs="?", default=".")
    hk = sub.add_parser("hook", help="internal: Grok lifecycle hook")
    hk.add_argument(
        "name",
        choices=("session-start", "session-end", "pretool", "posttool", "stop", "precompact"),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cwd = Path.cwd()
    if not args.cmd:
        return cmd_dashboard()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "doctor":
        return cmd_doctor()
    if args.cmd == "loop":
        return cmd_loop()
    if args.cmd == "context":
        return cmd_context()
    if args.cmd == "install":
        return cmd_install()
    if args.cmd == "activate":
        return cmd_activate()
    if args.cmd == "uninstall":
        return cmd_uninstall()
    if args.cmd == "instincts":
        return cmd_instincts()
    if args.cmd == "improve":
        return cmd_improve(cwd)
    if args.cmd == "review":
        return cmd_review(cwd, args.verdict, args.finding)
    if args.cmd == "begin":
        return cmd_begin(" ".join(args.goal), cwd, args.phase)
    if args.cmd == "phase":
        return cmd_phase(args.name, cwd, args.evidence)
    if args.cmd == "next":
        return cmd_next(cwd)
    if args.cmd == "abort":
        return cmd_abort(cwd)
    if args.cmd == "prove":
        return cmd_prove(cwd, record=args.record, timeout=args.timeout or DEFAULT_TIMEOUT)
    if args.cmd == "consult":
        return cmd_consult(" ".join(args.text), cwd)
    if args.cmd == "eval":
        return cmd_eval()
    if args.cmd == "done":
        return cmd_done(args.evidence, cwd)
    if args.cmd == "remember":
        return cmd_remember(
            " ".join(args.text), args.workspace, args.confidence, cwd, args.force
        )
    if args.cmd == "receipt":
        if args.receipt_cmd == "last":
            return cmd_receipt_last_workspace(cwd)
        if args.receipt_cmd == "check":
            return cmd_receipt_check(cwd)
        phases = [p.strip() for p in args.phases.split(",") if p.strip()]
        return cmd_receipt_write(args.goal, args.evidence, phases, Path(args.cwd))
    if args.cmd == "shield":
        return cmd_shield(Path(args.path))
    if args.cmd == "hook":
        event = load_event()
        if args.name == "session-start":
            return hook_session_start(event)
        if args.name == "session-end":
            return hook_session_end(event)
        if args.name == "posttool":
            return hook_posttool(event)
        if args.name == "stop":
            return hook_stop(event)
        if args.name == "precompact":
            return hook_precompact(event)
        return hook_pretool(event)
    return 2


if __name__ == "__main__":
    sys.exit(main())
