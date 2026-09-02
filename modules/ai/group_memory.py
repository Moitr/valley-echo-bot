"""Persistent, group-scoped facts used as shared AI conversation memory."""

import json
import os
import tempfile
import threading
import time

from config import section, state_path
from logger import logger

_ai_config = section("ai")
_storage_config = section("storage")

_MEMORY_FILE = str(state_path(str(_storage_config["shared_memories_file"])))
MAX_ITEMS_PER_GROUP = int(_ai_config["shared_memory_max_items_per_group"])
MAX_FACT_CHARACTERS = int(_ai_config["shared_memory_max_fact_characters"])
MAX_CONTEXT_CHARACTERS = int(_ai_config["shared_memory_context_max_characters"])

_memories: dict[str, list[dict[str, object]]] = {}
_memory_lock = threading.RLock()


def _atomic_dump(path: str, data: object):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix=".bot-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def _normalize_fact(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:MAX_FACT_CHARACTERS].strip()


def _load():
    global _memories
    try:
        if not os.path.exists(_MEMORY_FILE):
            return
        with open(_MEMORY_FILE, "r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError("shared memories must be an object")

        loaded: dict[str, list[dict[str, object]]] = {}
        for group_id, entries in raw.items():
            if not isinstance(entries, list):
                continue
            normalized_entries = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                fact = _normalize_fact(entry.get("fact"))
                if not fact:
                    continue
                updated_at = entry.get("updated_at", 0)
                try:
                    updated_at = float(updated_at)
                except (TypeError, ValueError):
                    updated_at = 0.0
                normalized_entries.append({"fact": fact, "updated_at": updated_at})
            if normalized_entries:
                loaded[str(group_id)] = normalized_entries[-MAX_ITEMS_PER_GROUP:]
        _memories = loaded
        logger.info(f"[Shared Memory] 已加载 {sum(map(len, loaded.values()))} 条群记忆")
    except Exception as error:
        logger.error(f"[Shared Memory] 加载失败: {error}")


def _save():
    try:
        _atomic_dump(_MEMORY_FILE, _memories)
    except Exception as error:
        logger.error(f"[Shared Memory] 保存失败: {error}")


def get_context(
    group_id: int | str,
    max_characters: int | None = None,
    contains: str = "",
) -> str:
    """Return bounded factual context for one group, without cross-group data."""
    with _memory_lock:
        entries = list(_memories.get(str(group_id), []))

    limit = MAX_CONTEXT_CHARACTERS if max_characters is None else max(0, int(max_characters))
    if limit <= 0:
        return ""
    selected: list[str] = []
    total = 0
    for entry in reversed(entries):
        fact = _normalize_fact(entry.get("fact"))
        if not fact:
            continue
        if contains and contains not in fact:
            continue
        addition = len(fact) + 2
        if selected and total + addition > limit:
            break
        selected.append(fact)
        total += addition
    selected.reverse()
    return "\n".join(f"- {fact}" for fact in selected)


def record(group_id: int | str, fact: str, replace: str = "") -> bool:
    """Add or replace one sanitized fact and persist it atomically."""
    fact = _normalize_fact(fact)
    replace = _normalize_fact(replace)
    if not fact:
        return False

    key = str(group_id)
    now = time.time()
    with _memory_lock:
        entries = _memories.setdefault(key, [])
        if replace:
            entries[:] = [entry for entry in entries if entry.get("fact") != replace]

        for entry in entries:
            if entry.get("fact") == fact:
                entry["updated_at"] = now
                _save()
                return False

        entries.append({"fact": fact, "updated_at": now})
        if MAX_ITEMS_PER_GROUP > 0 and len(entries) > MAX_ITEMS_PER_GROUP:
            entries.sort(key=lambda entry: float(entry.get("updated_at", 0) or 0))
            del entries[:-MAX_ITEMS_PER_GROUP]
        _save()
    logger.info(f"[Shared Memory] 群 {group_id} 记录: {fact}")
    return True


_load()
