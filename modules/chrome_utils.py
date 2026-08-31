"""Cross-platform browser screenshots backed by Playwright.

The public functions keep their historical names because the Wiki modules use
them, but the implementation is no longer tied to Chrome or the CDP protocol.
Playwright can drive Chromium, Firefox, and WebKit on Linux, macOS, and
Windows. A browser is kept per worker thread and pages/contexts are isolated
per screenshot, avoiding process startup cost for every image.
"""

import atexit
import base64
import logging
import os
import shutil
import threading
import time
import uuid

from bot.config import section

logger = logging.getLogger("basic-bot.browser")

_browser_config = section("browser")
BROWSER_NAME = str(_browser_config.get("browser", "auto")).strip().lower() or "auto"
BROWSER_PATH = str(_browser_config.get("path", "")).strip()
HEADLESS = bool(_browser_config.get("headless", True))
PAGE_LOAD_TIMEOUT_SECONDS = float(_browser_config["page_load_timeout_seconds"])
ELEMENT_TIMEOUT_SECONDS = float(_browser_config["element_timeout_seconds"])

_VALID_BROWSERS = {"auto", "chromium", "firefox", "webkit"}
if BROWSER_NAME not in _VALID_BROWSERS:
    raise ValueError(
        f"browser.browser must be one of {sorted(_VALID_BROWSERS)}, got {BROWSER_NAME!r}"
    )

_browser_cache_lock = threading.RLock()
_browser_choice_cache: tuple[str, str | None] | None = None
_thread_session = threading.local()
_sessions: set["_BrowserSession"] = set()
_sessions_lock = threading.RLock()


def _which_candidates(*names: str) -> list[str]:
    return [path for name in names if (path := shutil.which(name))]


def _is_macos() -> bool:
    return os.name == "posix" and os.uname().sysname == "Darwin"


def _system_browser_candidates(browser_name: str) -> list[str]:
    """Return executable candidates in priority order for one browser family."""
    if browser_name == "firefox":
        candidates = _which_candidates("firefox", "firefox-esr")
        if os.name == "nt":
            candidates.extend(
                os.path.expandvars(path)
                for path in (
                    r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
                    r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
                    r"%LOCALAPPDATA%\Mozilla Firefox\firefox.exe",
                )
            )
        elif _is_macos():
            candidates.append("/Applications/Firefox.app/Contents/MacOS/firefox")
        else:
            candidates.extend(("/usr/bin/firefox", "/usr/bin/firefox-esr"))
        return candidates

    if browser_name == "webkit":
        # WebKit is normally supplied by Playwright rather than the OS.
        return []

    candidates = _which_candidates(
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "chrome",
        "microsoft-edge-stable",
        "microsoft-edge",
        "msedge",
    )
    if os.name == "nt":
        candidates.extend(
            os.path.expandvars(path)
            for path in (
                r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
                r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            )
        )
    elif _is_macos():
        candidates.extend(
            (
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            )
        )
    else:
        candidates.extend(
            (
                "/usr/bin/google-chrome-stable",
                "/usr/bin/google-chrome",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
            )
        )
    return candidates


def _existing_path(path: str) -> str | None:
    if not path or not os.path.isfile(path):
        return None
    if os.name != "nt" and not os.access(path, os.X_OK):
        return None
    return os.path.abspath(path)


def _detect_browser() -> tuple[str, str | None] | None:
    """Choose a Playwright browser and optional system executable."""
    if BROWSER_PATH:
        executable = _existing_path(BROWSER_PATH)
        if not executable:
            logger.warning("配置的浏览器路径不存在或不可执行: %s", BROWSER_PATH)
        else:
            if BROWSER_NAME != "auto":
                return BROWSER_NAME, executable
            inferred = "firefox" if "firefox" in executable.lower() else "chromium"
            return inferred, executable

    families = [BROWSER_NAME] if BROWSER_NAME != "auto" else ["chromium", "firefox", "webkit"]
    for family in families:
        for candidate in _system_browser_candidates(family):
            executable = _existing_path(candidate)
            if executable:
                return family, executable

    # Let Playwright look for its own managed browser installation.
    if BROWSER_NAME != "auto":
        return BROWSER_NAME, None
    return "chromium", None


def _browser_choice() -> tuple[str, str | None] | None:
    global _browser_choice_cache
    with _browser_cache_lock:
        if _browser_choice_cache is None:
            _browser_choice_cache = _detect_browser()
            if _browser_choice_cache:
                family, executable = _browser_choice_cache
                logger.info(
                    "浏览器后端: %s%s",
                    family,
                    f" ({executable})" if executable else " (Playwright managed)",
                )
            else:
                logger.error("没有可用的浏览器后端")
        return _browser_choice_cache


def get_browser_path() -> str | None:
    """Return the selected executable, or None for a Playwright-managed one."""
    choice = _browser_choice()
    return choice[1] if choice else None


def reset_browser_path_cache():
    """Reset browser discovery and close this thread's cached browser."""
    global _browser_choice_cache
    _close_thread_session()
    with _browser_cache_lock:
        _browser_choice_cache = None


class _BrowserSession:
    def __init__(self, family: str, executable: str | None):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "缺少 Playwright，请先执行: python -m pip install -r requirements.txt"
            ) from error

        self.playwright = sync_playwright().start()
        browser_type = getattr(self.playwright, family)
        launch_options = {"headless": HEADLESS}
        if executable:
            launch_options["executable_path"] = executable
        if family == "chromium":
            launch_options["args"] = ["--disable-dev-shm-usage", "--no-sandbox"]
        try:
            self.browser = browser_type.launch(**launch_options)
        except Exception:
            self.playwright.stop()
            raise
        self.family = family
        self.executable = executable

    def close(self):
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self.playwright.stop()
        except Exception:
            pass


