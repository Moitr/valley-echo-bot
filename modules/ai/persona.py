"""旧的 AI 聚合导入入口；新代码请按职责导入对应模块。"""

from modules.ai.prompt import PROACTIVE_SYSTEM_PROMPT, SYSTEM_PROMPT
from modules.ai.state import (
    AFFECTION_CHANGE_LIMIT,
    COOLDOWN_SECONDS,
    DEFAULT_AFFECTION,
    MAX_HISTORY,
    MAX_TOOL_ROUNDS,
    get_affections,
    get_histories,
    save_all,
)
from modules.ai.tools import TOOLS

__all__ = [
    "AFFECTION_CHANGE_LIMIT",
    "COOLDOWN_SECONDS",
    "DEFAULT_AFFECTION",
    "MAX_HISTORY",
    "MAX_TOOL_ROUNDS",
    "PROACTIVE_SYSTEM_PROMPT",
    "SYSTEM_PROMPT",
    "TOOLS",
    "get_affections",
    "get_histories",
    "save_all",
]
