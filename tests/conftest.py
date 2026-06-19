from __future__ import annotations

import json
from pathlib import Path

import pytest

from render import ROOT, load_config, load_persistent_export

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXPORT_FIXTURE = FIXTURES / "minimal_export.json"


@pytest.fixture
def minimal_export() -> dict[str, object]:
    return load_persistent_export(EXPORT_FIXTURE)


@pytest.fixture
def base_config() -> dict:
    return load_config(ROOT / "config.json")


@pytest.fixture
def render_config(tmp_path: Path, base_config: dict) -> tuple[dict, Path]:
    """Config pointing at fixture export and tmp output paths."""
    config = dict(base_config)
    config["persistentDataFile"] = "tests/fixtures/minimal_export.json"
    config["outputImage"] = str(tmp_path / "heatmap.png")
    config["crashOutputImage"] = str(tmp_path / "crashmap.png")

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config, config_path


@pytest.fixture
def aottg_root(tmp_path: Path) -> Path:
    (tmp_path / "CustomLogic").mkdir()
    (tmp_path / "CustomMap").mkdir()
    return tmp_path
