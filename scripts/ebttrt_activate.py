"""Activate ebttrt on this Mac. No hardcoded user home paths."""

from __future__ import annotations

import os
import re
import shutil
import stat
import sys
from pathlib import Path

from ebttrt_lib import grok_home, plugin_root

HOHEIT_TABLE = "[mcp_servers.hoheit]"
ZSH_PATH_LINE = 'export PATH="$HOME/.grok/bin:$PATH"'
PROJECT_MCP_COMMAND = "scripts/hoheit-mcp"


def looks_like_ebttrt(path: Path) -> bool:
    scripts = path / "scripts"
    return (path / "plugin.json").is_file() and (
        (scripts / "ebttrt.py").is_file() or (scripts / "ebttrl.py").is_file()
    )


def looks_like_hoheit(path: Path) -> bool:
    return (path / "scripts" / "hoheit").is_file() and (path / "apps" / "kernel").is_dir()


def find_ebttrt() -> Path | None:
    env = os.environ.get("EBTTRT_ROOT")
    if env is None:
        env = os.environ.get("EBTTRL_ROOT")
    if env is not None:
        p = Path(env).expanduser()
        return p if looks_like_ebttrt(p) else None
    root = plugin_root()
    if looks_like_ebttrt(root):
        return root
    here = Path(__file__).resolve().parent.parent
    if looks_like_ebttrt(here):
        return here
    cwd = Path.cwd()
    for cand in (cwd, *cwd.parents):
        if looks_like_ebttrt(cand):
            return cand
    for name in ("ebttrt", "ebttrl"):
        home_dev = Path.home() / "Developer" / name
        if looks_like_ebttrt(home_dev):
            return home_dev
    return None


def find_hoheit() -> Path | None:
    env = os.environ.get("HOHEIT_ROOT")
    if env is not None:
        p = Path(env).expanduser()
        return p if looks_like_hoheit(p) else None
    cwd = Path.cwd()
    for cand in (cwd, *cwd.parents):
        if looks_like_hoheit(cand):
            return cand
    ebt = find_ebttrt()
    if ebt:
        sib = ebt.parent / "hoheit"
        if looks_like_hoheit(sib):
            return sib
    home_dev = Path.home() / "Developer" / "hoheit"
    if looks_like_hoheit(home_dev):
        return home_dev
    return None


def zshrc_path() -> Path:
    env = os.environ.get("EBTTRT_ZSHRC") or os.environ.get("EBTTRL_ZSHRC")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".zshrc"


def ensure_zsh_path() -> str:
    isolated = grok_home() != (Path.home() / ".grok")
    override = os.environ.get("EBTTRT_ZSHRC") or os.environ.get("EBTTRL_ZSHRC")
    if isolated and not override:
        return "path: skipped (isolated GROK_HOME)"
    if not override:
        grok_bin = grok_home() / "bin"
        default_bin = Path.home() / ".grok" / "bin"
        path_env = os.environ.get("PATH", "")
        if grok_bin.is_dir() and str(grok_bin) in path_env:
            return "path: already on PATH"
        if default_bin.is_dir() and str(default_bin) in path_env:
            return "path: already on PATH"
    zshrc = zshrc_path()
    if zshrc.is_file() and ZSH_PATH_LINE in zshrc.read_text(encoding="utf-8"):
        return "path: zshrc already has ~/.grok/bin"
    zshrc.parent.mkdir(parents=True, exist_ok=True)
    with zshrc.open("a", encoding="utf-8") as fh:
        fh.write(f"\n# ebttrt\n{ZSH_PATH_LINE}\n")
    return f"path: appended {ZSH_PATH_LINE} to {zshrc} (open a new shell)"


def chmod_exec(path: Path) -> None:
    if path.is_file():
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def remove_stale_ebttrl_skill() -> str | None:
    stale = grok_home() / "skills" / "ebttrl-activate"
    if not stale.exists():
        return None
    if stale.is_dir():
        shutil.rmtree(stale)
    else:
        stale.unlink()
    return f"removed stale {stale}"


