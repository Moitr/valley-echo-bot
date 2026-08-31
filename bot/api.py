"""OneBot API client over the connected forward WebSocket."""
import json
import threading
import time
import uuid

from logger import logger
from bot.config import section

_api_config = section("api")

# ── WS 连接引用（由 app.py 在连接/重连时更新） ──
_ws_app = None  # type: ignore
_ws_lock = threading.RLock()

# ── API 响应匹配（echo → threading.Event） ──
_pending: dict[str, dict] = {}
_pending_lock = threading.Lock()
MAX_PENDING = int(_api_config["max_pending"])

# ── 机器人自身信息 ──
_bot_user_id: str = ""
_bot_nickname: str = ""

# ── 已发送消息追踪（用于判断是否回复了 bot） ──
_sent_msg_ids: set[str] = set()
_sent_msg_lock = threading.Lock()
MAX_TRACKED_IDS = int(_api_config["max_tracked_messages"])
DEFAULT_TIMEOUT_SECONDS = float(_api_config["default_timeout_seconds"])
LONG_TIMEOUT_SECONDS = float(_api_config["long_timeout_seconds"])


# ═══════════════════════════════════════════════════════════════════════
# WS 连接管理
# ═══════════════════════════════════════════════════════════════════════

def set_ws(ws):
    """更新全局 WS 连接引用（连接/重连时调用）"""
    global _ws_app
    with _ws_lock:
        _ws_app = ws


def set_bot_identity(user_id, nickname: str | None = None):
    """Cache identity from OneBot events without requiring get_login_info."""
    global _bot_user_id, _bot_nickname
    if user_id is not None:
        _bot_user_id = str(user_id)
    if nickname:
        _bot_nickname = str(nickname)


def handle_api_response(data: dict):
    """收到 API 响应（带 echo 字段），唤醒对应的等待线程"""
    if not isinstance(data, dict):
        return
    raw_echo = data.get("echo", "")
    if raw_echo is None or raw_echo == "":
        return
    echo = str(raw_echo)
    with _pending_lock:
        entry = _pending.pop(echo, None)
    if entry:
        entry["result"]["value"] = data  # 写入共享容器，避免二次 pop 丢数据
        entry["event"].set()
    else:
        logger.warning(
            f"[API] 收到未匹配的响应: echo={echo[:12]}..., "
            f"status={data.get('status')} retcode={data.get('retcode')}"
        )


def handle_auth_failure(data: dict):
    """Handle llbot's token failure response, which may omit echo."""
    with _pending_lock:
        if not _pending:
            return
        echo, entry = min(
            _pending.items(), key=lambda item: item[1].get("ts", 0)
        )
        _pending.pop(echo, None)
    entry["result"]["value"] = data
    entry["event"].set()
    logger.error(
        f"[API] llbot Token 鉴权失败: retcode={data.get('retcode')} "
        f"message={data.get('message') or data.get('wording')}"
    )


def fail_pending_requests(data: dict):
    """Wake all API waiters when the WebSocket closes."""
    with _pending_lock:
        entries = list(_pending.values())
        _pending.clear()
    for entry in entries:
        entry["result"]["value"] = data
        entry["event"].set()


# ═══════════════════════════════════════════════════════════════════════
# 底层 WS API 调用
# ═══════════════════════════════════════════════════════════════════════

