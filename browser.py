"""
Playwright 浏览器单例管理。

安装: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

_browser: object | None = None
_context: object | None = None
_page: object | None = None
_playwright: object | None = None
_plugin_root: str = ""
_bg_executor: object | None = None  # asyncio 环境下持久线程
_use_bg_thread: bool = False  # 一旦检测到 asyncio 就永远走后台线程


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
    global _browser, _context, _page, _playwright, _bg_executor, _use_bg_thread
    if _page is not None:
        try:
            if not _page.is_closed():
                return _page
        except Exception:
            pass
        _page = _context = _browser = _playwright = None

    from playwright.sync_api import sync_playwright

    cfg = _load_config()
    headless = cfg.headless
    browser_type = cfg.browser_type
    launcher = _BROWSER_LAUNCHERS.get(browser_type, _BROWSER_LAUNCHERS["chromium"])
    logger.info("Playwright 正在启动 %s (headless=%s)…", browser_type, headless)

    def _start():
        pw = sync_playwright().start()
        br = launcher(pw, headless)
        ctx = br.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        pg = ctx.new_page()
        return pw, br, ctx, pg

    if _use_bg_thread:
        if _bg_executor is None:
            _bg_executor = ThreadPoolExecutor(max_workers=1)
        _playwright, _browser, _context, _page = _bg_executor.submit(_start).result(timeout=30)
        logger.info("Playwright 浏览器已就绪（后台线程）")
        return _page

    try:
        _playwright = sync_playwright().start()
        _browser = launcher(_playwright, headless)
    except Exception as e:
        if "asyncio" not in str(e).lower():
            raise
        logger.info("asyncio 冲突，此后始终走后台线程运行 playwright…")
        _use_bg_thread = True
        if _bg_executor is None:
            _bg_executor = ThreadPoolExecutor(max_workers=1)
        _playwright, _browser, _context, _page = _bg_executor.submit(_start).result(timeout=30)
        logger.info("Playwright 浏览器已就绪（后台线程）")
        return _page
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


def _with_retry(fn, *args):
    """页面意外关闭时自动重建并重试一次；在后台线程的统一执行器中运行。"""
    global _bg_executor, _use_bg_thread
    if _use_bg_thread:
        if _bg_executor is None:
            _bg_executor = ThreadPoolExecutor(max_workers=1)
        return _bg_executor.submit(_with_retry_sync, fn).result(timeout=30)
    return _with_retry_sync(fn)


def _with_retry_sync(fn):
    global _page, _context, _browser
    try:
        return fn()
    except Exception as e:
        if "TargetClosed" in type(e).__name__ or "closed" in str(e).lower():
            _page = _context = _browser = None
            _ensure_browser()
            return fn()
        raise


def navigate(url: str) -> str:
    """导航到 URL，返回页面标题。"""
    def _do():
        page = _ensure_browser()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"已打开: {page.title()} ({url})"
    return _with_retry(_do)


def get_text() -> str:
    """提取当前页面可见文本（最多 8000 字符）。"""
    def _do():
        page = _ensure_browser()
        return page.inner_text("body")[:8000]
    return _with_retry(_do)


def get_html() -> str:
    """返回当前页面完整 HTML（最多 50000 字符）。"""
    def _do():
        page = _ensure_browser()
        return page.content()[:50000]
    return _with_retry(_do)


def screenshot() -> bytes:
    """截取当前页面全屏截图，返回 PNG 字节。"""
    def _do():
        page = _ensure_browser()
        return page.screenshot(full_page=False, type="png")
    return _with_retry(_do)


def click(selector: str) -> str:
    """点击匹配 CSS 选择器的第一个元素。"""
    def _do():
        page = _ensure_browser()
        page.click(selector, timeout=10000)
        return f"已点击: {selector}"
    return _with_retry(_do)


def fill(selector: str, text: str) -> str:
    """在匹配 CSS 选择器的输入框中填入文本。"""
    def _do():
        page = _ensure_browser()
        page.fill(selector, text, timeout=10000)
        return f"已填入 '{text}' → {selector}"
    return _with_retry(_do)


def search_web(query: str) -> str:
    """用 DuckDuckGo 搜索，返回结果摘要（不依赖 JS）。"""
    from urllib.parse import quote

    def _do():
        page = _ensure_browser()
        page.goto(f"https://html.duckduckgo.com/html/?q={quote(query)}",
                  wait_until="domcontentloaded", timeout=15000)
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
    return _with_retry(_do)


def shutdown_browser() -> None:
    """关闭浏览器并释放资源（后台线程保留以便重新打开）。"""
    global _browser, _context, _page, _playwright, _bg_executor, _use_bg_thread
    _close_safe(_page)
    _close_safe(_context)
    _close_safe(_browser)
    try:
        if _playwright is not None:
            _playwright.stop()
    except Exception:
        pass
    _page = _context = _browser = _playwright = None
    if not _use_bg_thread:
        _close_safe(_bg_executor)
        _bg_executor = None
    logger.info("Playwright 浏览器已关闭")


def _close_safe(obj: object | None) -> None:
    if obj is None:
        return
    try:
        obj.close()
    except Exception:
        pass
