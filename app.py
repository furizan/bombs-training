#!/usr/bin/env python3
"""Bombs-Training viewer — Qt app for all platforms."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
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
from render import ROOT, load_config, render_once, resolve_paths, save_config

CONFIG_PATH = ROOT / "config.json"
DEFAULTS_PATH = ROOT / "display_defaults.json"

BOOL_SETTINGS = (
    ("showPathLines", "Path lines"),
    ("showPathArrows", "Path arrows"),
    ("showPathDots", "Path dots"),
    ("showLegend", "Legend"),
)

FLOAT_SETTINGS = (
    ("pathDotRadius", "Path dot size", 0.5, 12.0, 0.5, 1),
    ("pathLineWidth", "Path line width", 1.0, 8.0, 0.5, 1),
    ("pathArrowLength", "Arrow length", 3.0, 24.0, 1.0, 0),
    ("crashMarkerRadius", "Crash marker size", 3.0, 24.0, 1.0, 0),
    ("crashMarkerSpread", "Crash spread", 0.0, 30.0, 1.0, 0),
    ("blurSigma", "Heatmap blur", 0.0, 5.0, 0.1, 1),
    ("gamma", "Heatmap gamma", 0.1, 2.0, 0.05, 2),
    ("minDensity", "Heatmap min density", 0.0, 1.0, 0.01, 2),
)

INT_SETTINGS = (
    ("pathLineAlpha", "Path line alpha", 0, 255, 1),
    ("pathDirectionEvery", "Arrow every N points", 1, 50, 1),
)


def load_display_defaults() -> dict:
    return json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))


def _values_equal(key: str, current, default) -> bool:
    if isinstance(default, bool):
        return bool(current) == default
    if isinstance(default, int) and key in {k for k, *_ in INT_SETTINGS}:
        return int(round(float(current))) == default
    return abs(float(current) - float(default)) < 1e-6


class SliderSpinRow(QWidget):
    """Slider linked to a spin box for one numeric setting."""

    def __init__(
        self,
        label: str,
        value: float,
        minimum: float,
        maximum: float,
        step: float,
        *,
        decimals: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scale = 10**decimals if decimals else 1
        self._decimals = decimals

        self.label = QLabel(label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(minimum * self._scale))
        self.slider.setMaximum(int(maximum * self._scale))
        self.slider.setSingleStep(max(1, int(step * self._scale)))

        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(decimals)
        self.spin.setSingleStep(step)
        self.spin.setRange(minimum, maximum)
        self.set_value(value)

        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.slider, stretch=1)
        row.addWidget(self.spin)

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
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
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
        body = QWidget()
        form = QFormLayout(body)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        display = QGroupBox("Crash map")
        display_layout = QVBoxLayout(display)
        for key, label in BOOL_SETTINGS:
            self._add_bool_setting(display_layout, key, label)

        for key, label, min_v, max_v, step, decimals in FLOAT_SETTINGS:
            if key in ("blurSigma", "gamma", "minDensity"):
                continue
            self._add_slider_setting(display_layout, key, label, min_v, max_v, step, decimals, self._float_rows)

        for key, label, min_v, max_v, step in INT_SETTINGS:
            self._add_slider_setting(display_layout, key, label, min_v, max_v, step, 0, self._int_rows)

        form.addRow(display)

        heatmap = QGroupBox("Heatmap")
        heatmap_layout = QVBoxLayout(heatmap)
        for key, label, min_v, max_v, step, decimals in FLOAT_SETTINGS:
            if key not in ("blurSigma", "gamma", "minDensity"):
                continue
            self._add_slider_setting(heatmap_layout, key, label, min_v, max_v, step, decimals, self._float_rows)
        form.addRow(heatmap)

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

    def _add_bool_setting(self, layout: QVBoxLayout, key: str, label: str) -> None:
        row = QHBoxLayout()
        box = QCheckBox(label)
        box.toggled.connect(self._on_change)
        self._boxes[key] = box
        row.addWidget(box)
        row.addStretch()
        row.addWidget(self._make_reset_button(key))
        layout.addLayout(row)

    def _add_slider_setting(
        self,
        layout: QVBoxLayout,
        key: str,
        label: str,
        min_v: float,
        max_v: float,
        step: float,
        decimals: int,
        store: dict[str, SliderSpinRow],
    ) -> None:
        header = QHBoxLayout()
        header.addWidget(QLabel(label))
        header.addStretch()
        header.addWidget(self._make_reset_button(key))
        layout.addLayout(header)

        row = SliderSpinRow(label, 0.0, min_v, max_v, step, decimals=decimals)
        row.label.hide()
        row.slider.valueChanged.connect(self._on_change)
        row.spin.valueChanged.connect(self._on_change)
        store[key] = row
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
            button.setEnabled(not _values_equal(key, self._current_value(key), default))

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
        self.setStyleSheet("background: #1a1a1a; color: #aaa;")
        self._source: QPixmap | None = None

    def set_source(self, pixmap: QPixmap | None, *, placeholder: str = "") -> None:
        self._source = pixmap
        if pixmap is None or pixmap.isNull():
            self.setText(placeholder or "Waiting for a run…")
            self.setPixmap(QPixmap())
            return
        self.setText("")
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bombs-Training")
        self.resize(1100, 720)

        self._config_path = CONFIG_PATH
        self._view = "crash"
        self._last_mtime = 0.0

        self._map = MapLabel()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._map)

        self._settings = SettingsPanel(self)
        self._settings.setMinimumWidth(280)
        self._settings.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
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
        self._maybe_install()
        self._show_current()

    def _build_menu(self) -> None:
        self._settings_action = QAction("Settings", self)
        self._settings_action.setCheckable(True)
        self._settings_action.setChecked(False)
        self._settings_action.triggered.connect(self._toggle_settings)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addAction(self._settings_action)

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
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
