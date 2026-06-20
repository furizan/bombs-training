"""Settings panel field definitions (no Qt dependency)."""

from __future__ import annotations

BOOL_SETTINGS = (
    ("showPathLines", "Lines"),
    ("showPathArrows", "Arrows"),
    ("showPathDots", "Dots"),
    ("showLegend", "Legend"),
)

FLOAT_SETTINGS = (
    ("pathDotRadius", 0.5, 12.0, 0.5, 1),
    ("pathLineWidth", 1.0, 8.0, 0.5, 1),
    ("pathArrowLength", 3.0, 24.0, 1.0, 0),
    ("crashMarkerRadius", 3.0, 24.0, 1.0, 0),
    ("blurSigma", 0.0, 5.0, 0.1, 1),
    ("gamma", 0.1, 2.0, 0.05, 2),
    ("minDensity", 0.0, 1.0, 0.01, 2),
)

INT_SETTINGS = (
    ("pathLineAlpha", 0, 255, 1),
    ("pathArrowAlpha", 0, 255, 1),
    ("pathDotAlpha", 0, 255, 1),
    ("crashMarkerAlpha", 0, 255, 1),
    ("pathDirectionEvery", 1, 50, 1),
)

SETTING_LABELS = {
    "pathLineWidth": "Width",
    "pathLineAlpha": "Alpha",
    "pathDotRadius": "Size",
    "pathDotAlpha": "Alpha",
    "pathArrowLength": "Length",
    "pathArrowAlpha": "Alpha",
    "pathDirectionEvery": "Spacing",
    "crashMarkerRadius": "Size",
    "crashMarkerAlpha": "Alpha",
    "blurSigma": "Blur",
    "gamma": "Gamma",
    "minDensity": "Floor",
}

SETTING_TOOLTIPS = {
    "showPathLines": "Draw colored path segments between crashes",
    "showPathArrows": "Draw direction arrows along the path",
    "showPathDots": "Draw a dot at each recorded sample point",
    "showLegend": "Show the key strip below the map",
    "pathLineWidth": "Path line thickness in pixels",
    "pathLineAlpha": "Path line transparency (0-255)",
    "pathDotRadius": "Sample dot radius in pixels",
    "pathDotAlpha": "Sample dot transparency (0-255)",
    "pathArrowLength": "Direction arrow length in pixels",
    "pathArrowAlpha": "Direction arrow transparency (0-255)",
    "pathDirectionEvery": "Draw an arrow every N sample points",
    "crashMarkerRadius": "Crash marker radius in pixels",
    "crashMarkerAlpha": "Crash marker transparency (0-255)",
    "blurSigma": "Gaussian blur applied to the heatmap",
    "gamma": "Contrast curve for density values",
    "minDensity": "Hide cells below this normalized density",
}

_FLOAT_BY_KEY = {key: (min_v, max_v, step, decimals) for key, min_v, max_v, step, decimals in FLOAT_SETTINGS}
_INT_BY_KEY = {key: (min_v, max_v, step) for key, min_v, max_v, step in INT_SETTINGS}
_INT_KEYS = frozenset(_INT_BY_KEY)

CRASH_MAP_SECTIONS = (
    ("Path line", ("pathLineWidth", "pathLineAlpha")),
    ("Path dots", ("pathDotRadius", "pathDotAlpha")),
    ("Path arrows", ("pathArrowLength", "pathArrowAlpha", "pathDirectionEvery")),
    ("Crash markers", ("crashMarkerRadius", "crashMarkerAlpha")),
)

HEATMAP_SLIDER_ORDER = (
    "blurSigma",
    "gamma",
    "minDensity",
)
