"""AI 对话 handler — 由 handlers.py 注册表调用"""

import base64
import json
import os
import random
import re
import threading
import time
from collections import defaultdict

from bot.transport import image, send_group_json_card, send_group_msg, text
from config import section, state_path
from modules.ai.service import (
    chat,
    get_affection,
    is_cooldown,
    proactive_chat,
    remember_group_exchange,
    set_affection,
    set_cooldown,
)
from logger import logger

# 近期发言追踪：{group_id: {user_id: timestamp}}
_recent_speakers: dict[str, dict[str, float]] = defaultdict(dict)
_ai_config = section("ai")
_storage_config = section("storage")
_RECENT_WINDOW = float(_ai_config["recent_speaker_window_seconds"])
_PROACTIVE_MIN_AFFECTION = float(_ai_config["proactive_min_affection"])


def _format_ai_log_text(text_stripped, image_urls):
    """返回不暴露图片地址的 AI 请求日志摘要。"""
    if image_urls:
        return f"{text_stripped} [图片]"
    return text_stripped


def _record_speaker(group_id, user_id):
    """记录用户发言时间，并清理过期记录"""
    now = time.time()
    group = _recent_speakers[str(group_id)]
    # 清理该群过期记录
    expired = [uid for uid, ts in group.items() if now - ts > _RECENT_WINDOW]
    for uid in expired:
        del group[uid]
    group[str(user_id)] = now


def _count_recent_speakers(group_id) -> int:
    """返回最近 _RECENT_WINDOW 秒内发言的不同用户数（含当前用户）"""
    now = time.time()
    group = _recent_speakers.get(str(group_id), {})
    count = sum(1 for ts in group.values() if now - ts <= _RECENT_WINDOW)
    return max(count, 1)  # 至少 1（当前用户）

# 卡片数据（模组教程 + 矿洞分布）
_CARDS_FILE = str(state_path(str(_storage_config["feed_cards_file"])))
_CARDS: dict | None = None

# 星露谷钓鱼图
_FISHING_IMAGE = str(state_path(str(_storage_config["fishing_image_path"])))

_FISHING_IMAGE_B64: str | None = None


def _load_fishing_image():
    """加载钓鱼图片并转为 base64"""
    global _FISHING_IMAGE_B64
    if _FISHING_IMAGE_B64 is None:
        if os.path.exists(_FISHING_IMAGE):
            with open(_FISHING_IMAGE, "rb") as f:
                _FISHING_IMAGE_B64 = "base64://" + base64.b64encode(f.read()).decode("ascii")
            logger.info(f"[AI] 钓鱼图片已加载: {_FISHING_IMAGE}")
        else:
            logger.warning(f"[AI] 钓鱼图片不存在: {_FISHING_IMAGE}")
    return _FISHING_IMAGE_B64


def _load_cards():
    global _CARDS
    if _CARDS is None:
        try:
            if os.path.exists(_CARDS_FILE):
                with open(_CARDS_FILE, encoding="utf-8") as f:
                    _CARDS = json.load(f)
        except Exception:
            _CARDS = None
    return _CARDS


def _strip_markdown(text: str) -> str:
    """去掉 AI 偶尔输出的 Markdown 语法（QQ 不支持）"""
    # 粗体：**text**  __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # 斜体：*text*  _text_（注意不要误删代码标识符里的下划线，如 search_game_data）
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<![a-zA-Z0-9])_(.+?)_(?![a-zA-Z0-9])", r"\1", text)
    # 删除线：~~text~~
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # 行内代码：`text`
    text = re.sub(r"`(.+?)`", r"\1", text)
    # 标题：### text → text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    return text


def _send_speech(group_id, speech):
    """发送消息：speech 可以是字符串或字符串列表，多条消息间有自然的短暂延迟"""
    if isinstance(speech, list):
        for i, msg in enumerate(speech):
            if not isinstance(msg, str) or not msg.strip():
                continue
            if i > 0:
                time.sleep(random.uniform(0.4, 1.0))
            send_group_msg(group_id, [text(_strip_markdown(msg))])
    else:
        speech = str(speech or "").strip()
        if speech:
            send_group_msg(group_id, [text(_strip_markdown(speech))])