def install_user_skill(repo: Path) -> Path:
    src = repo / "skills" / "ebttrt-activate" / "SKILL.md"
    dest_dir = grok_home() / "skills" / "ebttrt-activate"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "SKILL.md"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def portable_command(path: Path) -> str:
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(Path.home())
    except ValueError:
        return str(resolved)
    return "${HOME}/" + rel.as_posix()


def upsert_toml_table(path: Path, header: str, body: str) -> str:
    block = f"{header}\n{body}".rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(block + "\n", encoding="utf-8")
        return f"wrote {path}"
    text = path.read_text(encoding="utf-8")
    pat = re.compile(rf"(?ms)^{re.escape(header)}.*?(?=^\[|\Z)")
    if pat.search(text):
        path.write_text(pat.sub(block + "\n", text, count=1), encoding="utf-8")
        return f"updated {path}"
    path.write_text(text.rstrip() + "\n\n" + block + "\n", encoding="utf-8")
    return f"appended {path}"


def write_hoheit_project_mcp(hoheit: Path) -> str:
    cfg = hoheit / ".grok" / "config.toml"
    return upsert_toml_table(
        cfg,
        HOHEIT_TABLE,
        f'command = "{PROJECT_MCP_COMMAND}"\nenabled = true\n',
    )


def upsert_user_hoheit_mcp(hoheit: Path) -> str:
    mcp = hoheit / "scripts" / "hoheit-mcp"
    if not mcp.is_file():
        return "hoheit mcp script missing"
    cmd = portable_command(mcp)
    cfg = grok_home() / "config.toml"
    return "user mcp: " + upsert_toml_table(
        cfg,
        HOHEIT_TABLE,
        f'command = "{cmd}"\nenabled = true\n',
    )


def wire_hoheit(hoheit: Path) -> list[str]:
    notes = [f"hoheit: {hoheit}"]
    for rel in ("scripts/hoheit-prove", "scripts/hoheit-mcp", "scripts/hoheit"):
        target = hoheit / rel
        if target.is_file():
            chmod_exec(target)
            notes.append(f"chmod +x {rel}")
    ebt = hoheit / ".ebttrt.json"
    if not ebt.is_file():
        ebt.write_text('{\n  "prove": "scripts/hoheit-prove"\n}\n', encoding="utf-8")
        notes.append("wrote .ebttrt.json")
    notes.append("project mcp: " + write_hoheit_project_mcp(hoheit))
    notes.append(upsert_user_hoheit_mcp(hoheit))
    return notes


def cmd_activate() -> int:
    repo = find_ebttrt()
    if repo is None:
        print("ebttrt repo not found on this Mac.", file=sys.stderr)
        print("clone https://github.com/maf4711/ebttrt.git to ~/Developer/ebttrt, then:", file=sys.stderr)
        print("  python3 ~/Developer/ebttrt/scripts/ebttrt.py activate", file=sys.stderr)
        return 2
    os.environ["GROK_PLUGIN_ROOT"] = str(repo)
    from ebttrt import cmd_install

    chmod_exec(repo / "scripts" / "activate.sh")
    chmod_exec(repo / "scripts" / "install.sh")
    chmod_exec(repo / "scripts" / "ebttrt.py")
    print(f"repo:    {repo}")
    rc = cmd_install()
    print(ensure_zsh_path())
    stale = remove_stale_ebttrl_skill()
    if stale:
        print(stale)
    skill = install_user_skill(repo)
    print(f"skill:   {skill}")
    hoheit = find_hoheit()
    if hoheit:
        for note in wire_hoheit(hoheit):
            print(note)
    else:
        print("hoheit:  not found (ok — activate again after the repo is on this Mac)")
    print()
    print("next: new Grok session  ·  /plugins → r  ·  ebttrt doctor")
    return rc
