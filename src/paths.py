"""Application root and AoTTG2 data-folder discovery."""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

_GAME_DATA_TOP_DIRS = frozenset({"PersistentData", "CustomMap", "CustomLogic"})
_USER_SETTINGS_NAME = "user-settings.json"
_OVERRIDE_KEY = "aottgDataFolder"
_THEME_KEY = "uiTheme"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    return app_root() / "assets"


def user_settings_path() -> Path:
    return app_root() / _USER_SETTINGS_NAME


def _windows_users_tail(parts: tuple[str, ...]) -> str | None:
    if len(parts) < 4:
        return None
    drive = parts[0].rstrip("\\/")
    if not (len(drive) == 2 and drive[1] == ":"):
        return None
    if parts[1].lower() != "users":
        return None
    return Path(*parts[3:]).as_posix()


def _drive_from_parts(parts: tuple[str, ...]) -> str | None:
    if not parts:
        return None
    drive = parts[0].rstrip("\\/")
    if len(drive) == 2 and drive[1] == ":":
        return drive
    return None


def _drive_letter(path: Path | None = None) -> str:
    if path is not None:
        drive = path.drive
        if drive:
            return drive
    drive = Path.home().drive
    if drive:
        return drive
    return "C:"


def _profile_relative_display(tail_posix: str, *, drive: str | None = None) -> str:
    if sys.platform == "win32":
        tail = tail_posix.replace("/", "\\")
        letter = drive or _drive_letter()
        return f"{letter}\\Users\\%USERNAME%\\{tail}"
    return "~/" + tail_posix


def _home_relative_display(rel: Path, *, drive: str | None = None) -> str:
    return _profile_relative_display(rel.as_posix(), drive=drive)


def _native_path_str(path: Path) -> str:
    if sys.platform == "win32":
        return str(path)
    return path.as_posix()


def format_display_path(path: Path) -> str:
    """Privacy-friendly path for UI; pasteable in the OS file manager."""
    tail = _windows_users_tail(path.parts)
    if tail is not None:
        return _profile_relative_display(tail, drive=_drive_from_parts(path.parts))

    try:
        resolved = path.resolve()
    except OSError:
        return _native_path_str(path)

    tail = _windows_users_tail(resolved.parts)
    if tail is not None:
        return _profile_relative_display(tail, drive=_drive_from_parts(resolved.parts))

    home = Path.home()
    try:
        if resolved.is_relative_to(home):
            return _home_relative_display(
                resolved.relative_to(home),
                drive=_drive_letter(resolved),
            )
    except ValueError:
        pass

    return _native_path_str(resolved)


def _load_user_settings() -> dict:
    path = user_settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_user_settings(data: dict) -> None:
    user_settings_path().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def get_aottg_root_override() -> Path | None:
    raw = _load_user_settings().get(_OVERRIDE_KEY)
    if not raw or not isinstance(raw, str):
        return None
    path = Path(raw)
    if not is_aottg_root(path):
        return None
    return path.resolve()


def set_aottg_root_override(path: Path | None) -> None:
    data = _load_user_settings()
    if path is None:
        data.pop(_OVERRIDE_KEY, None)
    else:
        data[_OVERRIDE_KEY] = str(path.resolve())
    _save_user_settings(data)
    _find_default_aottg_root.cache_clear()


def get_ui_theme() -> str | None:
    raw = _load_user_settings().get(_THEME_KEY)
    if isinstance(raw, str) and raw in {"dark", "light"}:
        return raw
    return None


def set_ui_theme(theme: str) -> None:
    data = _load_user_settings()
    data[_THEME_KEY] = theme
    _save_user_settings(data)


def is_aottg_root(path: Path) -> bool:
    return (path / "CustomLogic").is_dir() and (path / "CustomMap").is_dir()


def _unique_candidate_paths(candidates: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        try:
            key = candidate.resolve()
        except OSError:
            key = candidate
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _windows_aottg_candidates(home: Path) -> list[Path]:
    candidates = [home / "Documents" / "Aottg2"]

    onedrive_roots: list[Path] = []
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        raw = os.environ.get(key)
        if raw:
            onedrive_roots.append(Path(raw))
    onedrive_roots.append(home / "OneDrive")

    for root in onedrive_roots:
        candidates.append(root / "Documents" / "Aottg2")

    try:
        for child in home.iterdir():
            if child.is_dir():
                candidates.append(child / "Documents" / "Aottg2")
    except OSError:
        pass

    return _unique_candidate_paths(candidates)


def standard_aottg_roots() -> list[Path]:
    home = Path.home()
    candidates: list[Path] = []
    if sys.platform == "win32":
        candidates.extend(_windows_aottg_candidates(home))
    elif sys.platform == "darwin":
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
    if start is not None:
        return _find_aottg_root_impl(start)
    override = get_aottg_root_override()
    if override is not None:
        return override
    return _find_default_aottg_root()


def resolve_config_path(
    value: str | Path,
    *,
    app_root_dir: Path | None = None,
    prefer_app: bool = False,
) -> Path:
    """Resolve a config path.

    Bundled assets (prefer_app) resolve under assets/ next to the executable.
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
