from __future__ import annotations

import json
from pathlib import Path

from app import BOOL_SETTINGS, FLOAT_SETTINGS, INT_SETTINGS
from render import ROOT, load_config

DISPLAY_DEFAULTS_PATH = ROOT / "display_defaults.json"


def test_display_defaults_keys_match_settings_panel() -> None:
    defaults = json.loads(DISPLAY_DEFAULTS_PATH.read_text(encoding="utf-8"))
    panel_keys = {key for key, _ in BOOL_SETTINGS}
    panel_keys |= {key for key, *_ in FLOAT_SETTINGS}
    panel_keys |= {key for key, *_ in INT_SETTINGS}
    assert set(defaults.keys()) == panel_keys


def test_config_json_has_renderer_fields() -> None:
    config = load_config(ROOT / "config.json")
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
