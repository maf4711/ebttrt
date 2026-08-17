"""ebttrt core: paths, shield, receipts, hooks. Stdlib only."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
LOOP = ("plan", "test", "implement", "review", "verify", "remember", "improve")
MAX_CONTEXT_CHARS = 6000
INJECT_CONTEXT_CHARS = 1800

SECRET_LINE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|private[_-]?key|authorization)"
    r"\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)
PEM_BEGIN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
AWS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")
GITHUB_PAT = re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")

DENY_COMMANDS = (
    re.compile(r"\bdump-keychain\b"),
    re.compile(r"\bsecurity\s+dump-keychain\b"),
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)*-(?:rf|fr)\s+/(?:\s|$)"),
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)*-(?:rf|fr)\s+/\*"),
    re.compile(r"\bmkfs\."),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*;\s*\}"),
    re.compile(r"\bpycookiecheat\b"),
    re.compile(r"\bbrowser_cookie3\b"),
    re.compile(r"\brookiepy\b"),
    re.compile(r"Chrome Safe Storage"),
    re.compile(r"\bgit\s+push\s+[^\n]*--force[^\n]*\s(?:origin\s+)?(?:main|master)\b"),
    re.compile(r"\bdrop\s+database\b", re.I),
)

SCAN_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".grok",
    "sessions",
    "tests",
}

# Executable-ish files: a markdown mention of dump-keychain is documentation, not a command.
COMMAND_SUFFIXES = {".sh", ".zsh", ".bash", ".json"}

SCAN_SUFFIXES = {
    ".py",
    ".sh",
    ".zsh",
    ".bash",
    ".js",
    ".ts",
    ".tsx",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".md",
    ".env",
}


def grok_home() -> Path:
    raw = os.environ.get("GROK_HOME") or str(Path.home() / ".grok")
    return Path(raw).expanduser()


def data_home() -> Path:
    override = os.environ.get("EBTTRT_HOME") or os.environ.get("EBTTRL_HOME")
    return Path(override).expanduser() if override else grok_home() / "ebttrt"


def plugin_root() -> Path:
    env = os.environ.get("GROK_PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def plugin_digest(root: Path | None = None) -> str:
    base = root or plugin_root()
    hasher = hashlib.sha256()
    for rel in ("VERSION", "plugin.json"):
        path = base / rel
        if path.is_file():
            hasher.update(path.read_bytes())
    hasher.update(VERSION.encode())
    return hasher.hexdigest()[:16]


def declared_versions(root: Path | None = None) -> tuple[str, str, str]:
    base = root or plugin_root()
    file_v = (base / "VERSION").read_text(encoding="utf-8").strip() if (base / "VERSION").is_file() else ""
    plug_v = ""
    manifest = base / "plugin.json"
    if manifest.is_file():
        try:
            plug_v = str((json.loads(manifest.read_text(encoding="utf-8")) or {}).get("version") or "")
        except json.JSONDecodeError:
            plug_v = ""
    return file_v, plug_v, VERSION


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> Path:
    home = data_home()
    (home / "receipts").mkdir(parents=True, exist_ok=True)
    (home / "sessions").mkdir(parents=True, exist_ok=True)
    (home / "instincts.jsonl").touch(exist_ok=True)
    return home


def git(cwd: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def dirty_digest(cwd: Path, porcelain: str) -> str | None:
    if not porcelain:
        return None
    diff = "\n".join((git(cwd, "diff"), git(cwd, "diff", "--cached"), porcelain))
    return hashlib.sha256(diff.encode()).hexdigest()[:16]


def source_state(cwd: Path) -> dict[str, Any]:
    dirty = git(cwd, "status", "--porcelain")
    return {
        "cwd": str(cwd),
        "head": git(cwd, "rev-parse", "HEAD") or None,
        "branch": git(cwd, "rev-parse", "--abbrev-ref", "HEAD") or None,
        "origin": git(cwd, "remote", "get-url", "origin") or None,
        "dirty": bool(dirty),
        "dirty_paths": [line[3:] for line in dirty.splitlines() if len(line) > 3][:40],
        "dirty_digest": dirty_digest(cwd, dirty),
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def workspace_slug(cwd: Path) -> str:
    origin = git(cwd, "remote", "get-url", "origin")
    key = origin or str(cwd.resolve())
    digest = hashlib.sha256(key.encode()).hexdigest()[:8]
    return f"{cwd.resolve().name}-{digest}"


def load_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def cmd_from_event(event: dict[str, Any]) -> str:
    tool_input = event.get("toolInput") or event.get("tool_input") or {}
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or "")
    return ""


def deny_reason(command: str) -> str | None:
    if not command:
        return None
    for pat in DENY_COMMANDS:
        if pat.search(command):
            return f"ebttrt shield blocked a dangerous command ({pat.pattern})"
    return None


def hook_session_start(event: dict[str, Any]) -> int:
    from ebttrt_loop import emit_hook_context, inject_session_context, write_session_context

    write_session_context(event)
    emit_hook_context("SessionStart", inject_session_context(event), INJECT_CONTEXT_CHARS)
    return 0


def hook_precompact(event: dict[str, Any]) -> int:
    from ebttrt_loop import emit_hook_context, inject_session_context, write_session_context

    write_session_context(event)
    emit_hook_context("PreCompact", inject_session_context(event), INJECT_CONTEXT_CHARS)
    return 0


def hook_posttool(event: dict[str, Any]) -> int:
    from ebttrt_loop import note_edit

    return note_edit(event)


def hook_stop(event: dict[str, Any]) -> int:
    from ebttrt_loop import hook_stop as _stop

    return _stop(event)


def hook_session_end(event: dict[str, Any]) -> int:
    home = ensure_dirs()
    sid = event.get("sessionId") or event.get("session_id") or "unknown"
    path = home / "sessions" / f"{sid}.json"
    payload = {
        "session_id": sid,
        "ended": now_iso(),
        "reason": event.get("reason"),
        "cwd": event.get("workspaceRoot") or event.get("cwd"),
    }
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                existing.update(payload)
                payload = existing
        except json.JSONDecodeError:
            pass
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


def hook_pretool(event: dict[str, Any]) -> int:
    reason = deny_reason(cmd_from_event(event))
    if reason:
        sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}) + "\n")
        return 2
    sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
    return 0


INSTINCT_SECRET = re.compile(
    r"(?i)(/Users/|/home/)[^\s]+|/Users/\S+|sk-[A-Za-z0-9]{8,}|gh[pousr]_[A-Za-z0-9_]{12,}"
    r"|password\s*[:=]|api[_-]?key\s*[:=]"
)


def instinct_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def receipt_matches(cwd: Path) -> dict[str, Any] | None:
    from ebttrt_loop import receipts_for

    rows = receipts_for(workspace_slug(cwd), 1)
    if not rows:
        return None
    rec = rows[0]
    src = source_state(cwd)
    rec_src = rec.get("source") or {}
    if rec_src.get("head") == src.get("head") and rec_src.get("dirty_digest") == src.get("dirty_digest"):
        return rec
    return None


def cmd_remember(
    text: str,
    workspace: str = "*",
    confidence: float = 0.6,
    cwd: Path | None = None,
    force: bool = False,
) -> int:
    body = text.strip()
    if not body:
        print("instinct text is empty", file=sys.stderr)
        return 2
    if INSTINCT_SECRET.search(body) or SECRET_LINE.search(body):
        print("instinct looks like a secret or home path — refused", file=sys.stderr)
        return 2
    here = cwd or Path.cwd()
    slug = workspace_slug(here) if workspace == "." else workspace
    if not force:
        if receipt_matches(here) is None:
            print("need a MATCH receipt for this workspace (ebttrt done) or --force", file=sys.stderr)
            return 1
    home = ensure_dirs()
    path = home / "instincts.jsonl"
    rows = read_jsonl(path)
    key = instinct_key(body)
    for item in reversed(rows):
        if instinct_key(str(item.get("text") or "")) == key and item.get("workspace") == slug:
            prev = float(item.get("confidence") or 0)
            item["confidence"] = min(0.9, max(prev, 0.5) + 0.2)
            item["at"] = now_iso()
            item["hits"] = int(item.get("hits") or 1) + 1
            _rewrite_instincts(path, rows)
            print(f"instinct hit {item['hits']}  confidence {item['confidence']:.2f} ({slug})")
            return 0
    item = {
        "at": now_iso(),
        "workspace": slug,
        "confidence": min(0.5, float(confidence)),
        "text": body,
        "hits": 1,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"instinct stored ({slug})  confidence {item['confidence']:.2f}")
    return 0


def _rewrite_instincts(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def cmd_instincts() -> int:
    rows = read_jsonl(ensure_dirs() / "instincts.jsonl")
    if not rows:
        print("(no instincts)")
        return 0
    print(f"{len(rows)} instinct(s)")
    for item in rows[-30:]:
        print(
            f"{item.get('at', '?')}  {item.get('workspace', '?')}  "
            f"{float(item.get('confidence') or 0):.2f}  {item.get('text', '')}"
        )
    return 0


def cmd_improve(cwd: Path) -> int:
    from ebttrt_loop import load_receipts

    slug = workspace_slug(cwd)
    recs = load_receipts()
    rows = read_jsonl(ensure_dirs() / "instincts.jsonl")
    shown = 0
    for item in rows:
        if float(item.get("confidence") or 0) <= 0.5:
            continue
        ws = str(item.get("workspace") or "*")
        if ws not in {slug, "*"}:
            continue
        n = sum(1 for r in recs if r.get("workspace") in {slug, ws})
        if n < 2:
            continue
        print(f"{float(item['confidence']):.2f}  receipts={n}  {item.get('text', '')}")
        shown += 1
    if not shown:
        print("(no earned instincts — same win twice + two receipts)")
        return 0
    print("promote only the lines above; do not invent a catalog skill")
    return 0


def cmd_receipt_write(goal: str, evidence: str, phases: list[str], cwd: Path) -> int:
    home = ensure_dirs()
    rec = {
        "at": now_iso(),
        "goal": goal,
        "evidence": evidence,
        "phases": phases or list(LOOP),
        "workspace": workspace_slug(cwd),
        "source": source_state(cwd),
        "version": VERSION,
        "plugin_digest": plugin_digest(),
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", goal.lower()).strip("-")[:40] or "loop"
    path = home / "receipts" / f"{stamp}-{slug}.json"
    path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


def cmd_receipt_last() -> int:
    home = ensure_dirs()
    receipts = sorted((home / "receipts").glob("*.json"), key=lambda p: p.name, reverse=True)
    if not receipts:
        print("(no receipts)")
        return 0
    sys.stdout.write(receipts[0].read_text(encoding="utf-8"))
    return 0


def scan_file(path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    if PEM_BEGIN.search(text):
        findings.append({"severity": "critical", "path": str(path), "rule": "private-key"})
    if AWS_KEY.search(text):
        findings.append({"severity": "critical", "path": str(path), "rule": "aws-access-key"})
    if GITHUB_PAT.search(text):
        findings.append({"severity": "critical", "path": str(path), "rule": "github-token"})
    for i, line in enumerate(text.splitlines(), 1):
        if SECRET_LINE.search(line):
            findings.append(
                {
                    "severity": "high",
                    "path": str(path),
                    "line": i,
                    "rule": "assignment-looks-like-secret",
                }
            )
        if path.suffix.lower() in COMMAND_SUFFIXES and deny_reason(line):
            findings.append(
                {
                    "severity": "high",
                    "path": str(path),
                    "line": i,
                    "rule": "dangerous-command",
                }
            )
    try:
        if path.stat().st_mode & stat.S_IWOTH:
            findings.append({"severity": "medium", "path": str(path), "rule": "world-writable"})
    except OSError:
        pass
    return findings


def grade(findings: list[dict[str, Any]]) -> str:
    sev = {f["severity"] for f in findings}
    if "critical" in sev:
        return "F"
    if "high" in sev:
        return "C"
    if "medium" in sev:
        return "B"
    return "A"


def cmd_shield(root: Path) -> int:
    findings: list[dict[str, Any]] = []
    root = root.resolve()
    if root.is_file():
        findings.extend(scan_file(root))
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SCAN_SKIP_DIRS]
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix.lower() not in SCAN_SUFFIXES and name not in {".env", "hooks.json"}:
                    continue
                if path.stat().st_size > 1_000_000:
                    continue
                findings.extend(scan_file(path))
    letter = grade(findings)
    print(f"ebttrt shield  {letter}  {len(findings)} finding(s)  {root}")
    for item in findings[:50]:
        loc = f":{item['line']}" if "line" in item else ""
        print(f"  {item['severity']:8} {item['rule']:32} {item['path']}{loc}")
    if len(findings) > 50:
        print(f"  … {len(findings) - 50} more")
    return 2 if letter == "F" else 1 if letter == "C" else 0
