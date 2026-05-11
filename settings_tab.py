"""Playwright 插件设置页 — 挂载到 Tools 标签页。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from plugins.playwright_browser import browser
from plugins.playwright_browser.config_model import (
    PlaywrightBrowserConfig,
    default_config_path,
    load_config,
    save_config,
)


class PlaywrightBrowserSettingsTab(QWidget):
    def __init__(self, plugin_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = plugin_root
        self._cfg_path = default_config_path(plugin_root)

        lay = QVBoxLayout(self)

        box = QGroupBox("Playwright 浏览器设置")
        form = QFormLayout(box)

        hint = QLabel(
            "修改后需重启应用生效。取消勾选可显示浏览器窗口，便于观察操作过程。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        form.addRow(hint)

        cfg = load_config(self._cfg_path)
        self._headless_cb = QCheckBox("无头模式（Headless）")
        self._headless_cb.setChecked(bool(cfg.headless))
        self._headless_cb.toggled.connect(self._on_save)
        form.addRow(self._headless_cb)

        lay.addWidget(box)
        lay.addStretch(1)

    def _on_save(self) -> None:
        cfg = PlaywrightBrowserConfig(headless=self._headless_cb.isChecked())
        save_config(self._cfg_path, cfg)
        browser.set_plugin_root(str(self._root))
