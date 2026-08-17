"""Review snapshot + done/remember gate. Stdlib only."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ebttrt_lib import now_iso, source_state
from ebttrt_loop import journal, workspace_dir

PUBLIC_NAMES = {"__init__.py", "index.ts", "index.js", "index.tsx", "mod.rs"}


def last_review_path(cwd: Path) -> Path:
    return workspace_dir(cwd) / "review.json"


def load_last_review(cwd: Path) -> dict[str, Any] | None:
    path = last_review_path(cwd)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def dirty_paths(cwd: Path) -> list[str]:
    src = source_state(cwd)
    return [str(p) for p in (src.get("dirty_paths") or [])]


def looks_public_api(paths: list[str]) -> bool:
    for raw in paths:
        norm = raw.replace("\\", "/")
        name = Path(norm).name
        if name in PUBLIC_NAMES or name.endswith(".d.ts"):
            return True
        if "/api/" in norm or norm.startswith("api/"):
            return True
    return False


def review_required(cwd: Path) -> bool:
    paths = dirty_paths(cwd)
    return len(paths) > 1 or looks_public_api(paths)


def review_fresh(cwd: Path, rec: dict[str, Any] | None = None) -> bool:
    rec = rec if rec is not None else load_last_review(cwd)
    if not rec:
        return False
    src = source_state(cwd)
    return rec.get("head") == src.get("head") and rec.get("dirty_digest") == src.get("dirty_digest")


def high_findings(rec: dict[str, Any]) -> bool:
    for item in rec.get("findings") or []:
        if isinstance(item, dict) and item.get("severity") in {"critical", "high"}:
            return True
    return False


def review_blocker(cwd: Path) -> str | None:
    if not review_required(cwd):
        return None
    rec = load_last_review(cwd)
    if rec is None:
        return "review required (multi-file or public API) — ebttrt review"
    if not review_fresh(cwd, rec):
        return "review drifted (tree changed) — re-run ebttrt review"
    if rec.get("verdict") == "revise" and high_findings(rec):
        return "review revise + critical/high — fix and re-review"
    return None


def parse_finding(raw: str) -> dict[str, str]:
    # severity:path:message
    parts = raw.split(":", 2)
    if len(parts) == 3:
        return {"severity": parts[0].strip(), "path": parts[1].strip(), "message": parts[2].strip()}
    return {"severity": "info", "path": "", "message": raw.strip()}


def cmd_review(cwd: Path, verdict: str = "approve", findings: list[str] | None = None) -> int:
    if verdict not in {"approve", "revise"}:
        print("verdict must be approve or revise", file=sys.stderr)
        return 2
    src = source_state(cwd)
    parsed = [parse_finding(f) for f in (findings or []) if f.strip()]
    rec = {
        "at": now_iso(),
        "verdict": verdict,
        "findings": parsed,
        "diff_stat": src.get("dirty_paths") or [],
        "path_count": len(src.get("dirty_paths") or []),
        "head": src.get("head"),
        "dirty_digest": src.get("dirty_digest"),
        "cwd": str(cwd),
        "required": review_required(cwd),
    }
    path = last_review_path(cwd)
    path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    journal(cwd, "review", verdict=verdict, required=rec["required"], findings=len(parsed))
    print(f"review:  {verdict}  {rec['path_count']} path(s)  {path}")
    if rec["required"] and verdict == "revise" and high_findings(rec):
        print("blocks:  done/remember until re-review")
    return 0
