"""消息处理：入群欢迎、命令分发、Wiki 查询、AI 对话、群分析"""

import base64
import io
import os
import random
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime

from PIL import Image

from onebot.ai_handler import handle_ai_chat_command, handle_proactive
from config import PROJECT_ROOT, section
from onebot.transport import (
    at,
    get_bot_nickname,
    get_bot_user_id,
    get_group_member_info,
    image,
    node,
    reply,
    send_group_json_card,
    send_group_forward_msg,
    send_group_msg,
    send_poke,
    set_group_add_request,
    set_group_special_title,
    text,
)
from config import (
    AI_CHAT_GROUPS,
    LEAVE_GROUPS,
    POKE_GROUPS,
    TITLE_GROUPS,
    WELCOME_GROUPS,
    WIKI_GROUPS,
)
from logger import logger
from modules.knowledge.stardew_valley.wiki.sve import (
    WikiRequestError as SveWikiRequestError,
    get_direct_page_summary_data as sve_get_direct_page_summary_data,
    get_page_summary_data as sve_get_page_summary_data,
    get_search_results as sve_get_search_results,
    save_infobox_screenshot as sve_save_infobox_screenshot,
    SCREENSHOT_DIR as SVE_SCREENSHOT_DIR,
)
from modules.knowledge.stardew_valley.wiki.vanilla import (
    WikiRequestError,
    get_direct_page_summary_data,
    get_page_summary_data,
    get_search_results,
    save_infobox_screenshot,
    SCREENSHOT_DIR as STARDEW_SCREENSHOT_DIR,
)
from modules.knowledge.stardew_valley.wiki.summarize import summarize_wiki_page

# ═══════════════════════════════════════════════════════════════════════
# 欢迎消息
# ═══════════════════════════════════════════════════════════════════════

_welcome_config = section("welcome")
_wiki_config = section("wiki")
_poke_config = section("poke")
WELCOME_IMAGE = str(PROJECT_ROOT / str(_welcome_config["image_path"]))
MAX_SIZE = int(_welcome_config["max_image_size"])
SELECTION_TIMEOUT_SECONDS = float(_wiki_config["selection_timeout_seconds"])
POKE_REPLIES = tuple(
    item.strip()
    for item in _poke_config["reply_messages"]
    if isinstance(item, str) and item.strip()
)
POKE_BACK = bool(_poke_config["poke_back"])
if not POKE_REPLIES:
    raise ValueError("poke.reply_messages must contain at least one non-empty message")

_ai_config = section("ai")
_RECENT_CONTEXT_MESSAGES = max(1, int(_ai_config.get("proactive_context_messages", 6)))
_RECENT_CONTEXT_MAX_CHARACTERS = max(
    200, int(_ai_config.get("proactive_context_max_characters", 1200))
)
_recent_group_messages: defaultdict[str, deque[str]] = defaultdict(
    lambda: deque(maxlen=_RECENT_CONTEXT_MESSAGES)
)
_recent_group_messages_lock = threading.RLock()


