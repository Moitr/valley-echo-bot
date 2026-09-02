"""AI 业务服务门面。

Bot 层只依赖这里的公开能力，底层 API、流式协议和状态实现可独立重构。
"""

from modules.ai.client import (
    chat,
    get_affection,
    is_cooldown,
    proactive_chat,
    remember_group_exchange,
    set_affection,
    set_cooldown,
)

__all__ = [
    "chat",
    "get_affection",
    "is_cooldown",
    "proactive_chat",
    "remember_group_exchange",
    "set_affection",
    "set_cooldown",
]
