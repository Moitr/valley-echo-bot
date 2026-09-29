from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = Path(__file__).resolve()

# 连接入口：启动机器人前最需要检查这一组。
WEBSOCKET = {
    "url": "",
    "access_token": "",
    "log_level": "INFO",
    "event_workers": 8,
    "reconnect_seconds": 5,
    "ping_interval_seconds": 20,
    "ping_timeout_seconds": 10,
    "autoreload_enabled": True,
    "autoreload_poll_seconds": 2,
}

# OneBot 请求队列和超时。
API = {
    "max_pending": 1000,
    "default_timeout_seconds": 10,
    "long_timeout_seconds": 30,
}

# 群组开关：default 使用 default_groups，any 表示所有群，off 表示关闭。
GROUPS = {
    "default_groups": [],
    "welcome": "off",  # 入群欢迎和自动审批
    "leave": "off",  # 离开/被踢通知
    "ai_chat": "off",  # 主动搭话和 AI 对话
    "shared_memory": "off",  # 群聊共享记忆；只影响该群的 AI 对话
    "title": "off",  # 头衔功能
    "wiki": "off",  # Wiki 查询
    "poke": "off",  # 被戳一戳时回复并戳回
}

# AI 服务和对话策略。
AI = {
    "api_key": "",
    "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "chat_model": "glm-5.3-flash",
    "wiki_summary_model": "glm-5.3",
    "web_search_model": "glm-5.3-flash",
    "web_search_url": "https://open.bigmodel.cn/api/paas/v4/web_search",
    "web_search_count": 12,
    "web_search_recency_filter": "noLimit",
    "web_search_content_size": "high",
    "web_search_max_tokens": 4096,
    "web_search_temperature": 0.2,
    "web_search_request_timeout_seconds": 120,
    "web_search_page_width": 1000,
    "web_search_page_height": 800,
    "web_search_page_max_height": 7200,
    "cooldown_seconds": 0,  # 同一用户两次 AI 请求的最短间隔；0 表示不限制
    "default_affection": 45,  # 新用户的初始好感度
    "affection_change_limit": 3,  # 单次对话好感度变化的绝对值上限
    "proactive_min_affection": 35,  # 低于此值不主动搭话
    "max_history": 60,  # 每个用户保留的历史消息条数（约 30 轮问答）
    "max_tool_rounds": 5,  # 一次回答最多连续调用工具的轮数
    "recent_speaker_window_seconds": 600,  # 主动搭话统计近期发言人的时间窗口
    "chat_temperature": 1,  # 普通对话随机性；保留变化，避免措辞过度发散
    "chat_top_p": 0.95,  # 普通对话核采样范围
    "chat_max_tokens": 4096,  # 普通对话最大输出 token 数
    "streaming_enabled": True,  # 是否使用 SSE 流式接收
    "stream_request_timeout_seconds": 90,  # 流式请求首包/相邻数据最长等待时间
    "request_timeout_seconds": 30,  # 非流式请求超时
    "max_input_images": 3,  # 单轮最多发送给视觉模型的图片数
    "reply_context_max_characters": 2000,  # 引用消息注入 AI 的最大字符数
    "proactive_context_messages": 6,  # 主动搭话读取的近期消息数
    "proactive_context_max_characters": 1200,  # 主动搭话上下文最大字符数
    "shared_memory_model": "glm-5.3-flash",  # 群共享记忆审核模型
    "shared_memory_max_items_per_group": 60,  # 每个群最多保留的事实条数
    "shared_memory_max_fact_characters": 160,  # 单条事实最大字符数
    "shared_memory_context_max_characters": 1600,  # 注入普通对话的群记忆最大字符数
    "shared_memory_extraction_context_max_characters": 600,  # 记忆审核带入的旧记忆字符数
    "shared_memory_extraction_max_tokens": 80,  # 记忆审核模型最大输出 token 数
}


WELCOME = {
    "image_path": "resources/images/welcome.jpg",
    "max_image_size": 500,
}

WIKI = {
    "request_timeout_seconds": 10,
    "selection_timeout_seconds": 60,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "summary_request_timeout_seconds": 30,
    "summary_temperature": 0.0,
    "summary_max_tokens": 600,
    "summary_max_source_characters": 4000,
    "summary_head_characters": 2500,
    "summary_tail_characters": 1500,
}

POKE = {
    "reply_messages": [
        " 你戳我干嘛呀？",
        " 欸？怎么突然戳我啦？",
        " 收到啦，我也戳你一下。",
        " 好痒呀，不许欺负我哦。",
        " 嘿嘿，戳回去啦！",
    ],
    "poke_back": True,
}

WIKI_STARDEW = {
    "search_url": "https://wiki.biligame.com/stardewvalley/index.php",
    "base_url": "https://wiki.biligame.com",
    "page_base_url": "https://wiki.biligame.com/stardewvalley/",
    "screenshot_dir": "data/wiki_images",
}

WIKI_SVE = {
    "search_url": "https://sve.p1.wiki/index.php",
    "base_url": "https://sve.p1.wiki",
    "page_base_url": "https://sve.p1.wiki/",
    "screenshot_dir": "data/sve_wiki_images",
}

BROWSER = {
    "browser": "auto",  # auto / chromium / firefox / webkit
    "path": "",
    "headless": True,
    "page_load_timeout_seconds": 30,
    "element_timeout_seconds": 20,
}

STORAGE = {
    "affections_file": "data/affections.json",
    "ai_histories_file": "data/ai_histories.json",
    "shared_memories_file": "data/shared_memories.json",
    "feed_cards_file": "resources/feed_cards.json",
    "fishing_image_path": "resources/images/fishing_guide.jpg",
}

CONFIG = {
    "websocket": WEBSOCKET,
    "api": API,
    "groups": GROUPS,
    "ai": AI,
    "welcome": WELCOME,
    "wiki": WIKI,
    "poke": POKE,
    "wiki.stardew": WIKI_STARDEW,
    "wiki.sve": WIKI_SVE,
    "browser": BROWSER,
    "storage": STORAGE,
}


def section(name: str) -> dict[str, Any]:
    value = CONFIG.get(name)
    if not isinstance(value, dict):
        raise RuntimeError(f"Missing or invalid config section: {name}")
    return value


def state_path(configured_path: str | Path) -> Path:
    return PROJECT_ROOT / Path(configured_path)


def group_ids(name: str) -> list[int] | None:
    configured = section("groups").get(name)
    if configured == "any":
        return None
    if configured == "off":
        return []
    if configured == "default":
        configured = section("groups")["default_groups"]
    if not isinstance(configured, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) and item > 0
        for item in configured
    ):
        raise RuntimeError(f"groups.{name} must be 'default', 'any', 'off', or a list of positive IDs")
    return configured.copy()


WELCOME_GROUPS = group_ids("welcome")
LEAVE_GROUPS = group_ids("leave")
AI_CHAT_GROUPS = group_ids("ai_chat")
SHARED_MEMORY_GROUPS = group_ids("shared_memory")
TITLE_GROUPS = group_ids("title")
WIKI_GROUPS = group_ids("wiki")
POKE_GROUPS = group_ids("poke")

_AI = section("ai")
DEEPSEEK_KEY = str(_AI["api_key"]).strip()
DEEPSEEK_URL = str(_AI["url"]).strip()
DEEPSEEK_MODEL = str(_AI["chat_model"]).strip()
DEEPSEEK_SUMMARIZE_MODEL = str(_AI["wiki_summary_model"]).strip()