def _call_api(
    action: str,
    params: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict | None:
    """通过已连接的正向 WebSocket 调用 API，同步等待同 echo 响应。"""
    with _ws_lock:
        ws = _ws_app
    if not ws:
        logger.error(f"[API] WS 未连接，无法调用 {action}")
        return None

    echo = str(uuid.uuid4())
    event = threading.Event()
    result_holder: dict = {}  # 共享容器，handle_api_response 写入结果

    with _pending_lock:
        if len(_pending) >= MAX_PENDING:
            oldest = min(_pending.keys(), key=lambda k: _pending[k].get("ts", 0))
            _pending.pop(oldest, None)
        _pending[echo] = {"event": event, "result": result_holder, "ts": time.time()}

    try:
        payload = {"action": action, "params": params or {}, "echo": echo}
        logger.info(f"[API] 发送请求: action={action} echo={echo[:12]}...")
        ws.send(json.dumps(payload, ensure_ascii=False))
    except Exception as err:
        logger.error(f"[API] 发送 {action} 失败: {err}")
        with _pending_lock:
            _pending.pop(echo, None)
        return None

    if not event.wait(timeout):
        with _pending_lock:
            pending_count = len(_pending)
        logger.warning(
            f"[API] {action} 超时 ({timeout}s)，未收到 echo={echo[:12]}... 响应，"
            f"pending={pending_count}；请确认 Token 和 OneBot 正向 WS 配置"
        )
        with _pending_lock:
            _pending.pop(echo, None)
        return None

    # handle_api_response 已经把 _pending[echo] pop 掉了并写入了 result_holder
    return result_holder.get("value")


# ═══════════════════════════════════════════════════════════════════════
# 消息构造器
# ═══════════════════════════════════════════════════════════════════════

def text(content: str) -> dict:
    return {"type": "text", "data": {"text": content}}


def at(qq) -> dict:
    return {"type": "at", "data": {"qq": str(qq)}}


def reply(message_id) -> dict:
    return {"type": "reply", "data": {"id": str(message_id)}}


def image(file) -> dict:
    return {"type": "image", "data": {"file": file}}


def face(face_id) -> dict:
    return {"type": "face", "data": {"id": str(face_id)}}


def fmt_msg(message: list) -> str:
    return " ".join(
        segment["data"].get("text", "")
        if segment.get("type") == "text"
        else "[图片]"
        if segment.get("type") == "image"
        else f"[{segment.get('type')}]"
        for segment in message
    )


# ═══════════════════════════════════════════════════════════════════════
# 已发送消息追踪
# ═══════════════════════════════════════════════════════════════════════

def _track_sent_msg(message_id):
    """记录 bot 发出的消息 ID，用于判断是否有人回复 bot"""
    with _sent_msg_lock:
        _sent_msg_ids.add(str(message_id))
        while len(_sent_msg_ids) > MAX_TRACKED_IDS:
            _sent_msg_ids.pop()


def is_sent_by_bot(message_id) -> bool:
    """判断某个消息 ID 是否是 bot 发出的"""
    with _sent_msg_lock:
        return str(message_id) in _sent_msg_ids


# ═══════════════════════════════════════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════════════════════════════════════

def get_bot_user_id() -> str:
    return _bot_user_id


def get_bot_nickname() -> str:
    return _bot_nickname


def send_group_msg(group_id, message: list) -> dict | None:
    """发送群聊消息"""
    result = _call_api("send_group_msg", {"group_id": group_id, "message": message})
    if result and result.get("status") == "ok":
        logger.info(f"[群 {group_id}] 发送消息 成功: {fmt_msg(message)}")
        msg_id = result.get("data", {}).get("message_id")
        if msg_id:
            _track_sent_msg(msg_id)
        return result.get("data")
    logger.info(f"[群 {group_id}] 发送消息 失败")
    return None


def send_group_json_card(group_id, card_data) -> dict | None:
    """发送群聊 JSON 卡片消息"""
    if isinstance(card_data, dict):
        card_data = json.dumps(card_data, ensure_ascii=False)

    message = [{"type": "json", "data": {"data": card_data}}]
    result = _call_api("send_group_msg", {"group_id": group_id, "message": message})
    if result and result.get("status") == "ok":
        logger.info(f"[群 {group_id}] 发送卡片消息 成功")
        return result.get("data")
    logger.info(f"[群 {group_id}] 发送卡片消息 失败")
    return None


def set_group_add_request(flag, approve=True, reason="") -> dict | None:
    """处理加群请求"""
    result = _call_api("set_group_add_request", {
        "flag": flag, "sub_type": "add", "approve": approve, "reason": reason,
    })
    if result and result.get("status") == "ok":
        logger.info(f"处理加群请求 成功: flag={flag}, approve={approve}")
        return result  # data 可能为 null，返回整个 result 确保 truthy
    logger.info(f"处理加群请求 失败")
    return None


def send_private_msg(user_id, message: list) -> dict | None:
    """发送私聊消息"""
    result = _call_api("send_private_msg", {"user_id": user_id, "message": message})
    if result and result.get("status") == "ok":
        logger.info(f"[私聊 {user_id}] 发送消息 成功: {fmt_msg(message)}")
        return result.get("data")
    logger.info(f"[私聊 {user_id}] 发送消息 失败")
    return None


def send_poke(group_id: int, user_id: int) -> dict | None:
    """在指定群内向成员发送戳一戳。"""
    result = _call_api("send_poke", {"group_id": group_id, "user_id": user_id})
    if result and result.get("status") == "ok":
        logger.info(f"[群 {group_id}] 戳一戳发送成功: user={user_id}")
        return result.get("data")
    logger.warning(f"[群 {group_id}] 戳一戳发送失败: user={user_id}, 响应={result}")
    return None


def upload_group_file(group_id, file_path, filename=None) -> dict | None:
    """上传文件到群文件"""
    import os as _os
    name = filename or _os.path.basename(file_path)
    result = _call_api("upload_group_file", {
        "group_id": group_id, "file": file_path, "name": name,
    }, timeout=LONG_TIMEOUT_SECONDS)
    if result and result.get("status") == "ok":
        logger.info(f"[群 {group_id}] 上传文件 成功: {name}")
        return result.get("data")
    logger.info(f"[群 {group_id}] 上传文件 失败")
    return None


def set_group_special_title(group_id, user_id, special_title) -> dict | None:
    """设置群头衔，special_title 为空字符串时去掉头衔"""
    result = _call_api("set_group_special_title", {
        "group_id": group_id,
        "user_id": user_id,
        "special_title": special_title,
    })
    if result and result.get("status") == "ok":
        logger.info(f"[群 {group_id}] 设置头衔成功: user={user_id}, title={special_title!r}")
        return result.get("data")
    logger.error(
        f"[群 {group_id}] 设置头衔失败: user={user_id}, title={special_title!r}, 响应={result}"
    )
    return None


def get_login_info() -> dict | None:
    """获取机器人自身登录信息，并缓存 user_id / nickname。"""
    global _bot_user_id, _bot_nickname
    result = _call_api("get_login_info", {})
    if result and result.get("status") == "ok":
        info = result.get("data", {})
        _bot_user_id = str(info.get("user_id", ""))
        _bot_nickname = str(info.get("nickname", ""))
        logger.info(f"[API] 登录信息已加载: user_id={_bot_user_id} nickname={_bot_nickname}")
        return info
    logger.warning(f"[API] 获取登录信息失败: {result}")
    return None


def get_group_member_info(group_id: int, user_id: int) -> dict | None:
    """Get group member information, including nickname/card."""
    result = _call_api("get_group_member_info", {
        "group_id": group_id,
        "user_id": user_id,
    })
    if result and result.get("status") == "ok":
        return result.get("data", {})
    logger.warning(f"[群 {group_id}] 获取成员信息失败: user_id={user_id}, response={result}")
    return None


def get_group_msg_history(
    group_id: int,
    message_seq: int | None = None,
    count: int = 20,
    reverse_order: bool = False,
) -> list[dict]:
    """获取群聊历史消息"""
    body: dict = {"group_id": group_id, "count": count, "reverseOrder": reverse_order}
    if message_seq is not None:
        body["message_seq"] = message_seq

    result = _call_api("get_group_msg_history", body, timeout=LONG_TIMEOUT_SECONDS)
    if result and result.get("status") == "ok":
        return result.get("data", {}).get("messages", [])
    logger.warning(f"[群 {group_id}] 获取历史消息失败: {result}")
    return []
