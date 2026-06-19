#!/usr/bin/env python3
"""Bombs-Training viewer — Qt app for all platforms."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QClipboard, QColor, QImage, QKeySequence, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from install import LOGIC_NAME, MAP_NAME, default_aottg_root, find_aottg_root, is_installed, run_install
from render import ROOT, flatten_rgba, load_config, render_once, resolve_paths, save_config

CONFIG_PATH = ROOT / "config.json"
DEFAULTS_PATH = ROOT / "display_defaults.json"

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
    "pathLineAlpha": "Path line transparency (0–255)",
    "pathDotRadius": "Sample dot radius in pixels",
    "pathDotAlpha": "Sample dot transparency (0–255)",
    "pathArrowLength": "Direction arrow length in pixels",
    "pathArrowAlpha": "Direction arrow transparency (0–255)",
    "pathDirectionEvery": "Draw an arrow every N sample points",
    "crashMarkerRadius": "Crash marker radius in pixels",
    "crashMarkerAlpha": "Crash marker transparency (0–255)",
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

THEMES = ("dark", "light")


def fusion_dark_palette() -> QPalette:
    """Standard Qt Fusion dark palette."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(127, 127, 127))
    return palette


def apply_ui_theme(app: QApplication, theme: str) -> None:
    """Apply Qt's built-in dark or light styling to the whole application."""
    scheme = Qt.ColorScheme.Dark if theme == "dark" else Qt.ColorScheme.Light
    app.styleHints().setColorScheme(scheme)

    # Fusion is Qt's cross-platform style; palette swap gives a reliable dark/light toggle.
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    if theme == "dark":
        app.setPalette(fusion_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())

    for widget in app.allWidgets():
        if isinstance(widget, MapLabel) and widget.has_image():
            widget.update()
            continue
        style = widget.style()
        if style is None:
            continue
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


def load_ui_theme(config_path: Path = CONFIG_PATH) -> str:
    theme = load_config(config_path).get("uiTheme", "dark")
    return theme if theme in THEMES else "dark"


def load_display_defaults() -> dict:
    return json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))


def _values_equal(key: str, current, default) -> bool:
    if isinstance(default, bool):
        return bool(current) == default
    if isinstance(default, int) and key in _INT_KEYS:
        return int(round(float(current))) == default
    return abs(float(current) - float(default)) < 1e-6


class SliderSpinRow(QWidget):
    """One setting: label, slider, value, optional reset — single row."""

    _LABEL_WIDTH = 58
    _SPIN_WIDTH = 52

    def __init__(
        self,
        label: str,
        value: float,
        minimum: float,
        maximum: float,
        step: float,
        *,
        decimals: int = 0,
        reset_button: QToolButton | None = None,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scale = 10**decimals if decimals else 1
        self._decimals = decimals

        self.label = QLabel(label)
        self.label.setMinimumWidth(self._LABEL_WIDTH)
        self.label.setMaximumWidth(self._LABEL_WIDTH)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if tooltip:
            self.label.setToolTip(tooltip)
            self.setToolTip(tooltip)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(minimum * self._scale))
        self.slider.setMaximum(int(maximum * self._scale))
        self.slider.setSingleStep(max(1, int(step * self._scale)))

        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(decimals)
        self.spin.setSingleStep(step)
        self.spin.setRange(minimum, maximum)
        self.spin.setFixedWidth(self._SPIN_WIDTH)
        if tooltip:
            self.spin.setToolTip(tooltip)
            self.slider.setToolTip(tooltip)
        self.set_value(value)

        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.label)
        row.addWidget(self.slider, stretch=1)
        row.addWidget(self.spin)
        if reset_button is not None:
            row.addWidget(reset_button)

    def set_value(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.spin.blockSignals(True)
        self.slider.setValue(int(round(value * self._scale)))
        self.spin.setValue(value)
        self.slider.blockSignals(False)
        self.spin.blockSignals(False)

    def value(self) -> float:
        return float(self.spin.value())

    def _from_slider(self, raw: int) -> None:
        self.spin.blockSignals(True)
        self.spin.setValue(raw / self._scale)
        self.spin.blockSignals(False)

    def _from_spin(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(value * self._scale)))
        self.slider.blockSignals(False)


