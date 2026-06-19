#!/usr/bin/env python3
"""Install Bombs-Training custom logic and map into an AoTTG2 data folder."""

from __future__ import annotations

import shutil
from pathlib import Path

from paths import app_root

ROOT = app_root()
PACK = ROOT / "pack"

LOGIC_NAME = "BombsTrainingLogic.cl"
MAP_NAME = "BombsTrainingMap.txt"


def find_aottg_root(start: Path | None = None) -> Path | None:
    candidates = [start, ROOT, Path.cwd()] if start is None else [start, ROOT, Path.cwd()]
    seen: set[Path] = set()
    for base in candidates:
        if base is None:
            continue
        base = base.resolve()
        for candidate in (base, base.parent):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "CustomLogic").is_dir() and (candidate / "CustomMap").is_dir():
                return candidate
    return None


def default_aottg_root() -> Path | None:
    if (ROOT.parent / "CustomLogic").is_dir() and (ROOT.parent / "CustomMap").is_dir():
        return ROOT.parent.resolve()
    return find_aottg_root()


def is_installed(aottg_root: Path) -> bool:
    return (aottg_root / "CustomLogic" / LOGIC_NAME).is_file()


def install_file(src: Path, dest: Path, *, replace: bool) -> tuple[bool, str]:
    if not src.is_file():
        return False, f"Missing pack file: {src}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and not replace:
        return False, f"Skipped {dest.name} (already exists)"
    shutil.copy2(src, dest)
    return True, f"Installed {dest.name}"


def run_install(aottg_root: Path, *, replace: bool = True) -> tuple[bool, list[str]]:
    logic_dest = aottg_root / "CustomLogic" / LOGIC_NAME
    map_dest = aottg_root / "CustomMap" / MAP_NAME

    messages: list[str] = []
    ok = True
    for src, dest in ((PACK / LOGIC_NAME, logic_dest), (PACK / MAP_NAME, map_dest)):
        file_ok, msg = install_file(src, dest, replace=replace)
        messages.append(msg)
        ok = ok and file_ok

    return ok, messages
