from __future__ import annotations

from pathlib import Path

from PIL import Image

from render import ROOT, load_persistent_export, render_all, render_once, resolve_paths


def test_render_once_produces_outputs(render_config: tuple[dict, Path]) -> None:
    _, config_path = render_config
    assert render_once(config_path) is True

    _, _, _, density_out, crash_out = resolve_paths(config_path)
    assert density_out.is_file()
    assert crash_out.is_file()

    for path in (density_out, crash_out):
        img = Image.open(path)
        assert img.mode == "RGB"
        assert img.size[0] > 0 and img.size[1] > 0


def test_render_all_with_fixture(minimal_export: dict, render_config: tuple[dict, Path]) -> None:
    config, config_path = render_config
    _, export_path, map_path, density_out, crash_out = resolve_paths(config_path)

    render_all(config, minimal_export, map_path, density_out, crash_out)
    assert density_out.is_file()
    assert crash_out.is_file()


def test_render_once_missing_export_returns_false(tmp_path: Path, base_config: dict) -> None:
    import json

    config = dict(base_config)
    config["persistentDataFile"] = str(tmp_path / "missing.txt")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config) + "\n", encoding="utf-8")
    assert render_once(config_path) is False


def test_fixture_export_loads_from_repo() -> None:
    export = load_persistent_export(ROOT / "tests/fixtures/minimal_export.json")
    assert len(export["path"]) > 0
