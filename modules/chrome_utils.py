"""共享的 headless Chrome/Edge 截图工具。

从 stardew.py、sve.py、report.py 中提取，统一维护。
支持两种截图模式：
  - URL 导航 + 元素截图（Wiki 信息框）
  - 本地 HTML 文件 + 全页截图（群分析报告）
"""

import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from urllib.request import urlopen

import websocket

from bot.config import section

logger = logging.getLogger("basic-bot.chrome_utils")

_browser_config = section("browser")
BROWSER_PATH = str(_browser_config["path"]).strip()
DEVTOOLS_TIMEOUT_SECONDS = float(_browser_config["devtools_timeout_seconds"])
PAGE_LOAD_TIMEOUT_SECONDS = float(_browser_config["page_load_timeout_seconds"])
ELEMENT_TIMEOUT_SECONDS = float(_browser_config["element_timeout_seconds"])
CDP_TIMEOUT_SECONDS = float(_browser_config["cdp_timeout_seconds"])

# ═══════════════════════════════════════════════════════════════════
# 浏览器发现（延迟解析，支持运行时重试）
# ═══════════════════════════════════════════════════════════════════

_BROWSER_PATH_CACHE: str | None = None
_BROWSER_PATH_TRIED: bool = False


def _find_browser_path() -> str | None:
    """扫描系统查找 Chrome/Edge/Chromium，返回第一个存在的路径。

    按操作系统分别搜索常见安装位置，同时支持 config.py 的 BROWSER['path'] 覆盖。
    """
    if BROWSER_PATH and os.path.exists(BROWSER_PATH):
        return BROWSER_PATH

    if os.name == "nt":
        # ── Windows ──
        candidates = [
            shutil.which("chrome"),
            shutil.which("chrome.exe"),
            shutil.which("msedge"),
            shutil.which("msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(
                r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.Chrome*\chrome.exe"
            ),
        ]
    else:
        # ── Linux / macOS ──
        candidates = [
            shutil.which("google-chrome-stable"),
            shutil.which("google-chrome"),
            shutil.which("chromium-browser"),
            shutil.which("chromium"),
            shutil.which("chrome"),
            shutil.which("microsoft-edge-stable"),
            shutil.which("microsoft-edge"),
            shutil.which("msedge"),
            # Snap 安装路径
            "/snap/bin/chromium",
            "/snap/bin/google-chrome-stable",
        ]

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def get_browser_path() -> str | None:
    """返回缓存的浏览器路径。

    首次调用时扫描系统；后续直接返回缓存结果。
    若之前未找到，可通过 reset_browser_path_cache() 强制重新扫描。
    """
    global _BROWSER_PATH_CACHE, _BROWSER_PATH_TRIED
    if not _BROWSER_PATH_TRIED:
        _BROWSER_PATH_TRIED = True
        _BROWSER_PATH_CACHE = _find_browser_path()
        if _BROWSER_PATH_CACHE:
            logger.info(f"找到浏览器: {_BROWSER_PATH_CACHE}")
        else:
            logger.warning(
                "未找到 Chrome/Edge，截图功能不可用。"
                "请安装浏览器或在 config.py 设置 BROWSER['path']。"
            )
    return _BROWSER_PATH_CACHE


def reset_browser_path_cache():
    """强制重新扫描浏览器路径（例如安装浏览器后调用）。"""
    global _BROWSER_PATH_CACHE, _BROWSER_PATH_TRIED
    _BROWSER_PATH_CACHE = None
    _BROWSER_PATH_TRIED = False


# ═══════════════════════════════════════════════════════════════════
# 网络工具
# ═══════════════════════════════════════════════════════════════════

