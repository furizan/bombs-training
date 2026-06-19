from __future__ import annotations

from pathlib import Path

import pytest

from install import (
    LOGIC_NAME,
    MAP_NAME,
    PACK,
    find_aottg_root,
    install_file,
    is_installed,
    run_install,
)


def test_find_aottg_root_from_custom_logic_child(aottg_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import install

    monkeypatch.setattr(install, "ROOT", Path("/nonexistent/bombs-training"))
    monkeypatch.chdir(aottg_root)
    sub = aottg_root / "CustomLogic"
    assert find_aottg_root(sub) == aottg_root.resolve()


def test_find_aottg_root_returns_none_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import install

    isolated = tmp_path / "isolated"
    isolated.mkdir()
    monkeypatch.setattr(install, "ROOT", isolated / "app")
    monkeypatch.chdir(isolated)
    assert find_aottg_root(isolated) is None


def test_is_installed_false_until_logic_present(aottg_root: Path) -> None:
    assert is_installed(aottg_root) is False
    (aottg_root / "CustomLogic" / LOGIC_NAME).write_text("# stub\n", encoding="utf-8")
    assert is_installed(aottg_root) is True


def test_install_file_skips_existing_without_replace(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    dest = tmp_path / "dest.txt"
    src.write_text("v1", encoding="utf-8")
    dest.write_text("old", encoding="utf-8")

    ok, msg = install_file(src, dest, replace=False)
    assert ok is False
    assert "Skipped" in msg
    assert dest.read_text(encoding="utf-8") == "old"


def test_install_file_replaces_when_requested(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    dest = tmp_path / "dest.txt"
    src.write_text("v2", encoding="utf-8")
    dest.write_text("old", encoding="utf-8")

    ok, msg = install_file(src, dest, replace=True)
    assert ok is True
    assert dest.read_text(encoding="utf-8") == "v2"


@pytest.mark.skipif(
    not (PACK / LOGIC_NAME).is_file() or not (PACK / MAP_NAME).is_file(),
    reason="pack files not present",
)
def test_run_install_copies_pack_files(aottg_root: Path) -> None:
    ok, messages = run_install(aottg_root, replace=True)
    assert ok is True
    assert (aottg_root / "CustomLogic" / LOGIC_NAME).is_file()
    assert (aottg_root / "CustomMap" / MAP_NAME).is_file()
    assert any("Installed" in msg for msg in messages)
