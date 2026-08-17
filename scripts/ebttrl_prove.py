"""Discover and run the workspace prove command. Stdlib only."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from ebttrl_lib import now_iso, source_state
from ebttrl_loop import cmd_phase, journal, load_active, workspace_dir

DEFAULT_TIMEOUT = int(os.environ.get("EBTTRL_PROVE_TIMEOUT", "180"))
TAIL_LINES = 20
STORED_OUT = 8000


def load_config(cwd: Path) -> dict[str, Any]:
    for name in (".ebttrl.json", "ebttrl.json"):
        path = cwd / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _argv(command: str | list[str]) -> list[str]:
    if isinstance(command, list):
        return [str(p) for p in command]
    return shlex.split(command)


def parse_prove_commands(raw: Any) -> list[list[str]]:
    if isinstance(raw, str):
        return [_argv(raw)]
    if isinstance(raw, list) and raw:
        if all(isinstance(x, list) for x in raw):
            return [[str(p) for p in x] for x in raw]
        if all(isinstance(x, str) for x in raw):
            if len(raw) > 1 and all(" " not in x for x in raw):
                return [list(raw)]
            return [_argv(x) for x in raw]
    raise ValueError("prove must be a string or list of commands")


def prove_is_weak(chain: list[list[str]]) -> bool:
    if len(chain) != 1:
        return False
    argv = chain[0]
    if argv in (["true"], [":"]):
        return True
    if argv[:1] == ["echo"] and len(argv) <= 2:
        return True
    return False


def discover_prove(cwd: Path) -> tuple[list[list[str]], str]:
    cfg = load_config(cwd)
    if cfg.get("prove"):
        try:
            return parse_prove_commands(cfg["prove"]), ".ebttrl.json"
        except ValueError as exc:
            raise FileNotFoundError(str(exc)) from exc

    pkg = cwd / "package.json"
    if pkg.is_file():
        try:
            scripts = (json.loads(pkg.read_text(encoding="utf-8")) or {}).get("scripts") or {}
        except json.JSONDecodeError:
            scripts = {}
        if isinstance(scripts, dict) and scripts.get("test"):
            return [["npm", "test"]], "package.json#scripts.test"

    if (cwd / "Cargo.toml").is_file():
        return [["cargo", "test"]], "Cargo.toml"
    if (cwd / "go.mod").is_file():
        return [["go", "test", "./..."]], "go.mod"

    pyproject = cwd / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        if "[tool.pytest" in text or "pytest" in text:
            return [[sys.executable, "-m", "pytest"]], "pyproject.toml"

    makefile = cwd / "Makefile"
    if makefile.is_file() and re.search(r"^test:", makefile.read_text(encoding="utf-8", errors="replace"), re.M):
        return [["make", "test"]], "Makefile"

    tests_dir = cwd / "tests"
    if tests_dir.is_dir() and any(tests_dir.glob("test_*.py")):
        return [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]], "tests/"

    if (cwd / "test_ebttrl.py").is_file():
        return [[sys.executable, "test_ebttrl.py"]], "test_ebttrl.py"

    raise FileNotFoundError(
        "no prove command — add {\"prove\": \"…\"} to .ebttrl.json"
    )


def last_prove_path(cwd: Path) -> Path:
    return workspace_dir(cwd) / "last-prove.json"


def load_last_prove(cwd: Path) -> dict[str, Any] | None:
    path = last_prove_path(cwd)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def prove_is_fresh(cwd: Path, rec: dict[str, Any] | None = None) -> bool:
    rec = rec if rec is not None else load_last_prove(cwd)
    if not rec or not rec.get("ok"):
        return False
    src = source_state(cwd)
    return rec.get("head") == src.get("head") and rec.get("dirty_digest") == src.get("dirty_digest")


def save_last_prove(cwd: Path, rec: dict[str, Any]) -> Path:
    path = last_prove_path(cwd)
    path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return path


def _run_one(argv: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    started = now_iso()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        code = proc.returncode
        blob = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        code = 124
        blob = f"timeout after {timeout}s"
    except OSError as exc:
        code = 127
        blob = str(exc)
    tail = "\n".join(blob.splitlines()[-TAIL_LINES:])
    return {
        "argv": argv,
        "ok": code == 0,
        "code": code,
        "at": started,
        "tail": tail[-STORED_OUT:],
    }


def run_prove(cwd: Path, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    chain, source = discover_prove(cwd)
    steps: list[dict[str, Any]] = []
    for argv in chain:
        step = _run_one(argv, cwd, timeout)
        steps.append(step)
        if not step["ok"]:
            break
    src = source_state(cwd)
    ok = bool(steps) and all(s["ok"] for s in steps)
    rec = {
        "at": now_iso(),
        "ok": ok,
        "code": 0 if ok else int((steps[-1]["code"] if steps else 1)),
        "argv": steps[-1]["argv"] if steps else [],
        "steps": [{"argv": s["argv"], "ok": s["ok"], "code": s["code"]} for s in steps],
        "source": source,
        "head": src.get("head"),
        "dirty_digest": src.get("dirty_digest"),
        "cwd": str(cwd),
        "tail": (steps[-1]["tail"] if steps else "")[-STORED_OUT:],
        "weak": prove_is_weak(chain),
    }
    save_last_prove(cwd, rec)
    journal(cwd, "prove", ok=rec["ok"], code=rec["code"], steps=len(steps), via=source)
    return rec


def evidence_line(rec: dict[str, Any]) -> str:
    steps = rec.get("steps") or [{"argv": rec.get("argv") or [], "code": rec.get("code")}]
    bits = [" ".join(s.get("argv") or []) for s in steps]
    status = "exit 0" if rec.get("ok") else f"exit {rec.get('code')}"
    return f"{' && '.join(bits)}  {status}"


def cmd_prove(cwd: Path, record: bool = False, timeout: int = DEFAULT_TIMEOUT) -> int:
    try:
        rec = run_prove(cwd, timeout=timeout)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"prove:  {'OK' if rec['ok'] else 'FAIL'}  {evidence_line(rec)}")
    print(f"via:    {rec['source']}")
    if rec.get("weak"):
        print("warn:   prove looks like a no-op (true/echo) — set a real test command")
    if rec.get("tail"):
        print("-- tail --")
        print(rec["tail"])
    if rec["ok"] and record and load_active(cwd):
        cmd_phase("verify", cwd, evidence_line(rec))
    return 0 if rec["ok"] else 1


def cmd_consult(text: str, cwd: Path) -> int:
    lower = text.lower()
    if any(k in lower for k in ("review", "diff", "pr ", "schau")):
        phase = "review"
    elif any(k in lower for k in ("tdd", "failing test", "regression", "bug", "fix")):
        phase = "test"
    elif any(k in lower for k in ("plan", "design", "architect", "blueprint")):
        phase = "plan"
    elif any(k in lower for k in ("one-liner", "typo", "rename")):
        phase = "implement"
    else:
        phase = "plan"
    try:
        chain, via = discover_prove(cwd)
        prove = " && ".join(" ".join(cmd) for cmd in chain)
        weak = prove_is_weak(chain)
    except FileNotFoundError:
        chain, via, prove, weak = [], "none", "(set .ebttrl.json prove)", False
    print(f"goal:    {text.strip()}")
    print(f"start:   {phase}")
    print(f"skill:   { {'plan': 'ebttrl-plan', 'test': 'ebttrl-tdd', 'implement': 'ebttrl', 'review': 'ebttrl-review'}[phase] }")
    print(f"agent:   ebttrl:{ {'plan': 'ebttrl-planner', 'test': 'ebttrl-builder', 'implement': 'ebttrl-builder', 'review': 'ebttrl-reviewer'}[phase] }")
    print(f"prove:   {prove}")
    print(f"via:     {via}")
    if weak:
        print("warn:    prove looks like a no-op — prefer tests, then types/lint")
    print(f"run:     ebttrl begin \"{text.strip()}\" --phase {phase}")
    return 0


def cmd_receipt_check(cwd: Path) -> int:
    from ebttrl_loop import receipts_for, workspace_slug

    rows = receipts_for(workspace_slug(cwd), 1)
    if not rows:
        print("no receipt for this workspace")
        return 1
    rec = rows[0]
    src = source_state(cwd)
    rec_src = rec.get("source") or {}
    head_ok = rec_src.get("head") == src.get("head")
    digest_ok = rec_src.get("dirty_digest") == src.get("dirty_digest")
    if head_ok and digest_ok:
        print(f"receipt MATCH  {rec.get('goal')}  {(src.get('head') or '—')[:12]}")
        return 0
    print(f"receipt DRIFT  {rec.get('goal')}")
    print(f"  receipt head   {(rec_src.get('head') or '—')[:12]}  digest={rec_src.get('dirty_digest')}")
    print(f"  worktree head  {(src.get('head') or '—')[:12]}  digest={src.get('dirty_digest')}")
    return 1