def load_welcome_image():
    """加载欢迎图片并缩放到合适大小，返回 base64 字符串"""
    if not os.path.exists(WELCOME_IMAGE):
        logger.info(f"欢迎图片不存在: {WELCOME_IMAGE}")
        return None

    img = Image.open(WELCOME_IMAGE)
    w, h = img.size

    if max(w, h) > MAX_SIZE:
        ratio = MAX_SIZE / max(w, h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "base64://" + base64.b64encode(buf.getvalue()).decode("ascii")


def send_welcome_message(group_id, user_id):
    """发送入群欢迎消息（图片 + @ + 文字）"""
    logger.info(f"[群 {group_id}] 发送欢迎消息给用户 {user_id}")
    message = [at(user_id), text(" 欢迎加入！")]
    welcome_image = load_welcome_image()
    if welcome_image:
        message.append(image(welcome_image))
    result = send_group_msg(group_id, message)
    logger.info(f"[群 {group_id}] 欢迎消息发送结果: {result}")
    return result


# ═══════════════════════════════════════════════════════════════════════
# 消息解析辅助
# ═══════════════════════════════════════════════════════════════════════

def has_at(message, qq):
    return any(
        segment.get("type") == "at" and str(segment.get("data", {}).get("qq")) == str(qq)
        for segment in message or []
    )


def has_at_other(message, qq):
    return any(
        segment.get("type") == "at" and str(segment.get("data", {}).get("qq")) != str(qq)
        for segment in message or []
    )


def has_reply(message):
    """检查消息是否包含引用回复"""
    return any(
        segment.get("type") == "reply"
        for segment in message or []
    )


def _get_reply_target_id(message):
    """获取回复目标的消息 ID，没有回复则返回空字符串"""
    for segment in message or []:
        if segment.get("type") == "reply":
            return str(segment.get("data", {}).get("id", ""))
    return ""


def has_reply_to_bot(message):
    """检查消息是否回复了机器人发出的消息"""
    target_id = _get_reply_target_id(message)
    if not target_id:
        return False
    from onebot.transport import is_sent_by_bot
    return is_sent_by_bot(target_id)


def _msg_text(message):
    """从 OneBot message 数组提取纯文本"""
    return " ".join(
        segment.get("data", {}).get("text", "")
        for segment in message or []
        if segment.get("type") == "text"
    )


def _msg_log_text(message):
    """生成安全的日志摘要，不输出图片 URL、文件名或 Base64 内容。"""
    parts = []
    for segment in message or []:
        if not isinstance(segment, dict):
            continue
        segment_type = segment.get("type")
        if segment_type == "text":
            value = segment.get("data", {}).get("text", "")
            if value:
                parts.append(str(value))
        elif segment_type == "image":
            parts.append("[图片]")
    return " ".join(parts)


def _recent_group_context(group_id) -> str:
    """Return recent in-memory group messages for natural proactive replies."""
    with _recent_group_messages_lock:
        messages = list(_recent_group_messages.get(str(group_id), ()))
    if not messages:
        return ""
    context = "\n".join(messages)
    return context[-_RECENT_CONTEXT_MAX_CHARACTERS:]


def _record_recent_group_message(group_id, user_id, message):
    """Keep a short, non-persistent, privacy-safe context window per group."""
    summary = _msg_log_text(message).strip()
    if not summary:
        return
    with _recent_group_messages_lock:
        _recent_group_messages[str(group_id)].append(f"用户{user_id}：{summary}")


def _image_urls(message):
    """提取 OneBot 图片段可供视觉模型读取的 URL。"""
    urls = []
    for segment in message or []:
        if not isinstance(segment, dict) or segment.get("type") != "image":
            continue
        data = segment.get("data") or {}
        if not isinstance(data, dict):
            continue
        # llbot/OneBot 通常提供 url，必要时也接受 Data URL。
        candidate = data.get("url") or data.get("file")
        if not isinstance(candidate, str):
            continue
        candidate = candidate.strip()
        if candidate.startswith("base64://"):
            payload = candidate.removeprefix("base64://").strip()
            if payload:
                candidate = f"data:image/jpeg;base64,{payload}"
        if not (
            candidate.startswith("http://")
            or candidate.startswith("https://")
            or candidate.startswith("data:image/")
        ):
            continue
        if candidate not in urls:
            urls.append(candidate)
    return urls


# ═══════════════════════════════════════════════════════════════════════
# 事件处理：入群 + 加群审批
# ═══════════════════════════════════════════════════════════════════════

def _handle_notice(body):
    """入群欢迎"""
    user_id = body.get("user_id")
    self_id = body.get("self_id")
    group_id = body["group_id"]

    if user_id == self_id:
        logger.info(f"[群 {group_id}] 机器人自己入群，跳过欢迎")
        return None

    sub_type = body.get("sub_type")
    if sub_type == "approve":
        logger.info(f"[群 {group_id}] sub_type=approve，已在 _handle_request 中发送欢迎，跳过")
        return None

    logger.info(f"[群 {group_id}] 新成员加入: {user_id} (sub_type={sub_type})")
    send_welcome_message(group_id, user_id)
    return None


def _handle_request(body):
    """加群审批"""
    user_id = body.get("user_id")
    flag = body.get("flag")
    comment = body.get("comment", "")
    group_id = body["group_id"]

    logger.info(
        f"[群 {group_id}] 收到入群申请: 用户={user_id}, "
        f"验证信息={comment}, flag={flag}"
    )
    result = set_group_add_request(flag, approve=True)
    logger.info(f"[群 {group_id}] 入群申请处理结果: {result}")

    if result:
        logger.info(f"[群 {group_id}] 申请已同意，发送欢迎消息给 {user_id}")
        send_welcome_message(group_id, user_id)
    return None


def _get_member_display_name(group_id, user_id):
    """Return a member's nickname, falling back to their ID when unavailable."""
    user_id = str(user_id)
    if not user_id or user_id == "0":
        return user_id
    try:
        info = get_group_member_info(group_id, int(user_id))
    except (TypeError, ValueError):
        return user_id
    if info:
        return str(info.get("nickname") or info.get("card") or user_id)
    return user_id


def _handle_decrease(body):
    """Announce a member leaving or being kicked from the group."""
    sub_type = body.get("sub_type")
    if sub_type == "kick_me":
        return None

    group_id = body["group_id"]
    user_id = body.get("user_id")
    user_name = _get_member_display_name(group_id, user_id)
    if sub_type == "leave":
        message = f"老乡{user_name}（{user_id}）离开了鹈鹕镇"
    elif sub_type == "kick":
        operator_id = body.get("operator_id")
        operator_name = _get_member_display_name(group_id, operator_id)
        message = f"老乡{user_name}（{user_id}）被{operator_name}（{operator_id}）请离了鹈鹕镇"
    else:
        logger.info(f"[群 {group_id}] 忽略未知群成员减少事件: sub_type={sub_type}")
        return None

    logger.info(f"[群 {group_id}] {message}")
    send_group_msg(group_id, [text(message)])
    return None


def _handle_poke(body):
    """Reply when a group member pokes this bot, then optionally poke back."""
    group_id = body.get("group_id")
    user_id = body.get("user_id")
    self_id = body.get("self_id")
    target_id = body.get("target_id")

    if not group_id or not user_id:
        logger.warning(f"[戳一戳] 忽略字段不完整的事件: {body}")
        return None
    if str(target_id) != str(self_id) or str(user_id) == str(self_id):
        logger.debug(
            f"[群 {group_id}] 忽略非机器人的戳一戳: user={user_id}, target={target_id}"
        )
        return None

    reply_text = random.choice(POKE_REPLIES)
    logger.info(f"[群 {group_id}] 收到戳一戳: user={user_id}")
    # 单独的文本段以空格开头，避免 QQ 中 @昵称 和正文粘在一起。
    send_group_msg(group_id, [at(user_id), text(" " + reply_text)])
    if POKE_BACK:
        send_poke(group_id, user_id)
    return None


_event_handlers = [
    {
        "match": {"post_type": "notice", "notice_type": "group_increase"},
        "handler": _handle_notice,
        "groups": WELCOME_GROUPS,
    },
    {
        "match": {"post_type": "request", "request_type": "group", "sub_type": "add"},
        "handler": _handle_request,
        "groups": WELCOME_GROUPS,
    },
    {
        "match": {"post_type": "notice", "notice_type": "group_decrease"},
        "handler": _handle_decrease,
        "groups": LEAVE_GROUPS,
    },
    {
        "match": {"post_type": "notice", "notice_type": "notify", "sub_type": "poke"},
        "handler": _handle_poke,
        "groups": POKE_GROUPS,
    },
]


def _dispatch_event(body):
    """遍历事件注册表，匹配则执行"""
    for evt in _event_handlers:
        match = evt["match"]
        if not all(body.get(k) == v for k, v in match.items()):
            continue
        groups = evt["groups"]
        if groups is not None and body.get("group_id") not in groups:
            continue
        return evt["handler"](body)
    return None


# ═══════════════════════════════════════════════════════════════════════
# Wiki 查询
# ═══════════════════════════════════════════════════════════════════════

PENDING_SEARCHES = {}
SVE_PENDING_SEARCHES = {}
_pending_lock = threading.RLock()


def _wiki_summary_parts(summary: str, fallback_title: str = "", structured=True):
    """Split a Wiki summary into title, description, fields and link text."""
    lines = [
        re.sub(r"\[\s*\d+\s*\]", "", line).strip()
        for line in str(summary or "").splitlines()
    ]
    while lines and not lines[0]:
        lines.pop(0)

    link_index = next(
        (index for index, line in enumerate(lines) if line.startswith("Wiki链接：")),
        len(lines),
    )
    body = lines[:link_index]
    link = lines[link_index] if link_index < len(lines) else ""

    if not structured:
        return (
            str(fallback_title or "Wiki查询"),
            "\n".join(body).strip() or "暂无简介",
            "暂无条目",
            link or "Wiki链接：暂无",
        )

    title = body[0] if body else str(fallback_title or "Wiki查询")
    rest = body[1:] if body else []
    try:
        separator = rest.index("")
    except ValueError:
        separator = len(rest)

    description_lines = [line for line in rest[:separator] if line]
    field_lines = [line for line in rest[separator + 1:] if line]
    return (
        title or str(fallback_title or "Wiki查询"),
        "\n".join(description_lines) or "暂无简介",
        "\n".join(field_lines) or "暂无条目",
        link or "Wiki链接：暂无",
    )


def _wiki_forward_nodes(
    summary,
    fallback_title="",
    structured=True,
):
    title, description, fields, link = _wiki_summary_parts(
        summary, fallback_title, structured=structured
    )
    node_kwargs = {}
    bot_id = get_bot_user_id()
    bot_name = get_bot_nickname()
    if bot_id:
        node_kwargs["uin"] = bot_id
    if bot_name:
        node_kwargs["name"] = bot_name
    return [
        node(title, **node_kwargs),
        node(description, **node_kwargs),
        node(fields, **node_kwargs),
        node(link, **node_kwargs),
    ]


def _wiki_cached_image(item_name, cache_dir):
    cache_path = _wiki_cache_path(item_name, cache_dir)
    return cache_path if cache_path and wait_image_ready(cache_path) else None


def image_base64(image_path):
    with open(image_path, "rb") as file:
        return "base64://" + base64.b64encode(file.read()).decode("ascii")


def wait_image_ready(image_path):
    last_size = -1
    for _ in range(10):
        if os.path.exists(image_path):
            current_size = os.path.getsize(image_path)
            if current_size > 0 and current_size == last_size:
                return True
            last_size = current_size
        time.sleep(0.2)
    return os.path.exists(image_path) and os.path.getsize(image_path) > 0


def send_image_with_retry(group_id, image_path, retries=3):
    if not wait_image_ready(image_path):
        logger.info(f"[群 {group_id}] Wiki 图片文件未准备好: {image_path}")
        return
    image_data = image_base64(image_path)
    for attempt in range(1, retries + 1):
        result = send_group_msg(group_id, [image(image_data)])
        if result:
            return
        logger.info(f"[群 {group_id}] Wiki 图片发送失败，重试 {attempt}/{retries}")
        time.sleep(1)


_WIKI_IMAGE_CACHE_LOCK = threading.RLock()


def _wiki_cache_path(item_name, cache_dir):
    """按物品名称生成稳定缓存路径，不把 URL 或用户信息写入文件名。"""
    name = str(item_name or "").strip()
    name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", name).strip("._-")
    if not name:
        return None
    return os.path.join(cache_dir, f"{name}.png")


def _save_cached_wiki_image(item_name, html, url, save_func, cache_dir, label):
    """Return an existing item image or render it once and store by item name."""
    cache_path = _wiki_cache_path(item_name, cache_dir)
    if not cache_path:
        return save_func(html, url)

    with _WIKI_IMAGE_CACHE_LOCK:
        if wait_image_ready(cache_path):
            logger.info("%s Wiki 图片命中缓存: %s", label, item_name)
            return cache_path

        image_path = save_func(html, url)
        if not image_path or not wait_image_ready(image_path):
            return image_path
        os.makedirs(cache_dir, exist_ok=True)
        try:
            os.replace(image_path, cache_path)
        except OSError:
            # Another process may have created the same item between checks.
            if not os.path.exists(cache_path):
                raise
        logger.info("%s Wiki 图片写入缓存: %s", label, item_name)
        return cache_path if os.path.exists(cache_path) else image_path


def send_wiki_image(group_id, html, url, item_name):
    """在后台线程中截取并发送 Wiki 信息框图片。

    Args:
        html: 页面 HTML 内容（用于快速判断有无 infobox）
        url: Wiki 页面 URL
        item_name: 物品名称，用作持久化缓存键
    """
    try:
        image_path = _save_cached_wiki_image(
            item_name, html, url, save_infobox_screenshot, STARDEW_SCREENSHOT_DIR, "原版"
        )
        if image_path:
            send_image_with_retry(group_id, image_path)
        else:
            logger.info(f"[群 {group_id}] Wiki 信息框截图跳过或失败: {url}")
    except Exception as err:
        logger.error(f"[群 {group_id}] Wiki 信息框截图异常: {err}", exc_info=True)


def send_wiki_summary(
    group_id,
    message_id,
    summary,
    item_name=None,
    cache_dir=None,
    structured=True,
):
    image_path = _wiki_cached_image(item_name, cache_dir) if item_name and cache_dir else None
    send_group_forward_msg(
        group_id,
        _wiki_forward_nodes(
            summary,
            item_name or "",
            structured=structured,
        ),
    )
    if image_path:
        send_image_with_retry(group_id, image_path)


def send_wiki_error(group_id, message_id, err):
    send_group_msg(group_id, [reply(message_id), text(f"发生错误，错误代码：{err.status_code}。\n这并不是机器人的问题")])


def _auto_summarize(group_id, message_id, summary, page_url):
    """当 summary 只是裸 Wiki 链接或描述过长时，用 AI 生成摘要替换。"""
    if summary.startswith("Wiki链接："):
        logger.info(f"[群 {group_id}] 检测到裸链接，启动 AI 摘要: {page_url}")
        ai_summary = summarize_wiki_page(page_url)
        if ai_summary:
            return f"{ai_summary}\n（以上为AI总结）\n\nWiki链接：{page_url}"
        return summary  # AI 失败，退回裸链接

    return summary  # 正常 infobox 内容，不动


# ── SVE Wiki helpers ──

def sve_send_wiki_image(group_id, html, url, item_name):
    """在后台线程中截取并发送 SVE Wiki 信息框图片。

    Args:
        html: 页面 HTML 内容（用于快速判断有无 infobox）
        url: Wiki 页面 URL
        item_name: 物品名称，用作持久化缓存键
    """
    try:
        image_path = _save_cached_wiki_image(
            item_name, html, url, sve_save_infobox_screenshot, SVE_SCREENSHOT_DIR, "SVE"
        )
        if image_path:
            send_image_with_retry(group_id, image_path)
        else:
            logger.info(f"[群 {group_id}] SVE Wiki 信息框截图跳过或失败: {url}")
    except Exception as err:
        logger.error(f"[群 {group_id}] SVE Wiki 信息框截图异常: {err}", exc_info=True)


def sve_send_wiki_summary(
    group_id,
    message_id,
    summary,
    item_name=None,
    cache_dir=None,
    structured=True,
):
    image_path = _wiki_cached_image(item_name, cache_dir) if item_name and cache_dir else None
    send_group_forward_msg(
        group_id,
        _wiki_forward_nodes(
            summary,
            item_name or "",
            structured=structured,
        ),
    )
    if image_path:
        send_image_with_retry(group_id, image_path)


def sve_send_wiki_error(group_id, message_id, err):
    send_group_msg(group_id, [reply(message_id), text(f"发生错误，错误代码：{err.status_code}。\n这并不是机器人的问题")])


def _timeout_search(key):
    with _pending_lock:
        pending = PENDING_SEARCHES.pop(key, None)
    if pending:
        send_group_msg(
            pending["group_id"],
            [reply(pending["message_id"]), text("回复超时")],
        )


def _sve_timeout_search(key):
    with _pending_lock:
        pending = SVE_PENDING_SEARCHES.pop(key, None)
    if pending:
        send_group_msg(
            pending["group_id"],
            [reply(pending["message_id"]), text("SVE回复超时")],
        )


def handle_wiki_command(message, group_id, user_id, message_id, self_id):
    """处理 Wiki / SVE Wiki 查询命令"""
    msg_text = _msg_text(message)
    is_at_bot = has_at(message, self_id)
    is_at_other = has_at_other(message, self_id)

    # @ 了别人但没 @ 机器人 → 不处理
    if is_at_other and not is_at_bot:
        return False

    pending_key = (group_id, user_id)
    with _pending_lock:
        pending = PENDING_SEARCHES.get(pending_key)

    # 数字选择搜索结果
    if msg_text.isdigit() and pending:
        choice = int(msg_text)
        results = pending["results"]
        if 1 <= choice <= len(results):
            timer = pending.get("timer")
            if timer:
                timer.cancel()
            with _pending_lock:
                PENDING_SEARCHES.pop(pending_key, None)
            selected = results[choice - 1]
            try:
                summary, html, page_url, has_image = get_page_summary_data(selected["url"])
            except WikiRequestError as err:
                send_wiki_error(group_id, message_id, err)
                return True
            summary = _auto_summarize(group_id, message_id, summary, page_url)
            item_name = selected.get("title") or pending.get("item_name")
            send_wiki_summary(
                group_id,
                message_id,
                summary,
                item_name=item_name,
                cache_dir=STARDEW_SCREENSHOT_DIR,
                structured=has_image,
            )
            if has_image and not _wiki_cached_image(item_name, STARDEW_SCREENSHOT_DIR):
                threading.Thread(
                    target=send_wiki_image,
                    args=(group_id, html, page_url, selected.get("title") or pending.get("item_name")),
                    daemon=True,
                ).start()
        return True

    sve_pending_key = ("sve", group_id, user_id)
    with _pending_lock:
        sve_pending = SVE_PENDING_SEARCHES.get(sve_pending_key)
    if msg_text.isdigit() and sve_pending:
        choice = int(msg_text)
        results = sve_pending["results"]
        if 1 <= choice <= len(results):
            timer = sve_pending.get("timer")
            if timer:
                timer.cancel()
            with _pending_lock:
                SVE_PENDING_SEARCHES.pop(sve_pending_key, None)
            selected = results[choice - 1]
            try:
                summary, html, page_url, has_image = sve_get_page_summary_data(selected["url"])
            except SveWikiRequestError as err:
                sve_send_wiki_error(group_id, message_id, err)
                return True
            item_name = selected.get("title") or sve_pending.get("item_name")
            sve_send_wiki_summary(
                group_id,
                message_id,
                summary,
                item_name=item_name,
                cache_dir=SVE_SCREENSHOT_DIR,
                structured=has_image,
            )
            if has_image and not _wiki_cached_image(item_name, SVE_SCREENSHOT_DIR):
                threading.Thread(
                    target=sve_send_wiki_image,
                    args=(group_id, html, page_url, selected.get("title") or sve_pending.get("item_name")),
                    daemon=True,
                ).start()
        return True

    # 查询
    if msg_text.startswith("查询"):
        if pending:
            send_group_msg(group_id, [reply(message_id), text("上一个查询没有完成")])
            return True

        search_text = msg_text.removeprefix("查询").strip()
        if search_text:
            try:
                direct_summary, html, page_url, has_image = get_direct_page_summary_data(search_text)
            except WikiRequestError as err:
                send_wiki_error(group_id, message_id, err)
                return True

            if direct_summary:
                direct_summary = _auto_summarize(group_id, message_id, direct_summary, page_url)
                send_wiki_summary(
                    group_id,
                    message_id,
                    direct_summary,
                    item_name=search_text,
                    cache_dir=STARDEW_SCREENSHOT_DIR,
                    structured=has_image,
                )
                if has_image and not _wiki_cached_image(search_text, STARDEW_SCREENSHOT_DIR):
                    threading.Thread(
                        target=send_wiki_image,
                        args=(group_id, html, page_url, search_text),
                        daemon=True,
                    ).start()
                return True

            try:
                results = get_search_results(search_text)
            except WikiRequestError as err:
                send_wiki_error(group_id, message_id, err)
                return True

            result_lines = "\n".join(
                f"{index}.{result['title']}" for index, result in enumerate(results, 1)
            )
            if not result_lines:
                result_lines = "没有搜索结果"
            result_text = f"以下是 {search_text} 的搜索结果：\n\n{result_lines}"
            if results:
                result_text = f"{result_text}\n\n请在 {SELECTION_TIMEOUT_SECONDS:g} 秒内回复1-{len(results)}"
                timer = threading.Timer(SELECTION_TIMEOUT_SECONDS, _timeout_search, args=(pending_key,))
                with _pending_lock:
                    PENDING_SEARCHES[pending_key] = {
                        "group_id": group_id,
                        "message_id": message_id,
                        "item_name": search_text,
                        "results": results,
                        "timer": timer,
                    }
                timer.start()
            send_group_msg(group_id, [reply(message_id), text(result_text)])
        return True

    # sve查询
    if msg_text.startswith("sve查询"):
        if sve_pending:
            send_group_msg(group_id, [reply(message_id), text("上一个SVE查询没有完成")])
            return True

        search_text = msg_text.removeprefix("sve查询").strip()
        if search_text:
            try:
                direct_summary, html, page_url, has_image = sve_get_direct_page_summary_data(search_text)
            except SveWikiRequestError as err:
                sve_send_wiki_error(group_id, message_id, err)
                return True

            if direct_summary:
                sve_send_wiki_summary(
                    group_id,
                    message_id,
                    direct_summary,
                    item_name=search_text,
                    cache_dir=SVE_SCREENSHOT_DIR,
                    structured=has_image,
                )
                if has_image and not _wiki_cached_image(search_text, SVE_SCREENSHOT_DIR):
                    threading.Thread(
                        target=sve_send_wiki_image,
                        args=(group_id, html, page_url, search_text),
                        daemon=True,
                    ).start()
                return True

            try:
                results = sve_get_search_results(search_text)
            except SveWikiRequestError as err:
                sve_send_wiki_error(group_id, message_id, err)
                return True

            result_lines = "\n".join(
                f"{index}.{result['title']}" for index, result in enumerate(results, 1)
            )
            if not result_lines:
                result_lines = "没有搜索结果"
            result_text = f"以下是 {search_text} 的SVE Wiki搜索结果：\n\n{result_lines}"
            if results:
                result_text = f"{result_text}\n\n请在 {SELECTION_TIMEOUT_SECONDS:g} 秒内回复1-{len(results)}"
                timer = threading.Timer(SELECTION_TIMEOUT_SECONDS, _sve_timeout_search, args=(sve_pending_key,))
                with _pending_lock:
                    SVE_PENDING_SEARCHES[sve_pending_key] = {
                        "group_id": group_id,
                        "message_id": message_id,
                        "item_name": search_text,
                        "results": results,
                        "timer": timer,
                    }
                timer.start()
            send_group_msg(group_id, [reply(message_id), text(result_text)])
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════
# 命令 handler
# ═══════════════════════════════════════════════════════════════════════

def _handle_title(message, group_id, user_id, msg_text, message_id, self_id):
    """"我要头衔xxx" → 设置群头衔"""
    special_title = msg_text.strip().removeprefix("我要头衔").strip()
    if not special_title:
        return False

    logger.info(f"[群 {group_id}] 用户 {user_id} 请求设置头衔: {special_title!r}")
    result = set_group_special_title(group_id, user_id, special_title)
    if result:
        send_group_msg(group_id, [reply(message_id), text("好啦！")])
    else:
        send_group_msg(group_id, [reply(message_id), text("不可以哦！")])
    return True


def _handle_wiki(message, group_id, user_id, msg_text, message_id, self_id):
    """Wiki 查询 — 代理到 handle_wiki_command"""
    return handle_wiki_command(message, group_id, user_id, message_id, self_id)


def _handle_ai_chat(message, group_id, user_id, msg_text, message_id, self_id):
    """@机器人 + 有内容 → AI 对话"""
    return handle_ai_chat_command(message, group_id, user_id, msg_text, message_id, self_id,
                                  has_at, _all_triggers, has_reply_to_bot,
                                  image_urls=_image_urls(message))


def _handle_proactive(message, group_id, user_id, msg_text, message_id, self_id):
    """主动搭话（概率触发）"""
    return handle_proactive(message, group_id, user_id, msg_text, message_id, self_id,
                            has_at, _all_triggers, has_reply,
                            image_urls=_image_urls(message),
                            recent_context=_recent_group_context(group_id))


def _handle_chat(message, group_id, user_id, msg_text, message_id, self_id):
    """@机器人 无实质内容 → 随机回复（兜底）"""
    if not has_at(message, self_id):
        return False

    text_stripped = msg_text.strip()
    if text_stripped.startswith(_all_triggers()):
        return False
    if text_stripped.isdigit():
        return False

    replies = ["到！", "怎么了！", "叫我什么事呀？"]
    reply_text = random.choice(replies)
    logger.info(f"[群 {group_id}] 用户 {user_id} @机器人, 回复: {reply_text}")
    send_group_msg(group_id, [reply(message_id), text(reply_text)])
    return True


# ═══════════════════════════════════════════════════════════════════════
# 命令注册表
# ═══════════════════════════════════════════════════════════════════════

_commands = [
    {
        "trigger": None,
        "handler": _handle_wiki,
        "groups": WIKI_GROUPS,
    },
    {
        "trigger": None,
        "handler": _handle_proactive,
        "groups": AI_CHAT_GROUPS,
    },
    {
        "trigger": "我要头衔",
        "handler": _handle_title,
        "groups": TITLE_GROUPS,
    },
    {
        "trigger": None,
        "handler": _handle_ai_chat,
        "groups": AI_CHAT_GROUPS,
    },
    {
        "trigger": None,
        "handler": _handle_chat,
        "groups": AI_CHAT_GROUPS,
    },
]


def _match_trigger(msg_text, trigger):
    text = msg_text.strip()
    return text.startswith(trigger)


def _dispatch_commands(message, group_id, user_id, msg_text, message_id, self_id):
    """遍历注册表，按序匹配，命中即停"""
    is_at_other = has_at_other(message, self_id)
    is_at_bot = has_at(message, self_id)
    is_reply = has_reply(message)
    is_reply_to_bot = has_reply_to_bot(message)

    # 消息指向别人（@别人 或 回复别人）且没有指向 bot → 跳过
    is_targeting_other = is_at_other or (is_reply and not is_reply_to_bot)
    is_targeting_bot = is_at_bot or is_reply_to_bot
    if is_targeting_other and not is_targeting_bot:
        return

    for cmd in _commands:
        groups = cmd["groups"]
        if groups is not None and group_id not in groups:
            continue
        trigger = cmd["trigger"]
        if trigger is not None and not _match_trigger(msg_text, trigger):
            continue
        if cmd["handler"](message, group_id, user_id, msg_text, message_id, self_id):
            return


def _all_triggers():
    """收集注册表中所有非 None 触发词"""
    triggers = []
    for cmd in _commands:
        t = cmd["trigger"]
        if t is None:
            continue
        triggers.extend(t if isinstance(t, tuple) else [t])
    return tuple(triggers)


# ═══════════════════════════════════════════════════════════════════════
# 统一入口（app.py before_request 调用）
# ═══════════════════════════════════════════════════════════════════════

def dispatch_group_event(body):
    """所有群相关事件统一入口"""

    # ── 事件分发（notice / request） ──
    result = _dispatch_event(body)
    if result is not None:
        return result

    # ── message 事件 ──
    sender = body.get("sender")
    if not sender:
        return None

    message = body.get("message") or []
    msg_text = _msg_text(message)
    log_text = _msg_log_text(message)
    message_id = body.get("message_id")
    message_type = body.get("message_type")
    self_id = body.get("self_id")
    user_id = sender.get("user_id")
    group_id = body.get("group_id")
    nickname = sender.get("nickname")

    # 日志
    if message_type == "group":
        logger.info(f"[群 {group_id}] [{nickname} {user_id}]: {log_text}")
    elif message_type == "private":
        logger.info(f"[私聊] [{nickname} {user_id}]: {log_text}")
    else:
        logger.info(f"[{message_type or 'unknown'}] [{nickname} {user_id}]: {log_text}")

    # 只处理群消息
    if message_type != "group":
        return None

    # ── 群消息功能分发 ──
    _dispatch_commands(message, group_id, user_id, msg_text, message_id, self_id)
    _record_recent_group_message(group_id, user_id, message)

    return None
