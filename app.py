#!/usr/bin/env python3
"""Bombs-Training viewer — Qt app for all platforms."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from install import LOGIC_NAME, MAP_NAME, default_aottg_root, find_aottg_root, is_installed, run_install
from render import ROOT, load_config, render_once, resolve_paths, save_config

CONFIG_PATH = ROOT / "config.json"

PATH_OPTIONS = (
    ("showPathLines", "Path lines"),
    ("showPathArrows", "Path arrows"),
    ("showPathDots", "Path dots"),
    ("showLegend", "Legend"),
)


def pil_to_pixmap(image) -> QPixmap:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Display settings")
        self._config = json.loads(json.dumps(config))
        self._boxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        for key, label in PATH_OPTIONS:
            box = QCheckBox(label)
            box.setChecked(bool(self._config.get(key, True)))
            self._boxes[key] = box
            layout.addWidget(box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def config(self) -> dict:
        for key, box in self._boxes.items():
            self._config[key] = box.isChecked()
        return self._config


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
        self.resize(960, 720)

        self._config_path = CONFIG_PATH
        self._view = "crash"
        self._last_mtime = 0.0

        self._map = MapLabel()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._map)
        self.setCentralWidget(scroll)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._build_menu()
        QShortcut(QKeySequence(Qt.Key.Key_Tab), self, self._toggle_view)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._toggle_view)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll_export)
        self._timer.start()

        self._refresh_paths()
        self._maybe_install()
        self._show_current()

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")
        menu.addAction("Install to AoTTG2…", self._install)
        menu.addAction("Settings…", self._settings)
        menu.addSeparator()
        menu.addAction("Show &crash map", lambda: self._set_view("crash"))
        menu.addAction("Show &heatmap", lambda: self._set_view("heatmap"))
        menu.addSeparator()
        menu.addAction("E&xit", self.close)

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

    def _settings(self) -> None:
        dialog = SettingsDialog(load_config(self._config_path), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        save_config(self._config_path, dialog.config())
        self._refresh_paths()
        if self._export_path.is_file():
            try:
                render_once(self._config_path)
                self._show_current()
                self._status.showMessage("Settings applied.", 3000)
            except (json.JSONDecodeError, OSError, ValueError) as err:
                QMessageBox.warning(self, "Render failed", str(err))

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
