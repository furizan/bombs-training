"""Application root and AoTTG2 data-folder discovery."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

_GAME_DATA_TOP_DIRS = frozenset({"PersistentData", "CustomMap", "CustomLogic"})


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def is_aottg_root(path: Path) -> bool:
    return (path / "CustomLogic").is_dir() and (path / "CustomMap").is_dir()


def standard_aottg_roots() -> list[Path]:
    home = Path.home()
    candidates: list[Path] = []
    if sys.platform == "win32" or sys.platform == "darwin":
        candidates.append(home / "Documents" / "Aottg2")
    else:
        candidates.append(home / ".local" / "share" / "Aottg2")
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            candidates.append(Path(xdg_data) / "Aottg2")
    return candidates


def _walk_up(start: Path, *, max_depth: int = 8) -> list[Path]:
    current = start.resolve()
    chain: list[Path] = []
    for _ in range(max_depth):
        chain.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return chain


def _game_data_relative_parts(raw: Path) -> tuple[str, ...] | None:
    parts = raw.parts
    if not parts:
        return None
    if parts[0] == "..":
        return parts[1:]
    if parts[0] in _GAME_DATA_TOP_DIRS:
        return parts
    return None


def _find_aottg_root_impl(start: Path | None) -> Path | None:
    seen: set[Path] = set()

    def check(candidate: Path) -> Path | None:
        resolved = candidate.resolve()
        if resolved in seen:
            return None
        seen.add(resolved)
        if is_aottg_root(resolved):
            return resolved
        return None

    if start is None:
        for candidate in standard_aottg_roots():
            hit = check(candidate)
            if hit is not None:
                return hit
        for base in (app_root(), Path.cwd()):
            for candidate in _walk_up(base):
                hit = check(candidate)
                if hit is not None:
                    return hit
    else:
        for candidate in _walk_up(start):
            hit = check(candidate)
            if hit is not None:
                return hit
        for candidate in standard_aottg_roots():
            hit = check(candidate)
            if hit is not None:
                return hit

    return None


@lru_cache(maxsize=1)
def _find_default_aottg_root() -> Path | None:
    return _find_aottg_root_impl(None)


def find_aottg_root(start: Path | None = None) -> Path | None:
    if start is None:
        return _find_default_aottg_root()
    return _find_aottg_root_impl(start)


def resolve_config_path(
    value: str | Path,
    *,
    app_root_dir: Path | None = None,
    prefer_app: bool = False,
) -> Path:
    """Resolve a config path.

    Bundled assets (prefer_app) stay next to the executable.
    Game data paths (../PersistentData/..., ../CustomMap/...) resolve under the
    AoTTG2 data folder, checked at the standard install location first.
    """
    base = app_root_dir or app_root()
    raw = Path(value)
    if raw.is_absolute():
        return raw.resolve()

    app_path = (base / raw).resolve()
    if prefer_app:
        return app_path

    game_parts = _game_data_relative_parts(raw)
    if game_parts is not None:
        aottg = find_aottg_root()
        if aottg is not None:
            return aottg.joinpath(*game_parts).resolve()

    return app_path
