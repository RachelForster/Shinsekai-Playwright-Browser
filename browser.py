"""
Playwright 浏览器单例管理。

安装: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

_browser: object | None = None
_context: object | None = None
_page: object | None = None
_plugin_root: str = ""


_BROWSER_LAUNCHERS = {
    "chromium": lambda pw, headless: pw.chromium.launch(headless=headless),
    "firefox": lambda pw, headless: pw.firefox.launch(headless=headless),
    "webkit": lambda pw, headless: pw.webkit.launch(headless=headless),
    "msedge": lambda pw, headless: pw.chromium.launch(channel="msedge", headless=headless),
    "chrome": lambda pw, headless: pw.chromium.launch(channel="chrome", headless=headless),
}


def _load_config():
    from pathlib import Path

    from plugins.playwright_browser.config_model import default_config_path, load_config

    root = Path(_plugin_root) if _plugin_root else Path(__file__).parent
    return load_config(default_config_path(root))


def set_plugin_root(root: str) -> None:
    global _plugin_root
    _plugin_root = root


def _ensure_browser():
    global _browser, _context, _page
    if _page is not None:
        return _page
    from playwright.sync_api import sync_playwright

    cfg = _load_config()
    headless = cfg.headless
    browser_type = cfg.browser_type
    launcher = _BROWSER_LAUNCHERS.get(browser_type, _BROWSER_LAUNCHERS["chromium"])
    logger.info("Playwright 正在启动 %s (headless=%s)…", browser_type, headless)
    _pw = sync_playwright().start()
    _browser = launcher(_pw, headless)
    _context = _browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    )
    _page = _context.new_page()
    logger.info("Playwright 浏览器已就绪")
    return _page


def navigate(url: str) -> str:
    """导航到 URL，返回页面标题。"""
    page = _ensure_browser()
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    title = page.title()
    return f"已打开: {title} ({url})"


def get_text() -> str:
    """提取当前页面可见文本（最多 8000 字符）。"""
    page = _ensure_browser()
    text = page.inner_text("body")
    return text[:8000]


def get_html() -> str:
    """返回当前页面完整 HTML（最多 50000 字符）。"""
    page = _ensure_browser()
    return page.content()[:50000]


def screenshot() -> bytes:
    """截取当前页面全屏截图，返回 PNG 字节。"""
    page = _ensure_browser()
    return page.screenshot(full_page=False, type="png")


def click(selector: str) -> str:
    """点击匹配 CSS 选择器的第一个元素。"""
    page = _ensure_browser()
    page.click(selector, timeout=10000)
    return f"已点击: {selector}"


def fill(selector: str, text: str) -> str:
    """在匹配 CSS 选择器的输入框中填入文本。"""
    page = _ensure_browser()
    page.fill(selector, text, timeout=10000)
    return f"已填入 '{text}' → {selector}"


def search_web(query: str) -> str:
    """用 DuckDuckGo 搜索，返回结果摘要（不依赖 JS）。"""
    page = _ensure_browser()
    from urllib.parse import quote

    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    results = page.query_selector_all(".result__body")
    if not results:
        return "未找到搜索结果。"
    lines: list[str] = []
    for i, r in enumerate(results[:8]):
        title_el = r.query_selector(".result__title")
        snippet_el = r.query_selector(".result__snippet")
        link_el = r.query_selector(".result__url")
        title = title_el.inner_text().strip() if title_el else ""
        snippet = snippet_el.inner_text().strip() if snippet_el else ""
        link = link_el.inner_text().strip() if link_el else ""
        lines.append(f"{i + 1}. {title}\n   {snippet}\n   {link}")
    return "\n\n".join(lines)


def shutdown_browser() -> None:
    """关闭浏览器并释放资源。"""
    global _browser, _context, _page
    try:
        if _page is not None:
            _page.close()
    except Exception:
        pass
    try:
        if _context is not None:
            _context.close()
    except Exception:
        pass
    try:
        if _browser is not None:
            _browser.close()
    except Exception:
        pass
    _page = _context = _browser = None
    logger.info("Playwright 浏览器已关闭")
