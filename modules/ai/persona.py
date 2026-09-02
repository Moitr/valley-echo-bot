"""小芳的人设、系统提示词、工具定义和常量"""

import json
import os
import tempfile
import threading

from logger import logger
from bot.config import section, state_path
from modules.ai.prompt import PROACTIVE_SYSTEM_PROMPT, SYSTEM_PROMPT

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

_ai_config = section("ai")
_storage_config = section("storage")

COOLDOWN_SECONDS = float(_ai_config["cooldown_seconds"])
DEFAULT_AFFECTION = float(_ai_config["default_affection"])
AFFECTION_CHANGE_LIMIT = float(_ai_config["affection_change_limit"])
MAX_HISTORY = int(_ai_config["max_history"])
MAX_TOOL_ROUNDS = int(_ai_config["max_tool_rounds"])

_DATA_FILE = str(state_path(str(_storage_config["affections_file"])))
_HISTORY_FILE = str(state_path(str(_storage_config["ai_histories_file"])))

# ═══════════════════════════════════════════════════════════════
# 好感度 & 对话历史持久化
# ═══════════════════════════════════════════════════════════════

_affections: dict[str, float] = {}
_histories: dict[str, list[dict]] = {}
_state_lock = threading.RLock()


def _load():
    global _affections, _histories
    try:
        if os.path.exists(_DATA_FILE):
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if not isinstance(raw, dict):
                    raise ValueError("affections data must be an object")
                _affections = {str(k): float(v) for k, v in raw.items()}
            logger.info(f"[AI Chat] 已加载 {len(_affections)} 条好感度")
    except Exception as e:
        logger.error(f"[AI Chat] 加载好感度失败: {e}")

    try:
        if os.path.exists(_HISTORY_FILE):
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if not isinstance(raw, dict):
                    raise ValueError("history data must be an object")
                _histories = raw
            logger.info(f"[AI Chat] 已加载 {len(_histories)} 条对话历史")
    except Exception as e:
        logger.error(f"[AI Chat] 加载对话历史失败: {e}")


def _atomic_dump(path: str, data):
    directory = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(prefix=".bot-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _save():
    try:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        _atomic_dump(_DATA_FILE, _affections)
    except Exception as e:
        logger.error(f"[AI Chat] 保存好感度失败: {e}")


def _save_history():
    try:
        os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
        _atomic_dump(_HISTORY_FILE, _histories)
    except Exception as e:
        logger.error(f"[AI Chat] 保存对话历史失败: {e}")


_load()


def get_affections() -> dict[str, float]:
    return _affections


def get_histories() -> dict[str, list[dict]]:
    return _histories


def save_all():
    with _state_lock:
        _save()
        _save_history()


from modules.ai.tools import TOOLS
