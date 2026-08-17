"""ebttrl loop state: begin → phase → next → done. One active loop per workspace."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from ebttrl_lib import (
    INJECT_CONTEXT_CHARS,
    LOOP,
    MAX_CONTEXT_CHARS,
    data_home,
    ensure_dirs,
    grok_home,
    now_iso,
    read_jsonl,
    source_state,
    workspace_slug,
)

PHASE_SKILL = {
    "plan": "ebttrl-plan",
    "test": "ebttrl-tdd",
    "implement": "ebttrl",
    "review": "ebttrl-review",
    "verify": "ebttrl-verify",
    "remember": "ebttrl-remember",
    "improve": "ebttrl-improve",
}

# Allowed forward hops. Review may be skipped; verify may not.
ALLOWED: dict[str | None, tuple[str, ...]] = {
    None: ("plan", "test", "implement"),
    "plan": ("test", "implement"),
    "test": ("implement",),
    "implement": ("review", "verify"),
    "review": ("verify",),
    "verify": ("remember",),
    "remember": ("improve",),
    "improve": (),
}

DONE_RX = re.compile(
    r"\b(done|fertig|fixed|complete|completed|ready to (?:ship|merge)|"
    r"all tests pass|lgtm|ship it)\b",
    re.I,
)
EDIT_TOOLS = {
    "search_replace",
    "Write",
    "Edit",
    "MultiEdit",
    "write",
    "edit",
}


def workspace_dir(cwd: Path) -> Path:
    path = ensure_dirs() / "workspaces" / workspace_slug(cwd)
    path.mkdir(parents=True, exist_ok=True)
    return path


def active_path(cwd: Path) -> Path:
    return workspace_dir(cwd) / "active.json"


def load_active(cwd: Path) -> dict[str, Any] | None:
    path = active_path(cwd)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def journal(cwd: Path, event: str, **fields: Any) -> None:
    row = {"at": now_iso(), "event": event, **fields}
    path = workspace_dir(cwd) / "journal.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_journal(cwd: Path, limit: int = 5) -> list[dict[str, Any]]:
    path = workspace_dir(cwd) / "journal.jsonl"
    if not path.exists():
        return []
    rows = read_jsonl(path)
    return rows[-limit:]


def save_active(cwd: Path, data: dict[str, Any]) -> Path:
    path = active_path(cwd)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def clear_active(cwd: Path) -> None:
    path = active_path(cwd)
    if path.exists():
        path.unlink()


def next_phases(current: str | None) -> tuple[str, ...]:
    return ALLOWED.get(current, ())


def load_receipts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in (ensure_dirs() / "receipts").glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(rec, dict):
            rec["_path"] = str(path)
            rows.append(rec)
    rows.sort(key=lambda r: str(r.get("at") or r.get("_path") or ""), reverse=True)
    return rows


def receipts_for(slug: str, limit: int = 3) -> list[dict[str, Any]]:
    return [r for r in load_receipts() if r.get("workspace") == slug][:limit]


def cmd_begin(goal: str, cwd: Path, phase: str = "plan") -> int:
    if phase not in LOOP:
        print(f"unknown phase: {phase}", file=sys.stderr)
        return 2
    if phase not in ALLOWED[None]:
        print(f"begin at plan, test, or implement — not {phase}", file=sys.stderr)
        return 2
    existing = load_active(cwd)
    if existing and existing.get("goal") and existing.get("phase") not in ("remember", "improve"):
        print(f"open loop already: {existing.get('phase')} · {existing.get('goal')}")
        print("ebttrl abort   — drop it")
        print("ebttrl done    — close it with a receipt")
        return 1
    data = {
        "goal": goal.strip(),
        "phase": phase,
        "started": now_iso(),
        "updated": now_iso(),
        "cwd": str(cwd.resolve()),
        "workspace": workspace_slug(cwd),
        "verified": False,
        "evidence": "",
        "edits": 0,
    }
    save_active(cwd, data)
    journal(cwd, "begin", goal=data["goal"], phase=phase)
    print(format_loop(data))
    return 0


def cmd_phase(phase: str, cwd: Path, evidence: str = "") -> int:
    if phase not in LOOP:
        print(f"unknown phase: {phase}", file=sys.stderr)
        return 2
    active = load_active(cwd)
    if not active:
        print("no open loop — ebttrl begin \"goal\"", file=sys.stderr)
        return 1
    current = str(active.get("phase") or "")
    if phase != current and phase not in next_phases(current):
        allowed = ", ".join(next_phases(current)) or "done"
        print(f"cannot {current} → {phase}. next: {allowed}", file=sys.stderr)
        return 1
    if phase == "remember" and not active.get("verified"):
        print("verify first (ebttrl phase verify --evidence \"cmd + result\")", file=sys.stderr)
        return 1
    if phase == "verify" and evidence:
        active["verified"] = True
        active["evidence"] = evidence
    active["phase"] = phase
    active["updated"] = now_iso()
    save_active(cwd, active)
    journal(cwd, "phase", phase=phase, verified=bool(active.get("verified")))
    print(format_loop(active))
    return 0


def cmd_next(cwd: Path) -> int:
    active = load_active(cwd)
    nxt = next_phases(active.get("phase") if active else None)
    if not active:
        print("no open loop")
        print("next:    plan | test | implement")
        print("run:     ebttrl begin \"goal\"")
        return 0
    print(format_loop(active))
    if not nxt:
        print("next:    done")
        print("run:     ebttrl done --evidence \"…\"")
        return 0
    print(f"next:    {' | '.join(nxt)}")
    print(f"skill:   {PHASE_SKILL[nxt[0]]}")
    print(f"run:     ebttrl phase {nxt[0]}")
    return 0


def cmd_abort(cwd: Path) -> int:
    if not load_active(cwd):
        print("no open loop")
        return 0
    journal(cwd, "abort")
    clear_active(cwd)
    print("loop aborted")
    return 0


def format_loop(active: dict[str, Any]) -> str:
    phase = str(active.get("phase") or "?")
    skill = PHASE_SKILL.get(phase, "ebttrl")
    lines = [
        f"loop:    {active.get('goal', '')}",
        f"phase:   {phase}",
        f"skill:   {skill}",
        f"verify:  {'yes' if active.get('verified') else 'no'}",
    ]
    if active.get("evidence"):
        lines.append(f"evidence:{active['evidence']}")
    return "\n".join(lines)


def emit_hook_context(event_name: str, text: str, limit: int = INJECT_CONTEXT_CHARS) -> None:
    clip = text if len(text) <= limit else text[: limit - 20] + "\n… [truncated]\n"
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": clip,
                }
            }
        )
        + "\n"
    )


def inject_session_context(event: dict[str, Any]) -> str:
    cwd = Path(event.get("workspaceRoot") or event.get("cwd") or os.getcwd())
    slug = workspace_slug(cwd)
    active = load_active(cwd)
    last_prove = None
    try:
        from ebttrl_prove import load_last_prove

        last_prove = load_last_prove(cwd)
    except Exception:
        last_prove = None
    recs = receipts_for(slug, 1)
    rec = recs[0] if recs else None
    rec_src = (rec or {}).get("source") or {}
    if last_prove:
        prove = f"{'OK' if last_prove.get('ok') else 'FAIL'} {last_prove.get('at')}"
    else:
        prove = "none"
    if active:
        loop = (
            f"{active.get('goal')} · {active.get('phase')} · "
            f"verified={'yes' if active.get('verified') else 'no'}"
        )
    else:
        loop = "none"
    receipt = "none"
    if rec:
        receipt = f"{rec.get('goal')} · {(rec_src.get('head') or '—')[:12]}"
    lines = [
        "# ebttrl context",
        f"workspace: {cwd}",
        f"slug: {slug}",
        f"loop: {loop}",
        f"prove: {prove}",
        f"receipt: {receipt}",
        "next: ebttrl prove --record && ebttrl done",
    ]
    text = "\n".join(lines) + "\n"
    if len(text) > INJECT_CONTEXT_CHARS:
        return text[: INJECT_CONTEXT_CHARS - 20] + "\n… [truncated]\n"
    return text


def write_session_context(event: dict[str, Any]) -> str:
    cwd = Path(event.get("workspaceRoot") or event.get("cwd") or os.getcwd())
    slug = workspace_slug(cwd)
    active = load_active(cwd)
    src = source_state(cwd)
    receipts = receipts_for(slug, 3)
    instincts = [
        r
        for r in read_jsonl(data_home() / "instincts.jsonl")
        if r.get("workspace") in (slug, "*")
    ][-8:]
    last_prove = None
    try:
        from ebttrl_prove import load_last_prove

        last_prove = load_last_prove(cwd)
    except Exception:
        last_prove = None
    lines = [
        f"# ebttrl context ({now_iso()})",
        "",
        f"workspace: {cwd}",
        f"slug: {slug}",
        f"git: {src.get('branch') or '—'} @ {(src.get('head') or '—')[:12]}"
        + (" dirty" if src.get("dirty") else " clean"),
        "loop: " + " → ".join(LOOP),
        "",
    ]
    if active:
        lines.extend(
            [
                "## Active loop",
                f"- goal: {active.get('goal')}",
                f"- phase: {active.get('phase')} → skill `{PHASE_SKILL.get(str(active.get('phase')), 'ebttrl')}`",
                f"- verified: {'yes' if active.get('verified') else 'no'}",
                f"- next: {' | '.join(next_phases(str(active.get('phase')))) or 'done'}",
                "",
            ]
        )
    else:
        lines.extend(["## Active loop", "(none — `ebttrl begin \"goal\"`)", ""])
    lines.append("## Last prove")
    if last_prove:
        lines.append(
            f"- {'OK' if last_prove.get('ok') else 'FAIL'} {last_prove.get('at')} "
            f"`{' '.join(last_prove.get('argv') or [])}`"
        )
    else:
        lines.append("(none — `ebttrl prove`)")
    lines.extend(["", "## Recent receipts"])
    if not receipts:
        lines.append("(none for this workspace)")
    for rec in receipts:
        head = ((rec.get("source") or {}).get("head") or "—")[:12]
        digest = (rec.get("source") or {}).get("dirty_digest") or "clean"
        lines.append(f"- {rec.get('at', '?')} · {rec.get('goal', '(no goal)')} · {head} · {digest}")
    lines.extend(["", "## Journal"])
    events = read_journal(cwd, 5)
    if not events:
        lines.append("(empty)")
    for item in events:
        lines.append(f"- {item.get('at', '?')} {item.get('event', '?')}")
    lines.extend(["", "## Instincts"])
    if not instincts:
        lines.append("(none)")
    for item in instincts:
        lines.append(f"- ({item.get('confidence', 0.5):.2f}) {item.get('text', '').strip()}")
    text = "\n".join(lines) + "\n"
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[: MAX_CONTEXT_CHARS - 20] + "\n… [truncated]\n"
    home = ensure_dirs()
    (home / "current-context.md").write_text(text, encoding="utf-8")
    (workspace_dir(cwd) / "context.md").write_text(text, encoding="utf-8")
    inject = inject_session_context(event)
    (home / "last-context.json").write_text(
        json.dumps(
            {
                "at": now_iso(),
                "cwd": str(cwd),
                "inject_bytes": len(inject.encode()),
                "disk_bytes": len(text.encode()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    sid = event.get("sessionId") or event.get("session_id")
    if sid:
        (home / "sessions" / f"{sid}.json").write_text(
            json.dumps(
                {
                    "session_id": sid,
                    "started": now_iso(),
                    "cwd": str(cwd),
                    "slug": slug,
                    "edits": 0,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return text


def append_memory(cwd: Path, goal: str, evidence: str) -> Path | None:
    src = source_state(cwd)
    line = (
        f"- {now_iso()[:10]}: {goal} — {evidence} — "
        f"{(src.get('head') or '—')[:12]} digest={src.get('dirty_digest') or 'clean'}"
    )
    our = ensure_dirs() / "MEMORY.md"
    _upsert_memory(our, line)
    grok_mem = grok_home() / "memory" / "MEMORY.md"
    if grok_mem.parent.is_dir():
        _upsert_memory(grok_mem, line)
        return grok_mem
    return our


def _upsert_memory(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if line in existing:
        return
    if "## ebttrl" not in existing:
        block = existing.rstrip() + ("\n\n" if existing.strip() else "") + "## ebttrl\n" + line + "\n"
    else:
        block = existing.rstrip() + "\n" + line + "\n"
    path.write_text(block, encoding="utf-8")


def note_edit(event: dict[str, Any]) -> int:
    tool = str(event.get("toolName") or event.get("tool_name") or "")
    if tool not in EDIT_TOOLS:
        return 0
    cwd = Path(event.get("workspaceRoot") or event.get("cwd") or os.getcwd())
    active = load_active(cwd)
    if not active:
        return 0
    active["edits"] = int(active.get("edits") or 0) + 1
    active["updated"] = now_iso()
    save_active(cwd, active)
    return 0


def stop_nudge_enabled() -> bool:
    return os.environ.get("EBTTRL_STOP_NUDGE", "1") not in {"0", "false", "off"}


def should_nudge(event: dict[str, Any], active: dict[str, Any] | None) -> bool:
    if not stop_nudge_enabled():
        return False
    if event.get("reason") != "end_turn":
        return False
    if event.get("stopHookActive") or event.get("stop_hook_active"):
        return False
    if event.get("subagentType") or event.get("subagent_type"):
        return False
    if not active:
        return False
    phase = str(active.get("phase") or "")
    if phase not in {"test", "implement", "review"}:
        return False
    if active.get("verified"):
        return False
    message = str(event.get("lastAssistantMessage") or event.get("last_assistant_message") or "")
    if DONE_RX.search(message):
        return True
    return int(active.get("edits") or 0) > 0 and bool(
        re.search(r"\b(pass(?:es|ed|ing)?|green|fixed)\b", message, re.I)
    )


def hook_stop(event: dict[str, Any]) -> int:
    cwd = Path(event.get("workspaceRoot") or event.get("cwd") or os.getcwd())
    active = load_active(cwd)
    if not should_nudge(event, active):
        return 0
    assert active is not None
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": (
                f"ebttrl: open loop \"{active.get('goal')}\" is still in {active.get('phase')} "
                "and is not verified. Do not claim done. Run `ebttrl prove --record`, then "
                "`ebttrl done`."
            ),
        }
    }
    journal(cwd, "nudge", phase=active.get("phase"))
    print(json.dumps(payload))
    return 0