def _stream_speech_sender(group_id, sent_messages):
    """返回流式 speech 回调；每个完整消息只发送一次。"""
    def _send_piece(piece):
        piece = str(piece or "").strip()
        if not piece:
            return
        try:
            _send_speech(group_id, piece)
        except Exception:
            logger.exception(f"[群 {group_id}] 流式 speech 发送失败")
            return
        sent_messages.append(piece)

    return _send_piece


def _send_unsent_speech(group_id, speech, sent_count):
    """流式解析只发出部分消息时，补发最终 JSON 中剩余的消息。"""
    if isinstance(speech, list):
        remaining = speech[sent_count:]
        if remaining:
            _send_speech(group_id, remaining)
    elif not sent_count:
        _send_speech(group_id, speech)


def _run_background(task, group_id):
    try:
        task()
    except Exception:
        logger.exception(f"[群 {group_id}] AI 后台任务异常")
        send_group_msg(group_id, [text("脑袋卡住了，等会儿再和我说吧！")])


def handle_ai_chat_command(message, group_id, user_id, msg_text, message_id, self_id,
                           has_at, all_triggers, has_reply_to_bot=None, image_urls=None):
    """@机器人 或 引用回复机器人 → AI 对话。返回 True 表示已处理"""
    image_urls = tuple(image_urls or ())
    # @ 和引用回复都可以触发，逻辑一致
    is_at_bot = has_at(message, self_id)
    is_reply_to_bot = has_reply_to_bot and has_reply_to_bot(message)

    if not is_at_bot and not is_reply_to_bot:
        return False

    text_stripped = msg_text.strip()
    if text_stripped.isdigit():
        return False
    if text_stripped.startswith(all_triggers()):
        return False

    # 有 @ 或引用回复，但没有文字内容 → 图片消息仍交给视觉模型处理
    if not text_stripped:
        text_stripped = "请看看这张图片" if image_urls else "（用户引用了你的消息）"
        # 纯 @ 无文字也没有回复 → 留给兜底 handler
        if not image_urls and is_at_bot and not is_reply_to_bot:
            return False

    now = time.time()
    if is_cooldown(group_id, user_id, now):
        logger.info(f"[群 {group_id}] AI 请求被冷却限制: user={user_id}")
        return True
    set_cooldown(group_id, user_id, now)

    _record_speaker(group_id, user_id)
    logger.info(
        f"[群 {group_id}] 用户 {user_id} AI对话: "
        f"{_format_ai_log_text(text_stripped, image_urls)!r}"
    )

    affection = get_affection(group_id, user_id)

    def _call_and_reply():
        streamed_messages = []
        on_speech = _stream_speech_sender(group_id, streamed_messages)
        if image_urls:
            result = chat(
                group_id, user_id, text_stripped, affection,
                image_urls=image_urls, on_speech=on_speech,
            )
        else:
            result = chat(
                group_id, user_id, text_stripped, affection,
                on_speech=on_speech,
            )
        if result:
            speech, new_affection, send_card, send_mine_card, send_calendar_card, send_fish_img = result
            set_affection(group_id, user_id, new_affection)
            _send_unsent_speech(group_id, speech, len(streamed_messages))
            if send_card:
                cards = _load_cards()
                if cards and "mod_tutorial" in cards:
                    send_group_json_card(group_id, cards["mod_tutorial"])
            if send_mine_card:
                cards = _load_cards()
                if cards and "mine_distribution" in cards:
                    send_group_json_card(group_id, cards["mine_distribution"])
            if send_calendar_card:
                cards = _load_cards()
                if cards and "calendar" in cards:
                    send_group_json_card(group_id, cards["calendar"])
            if send_fish_img:
                fish_img = _load_fishing_image()
                if fish_img:
                    time.sleep(random.uniform(0.3, 0.6))
                    send_group_msg(group_id, [image(fish_img)])
                    logger.info(f"[群 {group_id}] 钓鱼图已发送")
            remember_group_exchange(group_id, user_id, text_stripped)
        else:
            if streamed_messages:
                logger.warning(
                    f"[群 {group_id}] AI 流式回复中断，已发送 {len(streamed_messages)} 条"
                )
            else:
                send_group_msg(group_id, [text("呜…脑袋卡住了，等会儿再说啦！")])

    threading.Thread(
        target=_run_background,
        args=(_call_and_reply, group_id),
        daemon=True,
        name="ai-chat",
    ).start()
    return True


