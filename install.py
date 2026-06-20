#!/usr/bin/env python3
"""Install bombs-training custom logic and map into an AoTTG2 data folder."""

from __future__ import annotations

import shutil
from pathlib import Path

from paths import app_root

ROOT = app_root()
PACK = ROOT / "pack"

LOGIC_NAME = "bombs-training-logic.cl"
MAP_NAME = "bombs-training-map.txt"


def _label(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


PRODUCT_NAME = _label("bombs-training")
LOGIC_ID = LOGIC_NAME.removesuffix(".cl")
MAP_ID = MAP_NAME.removesuffix(".txt")
LOGIC_LABEL = _label(LOGIC_ID)
MAP_LABEL = _label(MAP_ID)


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