def pil_to_pixmap(image) -> QPixmap:
    rgb = flatten_rgba(image) if image.mode == "RGBA" else image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class SettingsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = CONFIG_PATH
        self._defaults = load_display_defaults()
        self._loading = False
        self._boxes: dict[str, QCheckBox] = {}
        self._float_rows: dict[str, SliderSpinRow] = {}
        self._int_rows: dict[str, SliderSpinRow] = {}
        self._reset_buttons: dict[str, QToolButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Settings")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        crash_group = QGroupBox("Crash map")
        crash_layout = QVBoxLayout(crash_group)
        crash_layout.setSpacing(8)

        layers_box = QGroupBox("Layers")
        layers_grid = QGridLayout(layers_box)
        layers_grid.setHorizontalSpacing(12)
        layers_grid.setVerticalSpacing(4)
        for index, (key, label) in enumerate(BOOL_SETTINGS):
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(4)
            box = QCheckBox(label)
            box.toggled.connect(self._on_change)
            tip = SETTING_TOOLTIPS.get(key, "")
            if tip:
                box.setToolTip(tip)
            self._boxes[key] = box
            cell_layout.addWidget(box, stretch=1)
            cell_layout.addWidget(self._make_reset_button(key))
            layers_grid.addWidget(cell, index // 2, index % 2)
        crash_layout.addWidget(layers_box)

        for section_title, keys in CRASH_MAP_SECTIONS:
            self._add_section(crash_layout, section_title, keys)

        body_layout.addWidget(crash_group)

        heatmap_group = QGroupBox("Heatmap")
        heatmap_layout = QVBoxLayout(heatmap_group)
        heatmap_layout.setSpacing(4)
        for key in HEATMAP_SLIDER_ORDER:
            self._add_setting_row(heatmap_layout, key)
        body_layout.addWidget(heatmap_group)
        body_layout.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

        reset_all = QPushButton("Reset All to Defaults")
        reset_all.clicked.connect(self._reset_all)
        outer.addWidget(reset_all)

        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(350)
        self._apply_timer.timeout.connect(self._apply)

        self.reload()

    def _make_reset_button(self, key: str) -> QToolButton:
        button = QToolButton()
        button.setText("↺")
        button.setToolTip("Reset to default")
        button.setAutoRaise(True)
        button.clicked.connect(lambda: self._reset_key(key))
        self._reset_buttons[key] = button
        return button

    def _style_reset_button(self, button: QToolButton, *, active: bool) -> None:
        if active:
            button.setEnabled(True)
            button.setStyleSheet(
                "QToolButton { color: palette(link); }"
                "QToolButton:hover { color: palette(highlight); }"
            )
        else:
            button.setEnabled(False)
            button.setStyleSheet("QToolButton { color: palette(placeholder-text); }")

    def refresh_theme(self) -> None:
        self._update_reset_states()

    def _add_section(self, parent_layout: QVBoxLayout, title: str, keys: tuple[str, ...]) -> None:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 6, 8, 8)
        for key in keys:
            self._add_setting_row(layout, key)
        parent_layout.addWidget(box)

    def _add_setting_row(self, layout: QVBoxLayout, key: str) -> None:
        label = SETTING_LABELS.get(key, key)
        tooltip = SETTING_TOOLTIPS.get(key, "")
        reset = self._make_reset_button(key)
        if key in _FLOAT_BY_KEY:
            min_v, max_v, step, decimals = _FLOAT_BY_KEY[key]
            row = SliderSpinRow(
                label,
                0.0,
                min_v,
                max_v,
                step,
                decimals=decimals,
                reset_button=reset,
                tooltip=tooltip,
            )
            row.slider.valueChanged.connect(self._on_change)
            row.spin.valueChanged.connect(self._on_change)
            self._float_rows[key] = row
        else:
            min_v, max_v, step = _INT_BY_KEY[key]
            row = SliderSpinRow(
                label,
                0.0,
                min_v,
                max_v,
                step,
                decimals=0,
                reset_button=reset,
                tooltip=tooltip,
            )
            row.slider.valueChanged.connect(self._on_change)
            row.spin.valueChanged.connect(self._on_change)
            self._int_rows[key] = row
        layout.addWidget(row)

    def _current_value(self, key: str):
        if key in self._boxes:
            return self._boxes[key].isChecked()
        if key in self._int_rows:
            return int(round(self._int_rows[key].value()))
        return self._float_rows[key].value()

    def _set_value(self, key: str, value) -> None:
        if key in self._boxes:
            self._boxes[key].setChecked(bool(value))
        elif key in self._int_rows:
            self._int_rows[key].set_value(float(int(value)))
        else:
            self._float_rows[key].set_value(float(value))

    def _update_reset_states(self) -> None:
        for key, button in self._reset_buttons.items():
            default = self._defaults[key]
            active = not _values_equal(key, self._current_value(key), default)
            self._style_reset_button(button, active=active)

    def reload(self) -> None:
        self._loading = True
        config = load_config(self._config_path)
        for key in self._defaults:
            if key in config:
                self._set_value(key, config[key])
            else:
                self._set_value(key, self._defaults[key])
        self._loading = False
        self._update_reset_states()

    def _reset_key(self, key: str) -> None:
        self._loading = True
        self._set_value(key, self._defaults[key])
        self._loading = False
        self._update_reset_states()
        self._apply_timer.start()

    def _reset_all(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset all settings?",
            "Reset every display setting to its default?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._loading = True
        for key, value in self._defaults.items():
            self._set_value(key, value)
        self._loading = False
        self._update_reset_states()
        self._apply_timer.start()

    def _on_change(self) -> None:
        if self._loading:
            return
        self._update_reset_states()
        self._apply_timer.start()

    def _collect_config(self) -> dict:
        config = load_config(self._config_path)
        for key in self._defaults:
            config[key] = self._current_value(key)
        return config

    def _apply(self) -> None:
        save_config(self._config_path, self._collect_config())
        self._update_reset_states()
        window = self.window()
        if isinstance(window, MainWindow):
            window.on_settings_applied()


class MapLabel(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setAutoFillBackground(True)
        self.setBackgroundRole(QPalette.ColorRole.Base)
        self._source: QPixmap | None = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.refresh_appearance()

    def has_image(self) -> bool:
        return self._source is not None and not self._source.isNull()

    def refresh_appearance(self) -> None:
        if not self.has_image():
            self.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            return
        self.setForegroundRole(QPalette.ColorRole.WindowText)
        self.setStyleSheet("")
        self._fit()

    def set_source(self, pixmap: QPixmap | None, *, placeholder: str = "") -> None:
        self._source = pixmap
        if pixmap is None or pixmap.isNull():
            self.setText(placeholder or "Waiting for a run…")
            self.setPixmap(QPixmap())
            self.refresh_appearance()
            return
        self.setText("")
        self.refresh_appearance()
        self._fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        if self._source is None or self._source.isNull():
            return
        scaled = self._source.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def _show_context_menu(self, pos) -> None:
        if self._source is None or self._source.isNull():
            return
        menu = QMenu(self.window())
        menu.setStyleSheet(
            "QMenu { background: palette(window); color: palette(window-text); }"
            "QMenu::item { padding: 4px 20px; }"
            "QMenu::item:selected { background: palette(highlight); color: palette(highlighted-text); }"
        )
        copy_action = QAction("Copy", menu)
        copy_action.triggered.connect(self._copy_image)
        menu.addAction(copy_action)
        menu.exec(self.mapToGlobal(pos))

    def _copy_image(self) -> None:
        if self._source is None or self._source.isNull():
            return
        QApplication.clipboard().setPixmap(self._source, QClipboard.Mode.Clipboard)
        window = self.window()
        if isinstance(window, MainWindow):
            window.statusBar().showMessage("Copied to clipboard.", 2000)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bombs-Training")
        self.resize(1100, 720)

        self._config_path = CONFIG_PATH
        self._view = "crash"
        self._last_mtime = 0.0
        self._theme = "dark"

        self._map = MapLabel()
        self._map_scroll = QScrollArea()
        self._map_scroll.setWidgetResizable(True)
        self._map_scroll.setWidget(self._map)
        self._map_scroll.setAutoFillBackground(True)
        self._map_scroll.setBackgroundRole(QPalette.ColorRole.Base)

        self._settings = SettingsPanel(self)
        self._settings.setMinimumWidth(300)
        self._settings.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._map_scroll)
        splitter.addWidget(self._settings)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        self._splitter = splitter
        self.setCentralWidget(splitter)

        self._settings.hide()

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._build_menu()
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._toggle_view)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll_export)
        self._timer.start()

        self._refresh_paths()
        self._load_theme()
        self._maybe_install()
        self._show_current()

    def _load_theme(self) -> None:
        self._theme = load_ui_theme(self._config_path)
        self._apply_theme()

    def _save_theme(self) -> None:
        config = load_config(self._config_path)
        config["uiTheme"] = self._theme
        save_config(self._config_path, config)

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_ui_theme(app, self._theme)
        self._map.refresh_appearance()
        self._settings.refresh_theme()
        if hasattr(self, "_theme_button"):
            self._theme_button.setText("Light" if self._theme == "dark" else "Dark")

    def _toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        self._apply_theme()
        self._save_theme()

    def _build_menu(self) -> None:
        self._settings_action = QAction("Settings", self)
        self._settings_action.setCheckable(True)
        self._settings_action.setChecked(False)
        self._settings_action.triggered.connect(self._toggle_settings)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        self._theme_button = QPushButton("Light")
        self._theme_button.setToolTip("Switch between dark and light theme")
        self._theme_button.clicked.connect(self._toggle_theme)
        toolbar.addWidget(self._theme_button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        toolbar.addSeparator()
        toolbar.addAction(self._settings_action)
        self._apply_theme()

        menu = self.menuBar().addMenu("&File")
        menu.addAction("Install to AoTTG2…", self._install)
        menu.addSeparator()
        menu.addAction("E&xit", self.close)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self._settings_action)
        view_menu.addSeparator()

        self._toggle_view_action = QAction("Toggle map\tSpace", self)
        self._toggle_view_action.triggered.connect(self._toggle_view)
        view_menu.addAction(self._toggle_view_action)

        self._crash_action = QAction("Show &crash map", self)
        self._crash_action.triggered.connect(lambda: self._set_view("crash"))
        view_menu.addAction(self._crash_action)

        self._heatmap_action = QAction("Show &heatmap", self)
        self._heatmap_action.triggered.connect(lambda: self._set_view("heatmap"))
        view_menu.addAction(self._heatmap_action)

    def _toggle_settings(self, visible: bool) -> None:
        self._settings.setVisible(visible)
        if visible:
            width = max(self._splitter.width(), 1)
            self._splitter.setSizes([max(width - 300, 400), 300])

    def on_settings_applied(self) -> None:
        self._refresh_paths()
        if not self._export_path.is_file():
            self._status.showMessage("Settings saved.", 3000)
            return
        try:
            render_once(self._config_path)
            self._show_current()
            self._status.showMessage("Settings applied.", 3000)
        except (json.JSONDecodeError, OSError, ValueError) as err:
            self._status.showMessage(f"Render failed: {err}", 5000)

    def _refresh_paths(self) -> None:
        self._config, self._export_path, self._map_path, self._density_out, self._crash_out = resolve_paths(
            self._config_path
        )
        self._paths = {"heatmap": self._density_out, "crash": self._crash_out}

    def _maybe_install(self) -> None:
        root = default_aottg_root()
        if root is None or is_installed(root):
            return
        answer = QMessageBox.question(
            self,
            "Install Bombs-Training",
            "Install custom logic and map into your AoTTG2 folder?\n"
            f"(adds {LOGIC_NAME} and {MAP_NAME}.)",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._install_to(root)

    def _pick_aottg_root(self) -> Path | None:
        root = default_aottg_root()
        if root is not None:
            return root
        folder = QFileDialog.getExistingDirectory(self, "Select AoTTG2 data folder")
        if not folder:
            return None
        path = Path(folder)
        if not find_aottg_root(path):
            QMessageBox.warning(self, "Invalid folder", "That folder needs CustomLogic and CustomMap.")
            return None
        return find_aottg_root(path)

    def _install(self) -> None:
        root = self._pick_aottg_root()
        if root is None:
            return
        replace = True
        if is_installed(root):
            answer = QMessageBox.question(
                self,
                "Replace files?",
                "Bombs-Training is already installed. Replace existing files?",
            )
            replace = answer == QMessageBox.StandardButton.Yes
        self._install_to(root, replace=replace)

    def _install_to(self, root: Path, *, replace: bool = True) -> None:
        ok, messages = run_install(root, replace=replace)
        detail = "\n".join(messages)
        if ok:
            QMessageBox.information(
                self,
                "Installed",
                detail
                + "\n\nIn-game: load custom map "
                f"{MAP_NAME.removesuffix('.txt')}, game mode {LOGIC_NAME.removesuffix('.cl')}.",
            )
        else:
            QMessageBox.warning(self, "Install", detail)

    def _set_view(self, view: str) -> None:
        if view not in self._paths:
            return
        self._view = view
        self._show_current()

    def _toggle_view(self) -> None:
        self._set_view("heatmap" if self._view == "crash" else "crash")

    def _show_current(self) -> None:
        path = self._paths[self._view]
        self.setWindowTitle(f"Bombs-Training - {path.name}")
        if not path.is_file():
            self._map.set_source(None, placeholder=f"Waiting for {path.name}…\nFinish a run.")
            return
        from PIL import Image

        self._map.set_source(pil_to_pixmap(Image.open(path)))

    def _poll_export(self) -> None:
        if not self._export_path.is_file():
            self._status.showMessage("Waiting for PersistentData export…")
            return
        mtime = self._export_path.stat().st_mtime
        if mtime <= self._last_mtime:
            return
        self._last_mtime = mtime
        try:
            if render_once(self._config_path):
                self._show_current()
                self._status.showMessage(f"Updated {self._paths[self._view].name}", 5000)
        except (json.JSONDecodeError, OSError, ValueError) as err:
            self._status.showMessage(f"Skipped incomplete export: {err}", 5000)


def main() -> int:
    if not (ROOT / "map.png").is_file():
        print(f"map.png not found in {ROOT}", file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    apply_ui_theme(app, load_ui_theme())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