def handle_proactive(message, group_id, user_id, msg_text, message_id, self_id,
                     has_at, all_triggers, has_reply=None, image_urls=None,
                     recent_context=""):
    """不 @ 时随机主动搭话。返回 True 表示已处理"""
    image_urls = tuple(image_urls or ())
    # 被 @ 了或引用回复了留给上面处理
    if has_at(message, self_id):
        return False
    if has_reply and has_reply(message):
        return False

    text_stripped = msg_text.strip()
    if not text_stripped and not image_urls:
        logger.info(f"[群 {group_id}] 主动搭话跳过: 空消息")
        return False
    if not text_stripped:
        text_stripped = "请看看这张图片"
    if text_stripped.isdigit():
        logger.info(f"[群 {group_id}] 主动搭话跳过: 纯数字消息 {text_stripped!r}")
        return False
    if text_stripped.startswith(all_triggers()):
        logger.info(f"[群 {group_id}] 主动搭话跳过: 命令消息 {text_stripped!r}")
        return False

    # 记录发言，统计近期活跃人数
    _record_speaker(group_id, user_id)
    recent_count = _count_recent_speakers(group_id)

    affection = get_affection(group_id, user_id)
    if affection < _PROACTIVE_MIN_AFFECTION:
        logger.info(f"[群 {group_id}] 主动搭话跳过: 好感过低 {affection}")
        return False

    # 概率 = (好感/100)² × (12% / 近期发言人数)，好感越高、人越少概率越大，上限 12%
    chance = (affection / 100) ** 2 * (0.12 / recent_count)
    roll = random.random()
    if roll > chance:
        logger.info(
            f"[群 {group_id}] 主动搭话未触发: user={user_id}, "
            f"好感={affection}, 近期发言{recent_count}人, 概率={chance:.1%}, 随机={roll:.1%}"
        )
        return False

    logger.info(
        f"[群 {group_id}] 用户 {user_id} 主动搭话触发"
        f" {_format_ai_log_text(text_stripped, image_urls)!r}"
        f" (近期发言{recent_count}人, 概率={chance:.1%}, 随机={roll:.1%})"
    )

    def _call_and_reply():
        streamed_messages = []
        on_speech = _stream_speech_sender(group_id, streamed_messages)
        if image_urls:
            result = proactive_chat(
                group_id,
                user_id,
                text_stripped,
                affection,
                image_urls=image_urls,
                recent_context=recent_context,
                on_speech=on_speech,
            )
        else:
            result = proactive_chat(
                group_id, user_id, text_stripped, affection,
                recent_context=recent_context,
                on_speech=on_speech,
            )
        if result:
            speech, new_affection, send_fish_img = result
            set_affection(group_id, user_id, new_affection)
            _send_unsent_speech(group_id, speech, len(streamed_messages))
            if send_fish_img:
                fish_img = _load_fishing_image()
                if fish_img:
                    time.sleep(random.uniform(0.3, 0.6))
                    send_group_msg(group_id, [image(fish_img)])
                    logger.info(f"[群 {group_id}] 主动搭话触发钓鱼图")
        elif streamed_messages:
            logger.warning(
                f"[群 {group_id}] 主动搭话流式回复中断，已发送 {len(streamed_messages)} 条"
            )

    threading.Thread(
        target=_run_background,
        args=(_call_and_reply, group_id),
        daemon=True,
        name="ai-proactive",
    ).start()
    return True
