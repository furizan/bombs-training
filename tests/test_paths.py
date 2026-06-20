from __future__ import annotations

from pathlib import Path

import pytest

import paths
from paths import find_aottg_root, resolve_config_path, standard_aottg_roots


@pytest.fixture(autouse=True)
def _clear_aottg_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "user_settings_path", lambda: tmp_path / "user-settings.json")
    paths._find_default_aottg_root.cache_clear()
    yield
    paths._find_default_aottg_root.cache_clear()


def test_format_display_path_uses_tilde_under_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    target = home / ".local" / "share" / "Aottg2" / "PersistentData" / "bombs-training.txt"
    target.parent.mkdir(parents=True)
    target.touch()
    assert paths.format_display_path(target) == "~/.local/share/Aottg2/PersistentData/bombs-training.txt"


def test_format_display_path_redacts_windows_user_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "win32")
    path = Path("C:/Users/Someone/Documents/Aottg2/PersistentData/bombs-training.txt")
    assert (
        paths.format_display_path(path)
        == "C:\\Users\\%USERNAME%\\Documents\\Aottg2\\PersistentData\\bombs-training.txt"
    )


def test_format_display_path_uses_userprofile_under_home_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths.sys, "platform", "win32")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    target = home / "Documents" / "Aottg2" / "PersistentData" / "bombs-training.txt"
    target.parent.mkdir(parents=True)
    target.touch()
    assert (
        paths.format_display_path(target)
        == "C:\\Users\\%USERNAME%\\Documents\\Aottg2\\PersistentData\\bombs-training.txt"
    )


def test_aottg_root_override_persists(aottg_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "standard_aottg_roots", lambda: [])
    monkeypatch.setattr(paths, "app_root", lambda: Path("/nonexistent/bombs-training"))
    monkeypatch.chdir(Path("/tmp"))

    paths.set_aottg_root_override(aottg_root)
    assert paths.find_aottg_root() == aottg_root.resolve()

    paths.set_aottg_root_override(None)
    assert paths.find_aottg_root() is None


def test_aottg_root_override_ignored_when_invalid(
    aottg_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "standard_aottg_roots", lambda: [aottg_root])
    paths.set_aottg_root_override(tmp_path)
    assert paths.find_aottg_root() == aottg_root.resolve()


def test_ui_theme_persists_in_user_settings() -> None:
    assert paths.get_ui_theme() is None
    paths.set_ui_theme("light")
    assert paths.get_ui_theme() == "light"
    paths.set_ui_theme("dark")
    assert paths.get_ui_theme() == "dark"


def test_standard_aottg_roots_includes_linux_default() -> None:
    roots = standard_aottg_roots()
    assert Path.home() / ".local" / "share" / "Aottg2" in roots


def test_standard_aottg_roots_includes_onedrive_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths.sys, "platform", "win32")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    onedrive = home / "OneDrive - Personal"
    onedrive.mkdir()
    monkeypatch.setenv("OneDrive", str(onedrive))

    roots = standard_aottg_roots()
    assert home / "Documents" / "Aottg2" in roots
    assert onedrive / "Documents" / "Aottg2" in roots


def test_find_aottg_root_uses_onedrive_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths.sys, "platform", "win32")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    onedrive = home / "OneDrive - Personal"
    aottg = onedrive / "Documents" / "Aottg2"
    (aottg / "CustomLogic").mkdir(parents=True)
    (aottg / "CustomMap").mkdir()
    monkeypatch.setenv("OneDrive", str(onedrive))
    monkeypatch.setattr(paths, "app_root", lambda: Path("/nonexistent/bombs-training"))
    monkeypatch.chdir(Path("/tmp"))
    paths._find_default_aottg_root.cache_clear()

    assert find_aottg_root() == aottg.resolve()


def test_find_aottg_root_from_custom_logic_child(aottg_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "standard_aottg_roots", lambda: [])
    monkeypatch.setattr(paths, "app_root", lambda: Path("/nonexistent/bombs-training"))
    monkeypatch.chdir(aottg_root)
    sub = aottg_root / "CustomLogic"
    assert find_aottg_root(sub) == aottg_root.resolve()


def test_find_aottg_root_uses_standard_location(aottg_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "standard_aottg_roots", lambda: [aottg_root])
    monkeypatch.setattr(paths, "app_root", lambda: Path("/nonexistent/bombs-training"))
    monkeypatch.chdir(Path("/tmp"))
    assert find_aottg_root() == aottg_root.resolve()


def test_find_aottg_root_returns_none_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    monkeypatch.setattr(paths, "standard_aottg_roots", lambda: [])
    monkeypatch.setattr(paths, "app_root", lambda: isolated / "app")
    monkeypatch.chdir(isolated)
    assert find_aottg_root(isolated) is None


def test_resolve_config_path_prefers_app_bundle(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    map_file = app_dir / "map.png"
    map_file.write_bytes(b"png")

    resolved = resolve_config_path("map.png", app_root_dir=app_dir, prefer_app=True)
    assert resolved == map_file.resolve()


def test_find_aottg_root_uses_standard_location_before_app_parent(
    aottg_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = tmp_path / "nested" / "bombs-training"
    nested.mkdir(parents=True)
    (nested / "CustomLogic").mkdir()
    (nested / "CustomMap").mkdir()

    monkeypatch.setattr(paths, "standard_aottg_roots", lambda: [aottg_root])
    monkeypatch.setattr(paths, "app_root", lambda: nested)
    monkeypatch.chdir(nested)
    assert find_aottg_root() == aottg_root.resolve()


def test_resolve_config_path_prefers_aottg_over_local_copy(
    aottg_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_dir = tmp_path / "desktop-app"
    app_dir.mkdir()
    local_export = app_dir / "PersistentData" / "bombs-training.txt"
    local_export.parent.mkdir(parents=True)
    local_export.write_text("local", encoding="utf-8")

    real_export = aottg_root / "PersistentData" / "bombs-training.txt"
    real_export.parent.mkdir(parents=True, exist_ok=True)
    real_export.write_text("real", encoding="utf-8")

    monkeypatch.setattr(paths, "standard_aottg_roots", lambda: [aottg_root])
    monkeypatch.setattr(paths, "app_root", lambda: app_dir)
    paths._find_default_aottg_root.cache_clear()

    resolved = resolve_config_path(
        "../PersistentData/bombs-training.txt",
        app_root_dir=app_dir,
    )
    assert resolved == real_export.resolve()


def test_resolve_config_path_uses_app_for_non_game_paths(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    fixture = app_dir / "tests" / "fixtures" / "export.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("{}", encoding="utf-8")

    resolved = resolve_config_path("tests/fixtures/export.json", app_root_dir=app_dir)
    assert resolved == fixture.resolve()
