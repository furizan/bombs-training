from __future__ import annotations

import json
from pathlib import Path

from display_settings import BOOL_SETTINGS, FLOAT_SETTINGS, INT_SETTINGS
from paths import assets_dir
from render import load_config

DISPLAY_DEFAULTS_PATH = assets_dir() / "display_defaults.json"


def test_display_defaults_keys_match_settings_panel() -> None:
    defaults = json.loads(DISPLAY_DEFAULTS_PATH.read_text(encoding="utf-8"))
    panel_keys = {key for key, _ in BOOL_SETTINGS}
    panel_keys |= {key for key, *_ in FLOAT_SETTINGS}
    panel_keys |= {key for key, *_ in INT_SETTINGS}
    assert set(defaults.keys()) == panel_keys


def test_config_json_has_renderer_fields() -> None:
    config = load_config(assets_dir() / "config.json")
    required = (
        "world",
        "mapImage",
        "persistentDataFile",
        "outputImage",
        "crashOutputImage",
        "gridSize",
        "flipZ",
    )
    for key in required:
        assert key in config