def _get_session() -> _BrowserSession:
    session = getattr(_thread_session, "session", None)
    if session is not None:
        try:
            if session.browser.is_connected():
                return session
        except Exception:
            pass
        _close_thread_session()

    choice = _browser_choice()
    if not choice:
        raise RuntimeError("没有检测到可用的浏览器")
    family, executable = choice
    try:
        session = _BrowserSession(family, executable)
    except Exception as error:
        # System Firefox/Chromium builds can be incompatible with Playwright's
        # protocol. In auto mode, try the managed Chromium fallback before
        # reporting a deployment error.
        if BROWSER_NAME == "auto" and executable:
            try:
                session = _BrowserSession("chromium", None)
                logger.info("系统 %s 不兼容，已切换到 Playwright 管理的 Chromium", family)
            except Exception:
                raise RuntimeError(
                    f"无法启动 {family} ({executable})。请安装 Playwright 浏览器运行时："
                    "`python -m playwright install chromium`"
                ) from error
        elif executable:
            raise RuntimeError(
                f"无法启动 {family} ({executable})。请确认浏览器版本兼容，"
                "或运行 `python -m playwright install chromium firefox webkit`。"
            ) from error
        else:
            raise RuntimeError(
                f"无法启动 Playwright {family}，请运行 `python -m playwright install {family}`"
            ) from error
    _thread_session.session = session
    with _sessions_lock:
        _sessions.add(session)
    return session


def _close_thread_session():
    session = getattr(_thread_session, "session", None)
    if session is None:
        return
    try:
        session.close()
    finally:
        with _sessions_lock:
            _sessions.discard(session)
        _thread_session.session = None


def _close_all_sessions():
    with _sessions_lock:
        sessions = list(_sessions)
        _sessions.clear()
    for session in sessions:
        session.close()


atexit.register(_close_all_sessions)


def _new_context(session: _BrowserSession, width: int, height: int):
    return session.browser.new_context(
        viewport={"width": max(1, int(width)), "height": max(1, int(height))},
        device_scale_factor=1,
    )


def _wait_for_fonts(page):
    page.evaluate("document.fonts ? document.fonts.ready : Promise.resolve()")


def _wait_for_network_idle(page):
    try:
        page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT_SECONDS * 1000)
    except Exception:
        # Some Wiki pages keep analytics connections open forever.
        pass


def _screenshot_error(action: str, error: Exception):
    logger.warning("%s失败: %s", action, error)


def screenshot_element(
    url: str,
    selector: str,
    output_dir: str,
    window_size: str = "1280,1600",
) -> str | None:
    """Navigate to ``url`` and save a CSS element screenshot as a PNG path."""
    try:
        width, height = (int(value) for value in window_size.split(",", 1))
        session = _get_session()
        context = _new_context(session, width, height)
        page = context.new_page()
        page.set_default_timeout(ELEMENT_TIMEOUT_SECONDS * 1000)
        page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_SECONDS * 1000)
        try:
            page.goto(url, wait_until="domcontentloaded")
            _wait_for_network_idle(page)
            _wait_for_fonts(page)
            locator = page.locator(selector).first
            locator.wait_for(state="visible")
            if not locator.bounding_box():
                logger.warning("页面元素没有可见尺寸 '%s': %s", selector, url)
                return None

            os.makedirs(output_dir, exist_ok=True)
            image_path = os.path.join(
                output_dir, f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:12]}.png"
            )
            locator.screenshot(path=image_path, type="png", animations="disabled")
            logger.info("元素截图成功: %s", image_path)
            return image_path
        finally:
            context.close()
    except Exception as error:
        _screenshot_error(f"元素截图 ({url})", error)
        return None


def screenshot_full_page(
    html_content: str,
    width: int = 1200,
    height: int = 800,
    max_height: int = 0,
) -> str | None:
    """Render HTML and return a OneBot-compatible ``base64://`` PNG string."""
    context = None
    try:
        session = _get_session()
        context = _new_context(session, width, height)
        page = context.new_page()
        page.set_default_timeout(PAGE_LOAD_TIMEOUT_SECONDS * 1000)
        page.set_content(html_content, wait_until="load")
        _wait_for_network_idle(page)
        _wait_for_fonts(page)

        actual_height = int(
            page.evaluate(
                """Math.max(
                    document.documentElement.scrollHeight || 0,
                    document.body ? document.body.scrollHeight : 0,
                    300
                )"""
            )
        )
        capture_height = min(actual_height, max_height) if max_height > 0 else actual_height
        if max_height > 0 and actual_height > max_height:
            logger.warning(
                "页面高度 %spx 超过上限 %spx，将裁剪到 %spx",
                actual_height,
                max_height,
                max_height,
            )
        page.set_viewport_size({"width": max(1, int(width)), "height": max(1, capture_height)})
        png = page.screenshot(
            type="png",
            full_page=max_height <= 0,
            animations="disabled",
        )
        logger.info("全页截图成功: %sx%s", width, capture_height)
        return "base64://" + base64.b64encode(png).decode("ascii")
    except Exception as error:
        _screenshot_error("全页截图", error)
        return None
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
