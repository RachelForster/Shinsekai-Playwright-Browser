"""Playwright 浏览器自动化插件。"""

from __future__ import annotations

from pathlib import Path

from sdk.plugin import PluginBase
from sdk.plugin_host_context import PluginHostContext
from sdk.register import PluginCapabilityRegistry
from sdk.types import ToolsTabContribution


class PlaywrightBrowserPlugin(PluginBase):
    """Headless Chromium browser for web scraping, search, and screenshots."""

    @property
    def plugin_id(self) -> str:
        return "com.shinsekai.playwright_browser"

    @property
    def plugin_version(self) -> str:
        return "0.1.0"

    def initialize(
        self,
        register: PluginCapabilityRegistry,
        plugin_root: Path,
        host: PluginHostContext,
    ) -> None:
        from plugins.playwright_browser import browser

        browser.set_plugin_root(str(plugin_root))

        # 注册 LLM 工具
        import plugins.playwright_browser.llm_tool as _  # noqa: F401

        # 注册设置页
        def _build_settings(plg):
            from plugins.playwright_browser.settings_tab import PlaywrightBrowserSettingsTab

            return PlaywrightBrowserSettingsTab(plugin_root)

        register.register_tools_tab(
            ToolsTabContribution(
                tab_id="playwright_browser",
                title="Playwright 浏览器",
                build=_build_settings,
                order=46.0,
            )
        )

    def shutdown(self) -> None:
        from plugins.playwright_browser.browser import shutdown_browser

        shutdown_browser()
