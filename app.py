"""valley-echo-bot — 正向 WebSocket 客户端，连接 llbot 收发事件与 API 调用"""
import json
import logging
import os
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from websocket import WebSocketApp

from onebot.transport import get_login_info, handle_api_response, set_bot_identity, set_ws
from config import CONFIG_PATH, DEEPSEEK_KEY, section
from onebot.event_router import dispatch_group_event

logging.getLogger("websocket").setLevel(logging.ERROR)

_websocket_config = section("websocket")
WS_URL = str(_websocket_config["url"]).strip()
ACCESS_TOKEN = str(_websocket_config["access_token"]).strip()
LOG_LEVEL = str(_websocket_config["log_level"])
RECONNECT_SECONDS = float(_websocket_config["reconnect_seconds"])
PING_INTERVAL_SECONDS = float(_websocket_config["ping_interval_seconds"])
PING_TIMEOUT_SECONDS = float(_websocket_config["ping_timeout_seconds"])
AUTORELOAD_ENABLED = (
    bool(_websocket_config["autoreload_enabled"])
    and LOG_LEVEL.upper() == "DEBUG"
)
AUTORELOAD_POLL_SECONDS = float(_websocket_config["autoreload_poll_seconds"])
logging.getLogger("valley-echo-bot").setLevel(
    getattr(logging, LOG_LEVEL.upper(), logging.INFO)
)

_watch_root = os.path.dirname(os.path.abspath(__file__))
_event_executor = ThreadPoolExecutor(
    max_workers=int(_websocket_config["event_workers"]),
    thread_name_prefix="group-event",
)
_shutdown_event = threading.Event()
_active_ws = None
_active_ws_lock = threading.RLock()


def _request_shutdown(signum=None, _frame=None):
    """Stop reconnecting and wake the WebSocket loop on Ctrl+C/SIGTERM."""
    if _shutdown_event.is_set():
        return
    _shutdown_event.set()
    with _active_ws_lock:
        ws = _active_ws
    if ws is not None:
        # websocket-client 的 run_forever 可能在 close 后仍继续循环，先关闭运行标志。
        try:
            ws.keep_running = False
        except Exception:
            pass

        def _close_ws():
            try:
                ws.close()
            except Exception:
                pass

        # 不在信号处理器中直接执行可能阻塞的 WebSocket 清理。
        threading.Thread(target=_close_ws, daemon=True, name="shutdown-ws").start()
    # 让主线程立即跳出 websocket-client 的阻塞调用，进入统一清理流程。
    if signum == signal.SIGINT:
        raise KeyboardInterrupt


def _shutdown_runtime():
    """Release runtime resources after the main reconnect loop exits."""
    global _active_ws
    with _active_ws_lock:
        _active_ws = None
    try:
        _event_executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    try:
        from modules.infrastructure.browser import reset_browser_path_cache
        reset_browser_path_cache()
    except Exception:
        logging.getLogger("valley-echo-bot").exception("[退出] 关闭浏览器失败")


def _authorization_header(token: str) -> list[str]:
    """Build one Authorization header without duplicating an existing Bearer prefix."""
    if not token:
        return []
    value = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    # websocket-client 使用官方支持的 header 列表格式。
    return [f"Authorization: {value}"]


