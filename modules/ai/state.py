"""AI 好感度与对话历史的运行状态持久化。"""

import json
import os
import tempfile
import threading

from config import section, state_path
from logger import logger

_ai_config = section("ai")
_storage_config = section("storage")

COOLDOWN_SECONDS = float(_ai_config["cooldown_seconds"])
DEFAULT_AFFECTION = float(_ai_config["default_affection"])
AFFECTION_CHANGE_LIMIT = float(_ai_config["affection_change_limit"])
MAX_HISTORY = int(_ai_config["max_history"])
MAX_TOOL_ROUNDS = int(_ai_config["max_tool_rounds"])

_DATA_FILE = str(state_path(str(_storage_config["affections_file"])))
_HISTORY_FILE = str(state_path(str(_storage_config["ai_histories_file"])))
_affections: dict[str, float] = {}
_histories: dict[str, list[dict]] = {}
_state_lock = threading.RLock()


def _load():
    global _affections, _histories
    try:
        if os.path.exists(_DATA_FILE):
            with open(_DATA_FILE, "r", encoding="utf-8") as file:
                raw = json.load(file)
                if not isinstance(raw, dict):
                    raise ValueError("affections data must be an object")
                _affections = {str(key): float(value) for key, value in raw.items()}
            logger.info(f"[AI Chat] 已加载 {len(_affections)} 条好感度")
    except Exception as error:
        logger.error(f"[AI Chat] 加载好感度失败: {error}")

    try:
        if os.path.exists(_HISTORY_FILE):
            with open(_HISTORY_FILE, "r", encoding="utf-8") as file:
                raw = json.load(file)
                if not isinstance(raw, dict):
                    raise ValueError("history data must be an object")
                _histories = raw
            logger.info(f"[AI Chat] 已加载 {len(_histories)} 条对话历史")
    except Exception as error:
        logger.error(f"[AI Chat] 加载对话历史失败: {error}")


def _atomic_dump(path: str, data):
    directory = os.path.dirname(path)
    file_descriptor, temp_path = tempfile.mkstemp(
        prefix=".bot-", suffix=".tmp", dir=directory
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _save_affections():
    try:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        _atomic_dump(_DATA_FILE, _affections)
    except Exception as error:
        logger.error(f"[AI Chat] 保存好感度失败: {error}")


def _save_histories():
    try:
        os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
        _atomic_dump(_HISTORY_FILE, _histories)
    except Exception as error:
        logger.error(f"[AI Chat] 保存对话历史失败: {error}")


_load()


def get_affections() -> dict[str, float]:
    return _affections


def get_histories() -> dict[str, list[dict]]:
    return _histories


def save_all():
    with _state_lock:
        _save_affections()
        _save_histories()