def get_free_port() -> int:
    """获取一个空闲的 TCP 端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ═══════════════════════════════════════════════════════════════════
# CDP 通信
# ═══════════════════════════════════════════════════════════════════

def devtools_call(ws, method: str, params=None, msg_id=None):
    """通过 WebSocket 发送 CDP 命令并等待响应。"""
    if msg_id is None:
        msg_id = [0]
    msg_id[0] += 1
    ws.send(
        json.dumps({"id": msg_id[0], "method": method, "params": params or {}})
    )
    while True:
        data = json.loads(ws.recv())
        if data.get("id") == msg_id[0]:
            return data


def wait_for_devtools(port: int, timeout: float = DEVTOOLS_TIMEOUT_SECONDS) -> str | None:
    """轮询 http://127.0.0.1:<port>/json 直到获取到页面的 WebSocket URL。"""
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json"
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as resp:
                pages = json.loads(resp.read().decode("utf-8"))
                for page in pages:
                    if (
                        page.get("type") == "page"
                        and page.get("webSocketDebuggerUrl")
                    ):
                        return page["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.2)
    return None


# ═══════════════════════════════════════════════════════════════════
# 页面加载等待
# ═══════════════════════════════════════════════════════════════════

def _wait_for_page_load(ws, timeout: float = PAGE_LOAD_TIMEOUT_SECONDS) -> bool:
    """等待 Page.loadEventFired 或 Page.frameStoppedLoading 事件。

    替代 time.sleep(5) 的硬等待，在页面真的加载完成后立即返回。
    """
    deadline = time.time() + timeout
    old_timeout = ws.gettimeout()
    ws.settimeout(1.0)
    try:
        while time.time() < deadline:
            try:
                data = json.loads(ws.recv())
            except Exception:
                continue
            method = data.get("method", "")
            if method in ("Page.loadEventFired", "Page.frameStoppedLoading"):
                return True
        return False
    finally:
        ws.settimeout(old_timeout)


def _wait_for_element(ws, selector: str, timeout: float = ELEMENT_TIMEOUT_SECONDS) -> dict | None:
    """轮询等待 DOM 元素出现，返回其 bounding rect 或 None。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = devtools_call(
            ws,
            "Runtime.evaluate",
            {
                "expression": f"""
(() => {{
  const el = document.querySelector('{selector}');
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  return {{
    x: rect.x + window.scrollX, y: rect.y + window.scrollY,
    width: rect.width, height: rect.height, scale: 1
  }};
}})()
""",
                "returnByValue": True,
            },
        )
        value = result.get("result", {}).get("result", {}).get("value")
        if value and value.get("width") and value.get("height"):
            return value
        time.sleep(0.5)
    return None


# ═══════════════════════════════════════════════════════════════════
# 浏览器启动与清理
# ═══════════════════════════════════════════════════════════════════

def launch_browser(
    url: str,
    window_size: str = "1280,1600",
    timeout: float = 30,
) -> tuple[subprocess.Popen, int, str, str] | None:
    """启动 headless Chrome 并连接到 DevTools。

    Args:
        url: 要打开的 URL（支持 http/https/file://）
        window_size: 窗口尺寸 "WIDTH,HEIGHT"
        timeout: DevTools 连接超时（秒）

    Returns:
        (process, port, ws_url, user_data_dir) 或 None（启动失败）
    """
    browser_path = get_browser_path()
    if not browser_path:
        return None

    port = get_free_port()
    user_data_dir = tempfile.mkdtemp(prefix="chrome_bot_")

    cmd = [
        browser_path,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-sandbox",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data_dir}",
        f"--window-size={window_size}",
        url,
    ]

    popen_kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(cmd, **popen_kwargs)

    ws_url = wait_for_devtools(port, timeout=timeout)
    if not ws_url:
        # 收集 stderr 以便排查
        try:
            _, stderr = process.communicate(timeout=2)
            if stderr:
                logger.error(
                    f"Chrome stderr (port={port}): "
                    f"{stderr.decode('utf-8', errors='replace')[:500]}"
                )
        except Exception:
            pass
        _terminate_process(process)
        shutil.rmtree(user_data_dir, ignore_errors=True)
        logger.warning(f"DevTools 连接超时 (port={port})，请确认浏览器能正常启动")
        return None

    return process, port, ws_url, user_data_dir


def cleanup_browser(process: subprocess.Popen, user_data_dir: str):
    """终止浏览器进程并清理临时目录。"""
    _terminate_process(process)
    shutil.rmtree(user_data_dir, ignore_errors=True)


def _terminate_process(process: subprocess.Popen):
    """安全终止子进程。"""
    try:
        process.terminate()
    except Exception:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except Exception:
            pass
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# 高层截图函数
# ═══════════════════════════════════════════════════════════════════

def screenshot_element(
    url: str,
    selector: str,
    output_dir: str,
    window_size: str = "1280,1600",
) -> str | None:
    """导航到 URL，截取指定 CSS 选择器对应的元素。

    Wiki 信息框截图的通用实现。

    Args:
        url: 页面 URL
        selector: CSS 选择器（如 ".infoboxborder, .infoboxtable"）
        output_dir: 图片输出目录
        window_size: 浏览器窗口尺寸

    Returns:
        截图 PNG 文件的绝对路径，或 None
    """
    launched = launch_browser(url, window_size=window_size)
    if launched is None:
        return None

    process, port, ws_url, user_data_dir = launched
    os.makedirs(output_dir, exist_ok=True)

    ts = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:12]
    image_path = os.path.join(output_dir, f"{ts}_{uid}.png")

    try:
        ws = websocket.create_connection(ws_url, timeout=CDP_TIMEOUT_SECONDS)
        try:
            devtools_call(ws, "Page.enable")
            devtools_call(ws, "Runtime.enable")

            # 导航到目标 URL
            devtools_call(ws, "Page.navigate", {"url": url})

            # 等待页面加载完成（替代 time.sleep(5)）
            if not _wait_for_page_load(ws, timeout=PAGE_LOAD_TIMEOUT_SECONDS):
                logger.warning(f"页面加载超时: {url}")
                return None

            # 等待字体
            devtools_call(ws, "Runtime.evaluate", {
                "expression": "document.fonts && document.fonts.ready",
                "awaitPromise": True,
            })

            # 轮询等待目标元素出现
            clip = _wait_for_element(ws, selector, timeout=ELEMENT_TIMEOUT_SECONDS)
            if not clip:
                logger.warning(f"页面未找到元素 '{selector}': {url}")
                return None

            screenshot = devtools_call(ws, "Page.captureScreenshot", {
                "format": "png",
                "clip": clip,
                "captureBeyondViewport": True,
            })
            image_data = screenshot.get("result", {}).get("data")
            if not image_data:
                logger.warning(f"截图返回空数据: {url}")
                return None

            with open(image_path, "wb") as f:
                f.write(base64.b64decode(image_data))
            logger.info(f"元素截图成功: {image_path}")
            return image_path

        finally:
            ws.close()
    finally:
        cleanup_browser(process, user_data_dir)


# 截图最大高度（像素），超过此高度会被裁剪，防止图片过大导致 QQ 无法加载
# 设 0 表示不限制，按实际内容高度截图
def screenshot_full_page(
    html_content: str,
    width: int = 1200,
    height: int = 800,
    max_height: int = 0,
) -> str | None:
    """将 HTML 内容渲染为全页 PNG 图片。

    群分析报告截图的通用实现。

    Args:
        html_content: 完整的 HTML 文档字符串
        width: 页面宽度
        height: 初始高度会被忽略，实际以内容为准

    Returns:
        base64 图片数据 "base64://..." 或 None
    """
    initial_height = max(1, int(height))
    max_height = max(0, int(max_height))
    browser_path = get_browser_path()
    if not browser_path:
        logger.warning("截图失败：未找到浏览器")
        return None

    # 写入临时 HTML 文件
    tmp_dir = tempfile.mkdtemp(prefix="chrome_render_")
    html_path = os.path.join(tmp_dir, "page.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    file_url = f"file:///{html_path.replace(os.sep, '/')}"

    # 先用一个合理的初始视口打开页面
    INITIAL_HEIGHT = initial_height
    launched = launch_browser(file_url, window_size=f"{width},{INITIAL_HEIGHT}")
    if launched is None:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None

    process, port, ws_url, user_data_dir = launched

    try:
        ws = websocket.create_connection(ws_url, timeout=CDP_TIMEOUT_SECONDS)
        try:
            devtools_call(ws, "Page.enable")

            # 用 CDP 覆盖视口尺寸
            devtools_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": width,
                "height": INITIAL_HEIGHT,
                "deviceScaleFactor": 1,
                "mobile": False,
            })

            # 等待页面渲染和字体加载
            time.sleep(2)
            devtools_call(ws, "Runtime.evaluate", {
                "expression": "document.fonts && document.fonts.ready",
                "awaitPromise": True,
            })
            time.sleep(0.5)

            # 获取页面内容真实底部位置（不受 viewport 高度影响）
            get_bottom = devtools_call(ws, "Runtime.evaluate", {
                "expression": (
                    "Math.max("
                    "  Array.from(document.body.children).reduce((max, el) => {"
                    "    var r = el.getBoundingClientRect();"
                    "    return Math.max(max, r.bottom);"
                    "  }, 0),"
                    "  300"
                    ")"
                ),
                "returnByValue": True,
            })
            actual_height = int(
                get_bottom.get("result", {}).get("result", {}).get("value", 800)
                or 800
            )
            logger.info(f"页面内容底部: {actual_height}px")

            # 限制最大高度
            if max_height > 0 and actual_height > max_height:
                logger.warning(
                    f"页面高度 {actual_height}px 超过上限 {max_height}px，"
                    f"将裁剪到 {max_height}px"
                )
                actual_height = max_height

            # 把视口精确调到内容高度，确保不出现黑边
            devtools_call(ws, "Emulation.setDeviceMetricsOverride", {
                "width": width,
                "height": actual_height,
                "deviceScaleFactor": 1,
                "mobile": False,
            })
            time.sleep(0.3)

            # 视口 = 内容高度，直接截视口即可，无需 clip
            result = devtools_call(ws, "Page.captureScreenshot", {
                "format": "png",
                "captureBeyondViewport": False,
            })
            image_data = result.get("result", {}).get("data")
            if not image_data:
                logger.warning("全页截图失败：返回空数据")
                return None

            logger.info(f"全页截图成功: {width}x{actual_height}")
            return f"base64://{image_data}"

        finally:
            ws.close()
    finally:
        cleanup_browser(process, user_data_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# 为了兼容旧代码，导出 base64
import base64  # noqa: E402