def _start_autoreload():
    """监控 .py 文件变化，检测到改动时自动重启进程"""
    mtimes: dict[str, float] = {}

    def _collect_py_files():
        for root, dirs, files in os.walk(_watch_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in files:
                # logger.py 可能被部署工具或日志收集器触碰，不能触发重启循环。
                if f.endswith(".py") and f != "logger.py":
                    path = os.path.join(root, f)
                    if path not in mtimes:
                        try:
                            mtimes[path] = os.path.getmtime(path)
                        except OSError:
                            pass

    _collect_py_files()
    logger = logging.getLogger("valley-echo-bot")
    logger.info("[重载] 文件监控已启动，修改 .py 文件自动重启")

    while not _shutdown_event.is_set():
        if _shutdown_event.wait(AUTORELOAD_POLL_SECONDS):
            break
        try:
            for path, old_mtime in list(mtimes.items()):
                try:
                    new_mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if new_mtime > old_mtime:
                    logger.info(f"[重载] 检测到文件变化: {os.path.relpath(path, _watch_root)}")
                    # 子进程启动新实例，当前进程走正常退出流程。
                    import subprocess
                    subprocess.Popen([sys.executable] + sys.argv)
                    _request_shutdown()
                    return
            _collect_py_files()  # 定期重新扫描，发现新文件
        except Exception:
            pass


def _load_bot_identity():
    """Load login information outside the WebSocket callback thread.

    websocket-client invokes ``on_open`` and ``on_message`` on its receive
    thread. Waiting for an API response inside ``on_open`` therefore prevents
    that same thread from receiving the response. Keep this request in a
    separate thread so the echo response can always be dispatched promptly.
    """
    get_login_info()


def on_open(ws):
    """WS 连接成功后异步获取机器人登录信息。"""
    set_ws(ws)
    logging.getLogger("valley-echo-bot").info(f"[WS] 已连接到 llbot ({WS_URL})")
    threading.Thread(
        target=_load_bot_identity,
        daemon=True,
        name="login-info",
    ).start()


def on_message(_ws, raw):
    """收到 WS 消息，分发：API 响应 或 事件上报"""
    logging.getLogger("valley-echo-bot").debug("[WS] 收到原始 JSON: %s", raw)
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        logging.getLogger("valley-echo-bot").error(f"[WS] 无法解析消息: {raw[:200]}")
        return

    # API 响应（有 echo 字段）— 立即处理，不阻塞
    if not isinstance(data, dict):
        logging.getLogger("valley-echo-bot").warning("[WS] 忽略非对象消息")
        return

    self_id = data.get("self_id")
    if self_id is not None:
        set_bot_identity(self_id)

    if "echo" in data and data.get("echo"):
        handle_api_response(data)
        return

    if data.get("status") == "failed" and data.get("retcode") == 1403:
        from onebot.transport import handle_auth_failure
        handle_auth_failure(data)

    if data.get("post_type") == "meta_event" and data.get("meta_event_type") == "heartbeat":
        logging.getLogger("valley-echo-bot").info(
            f"[WS] 心跳已接收: self_id={self_id} status={data.get('status')}"
        )
        return

    if "status" in data or "retcode" in data:
        logging.getLogger("valley-echo-bot").warning(
            "[WS] 收到未匹配的服务端消息: "
            f"post_type={data.get('post_type')!r} "
            f"meta_event_type={data.get('meta_event_type')!r} "
            f"sub_type={data.get('sub_type')!r} "
            f"status={data.get('status')} retcode={data.get('retcode')} "
            f"echo={data.get('echo')!r} keys={sorted(data.keys())}"
        )

    # 事件上报 — 在单独线程中处理，避免 handler 内调用 API 时阻塞 WS 接收
    _event_executor.submit(_dispatch_event_safe, data)


def _dispatch_event_safe(data):
    try:
        dispatch_group_event(data)
    except Exception:
        logging.getLogger("valley-echo-bot").exception("[事件] 处理群事件时发生未捕获异常")


def on_error(_ws, err):
    if _shutdown_event.is_set():
        return
    logging.getLogger("valley-echo-bot").error(f"[WS] 连接错误: {err}")


def on_close(_ws, code, msg):
    set_ws(None)
    from onebot.transport import fail_pending_requests
    fail_pending_requests({
        "status": "failed",
        "retcode": 1000,
        "message": "WebSocket connection closed",
    })
    if not _shutdown_event.is_set():
        reason = msg or "服务器未提供关闭原因"
        logging.getLogger("valley-echo-bot").warning(
            f"[WS] 连接关闭: code={code} msg={reason}；请检查 WS 地址、Authorization Token 和 llbot 正向 WS 配置"
        )


def run():
    global _active_ws
    logger = logging.getLogger("valley-echo-bot")
    logger.info(f"[配置] 当前配置文件: {CONFIG_PATH}")
    logger.info(f"[配置] WebSocket Token: {'已设置' if ACCESS_TOKEN else '未设置'}（长度={len(ACCESS_TOKEN)}）")
    if not ACCESS_TOKEN:
        logger.warning(
            "[配置] WEBSOCKET['access_token'] 为空，将不发送 Authorization 请求头；"
            f"请编辑 {CONFIG_PATH}"
        )
    if not DEEPSEEK_KEY:
        logger.warning(
            "[配置] AI['api_key'] 为空，AI 功能将不可用；"
            f"请编辑 {CONFIG_PATH}"
        )
    # 先注册信号，再启动 WebSocket/自动重载线程，确保 Ctrl+C 始终由主进程接管。
    signal.signal(signal.SIGINT, _request_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_shutdown)
    if AUTORELOAD_ENABLED:
        threading.Thread(target=_start_autoreload, daemon=True, name="autoreload").start()
    else:
        logger.info("[重载] 已关闭源码自动重载（仅 DEBUG 级别启用）")

    try:
        while not _shutdown_event.is_set():
            ws = None
            try:
                ws = WebSocketApp(
                    WS_URL,
                    header=_authorization_header(ACCESS_TOKEN),
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                )
                set_ws(ws)
                with _active_ws_lock:
                    _active_ws = ws
                run_options = {}
                if PING_INTERVAL_SECONDS > 0:
                    run_options = {
                        "ping_interval": PING_INTERVAL_SECONDS,
                        "ping_timeout": PING_TIMEOUT_SECONDS,
                    }
                ws.run_forever(**run_options)
            except KeyboardInterrupt:
                _request_shutdown()
            except Exception as e:
                logger.error(f"[WS] 异常: {e}")
            finally:
                with _active_ws_lock:
                    if _active_ws is ws:
                        _active_ws = None
                set_ws(None)
            if not _shutdown_event.is_set():
                logger.info(f"[WS] {RECONNECT_SECONDS:g} 秒后重连…")
                _shutdown_event.wait(RECONNECT_SECONDS)
    finally:
        _request_shutdown()
        _shutdown_runtime()
        logger.info("[退出] valley-echo-bot 已停止")


if __name__ == "__main__":
    run()
