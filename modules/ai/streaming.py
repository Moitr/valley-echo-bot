"""流式响应的低层解析，不依赖具体模型或业务状态。"""

import json
import re

from logger import logger


class SpeechStreamParser:
    """从未完成的 JSON 中提取已经闭合的 speech 消息。"""

    def __init__(self, on_message):
        self._buffer = ""
        self._on_message = on_message
        self._speech_value_start: int | None = None
        self._mode: str | None = None
        self._cursor = 0
        self._sent = 0

    @staticmethod
    def _skip_space(value: str, index: int) -> int:
        while index < len(value) and value[index].isspace():
            index += 1
        return index

    @staticmethod
    def _read_string(value: str, start: int):
        if start >= len(value) or value[start] != '"':
            return None
        index = start + 1
        escaped = False
        while index < len(value):
            char = value[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                try:
                    return json.loads(value[start:index + 1]), index + 1
                except json.JSONDecodeError:
                    return None
            index += 1
        return None

    def feed(self, chunk: str):
        if not chunk or self._sent >= 3:
            return
        self._buffer += chunk
        if self._speech_value_start is None:
            match = re.search(r'"speech"\s*:\s*', self._buffer)
            if not match:
                return
            self._speech_value_start = match.end()
            self._cursor = self._skip_space(self._buffer, self._speech_value_start)
            if self._cursor >= len(self._buffer):
                return
            if self._buffer[self._cursor] == '"':
                self._mode = "string"
            elif self._buffer[self._cursor] == "[":
                self._mode = "array"
                self._cursor += 1
            else:
                self._mode = "invalid"

        if self._mode == "string":
            parsed = self._read_string(self._buffer, self._cursor)
            if parsed is not None:
                value, self._cursor = parsed
                if isinstance(value, str) and value.strip():
                    self._on_message(value.strip())
                    self._sent = 1
                self._mode = "done"
            return

        if self._mode != "array":
            return
        while self._sent < 3:
            self._cursor = self._skip_space(self._buffer, self._cursor)
            if self._cursor >= len(self._buffer):
                return
            if self._buffer[self._cursor] == "]":
                self._mode = "done"
                return
            if self._buffer[self._cursor] == ",":
                self._cursor += 1
                self._cursor = self._skip_space(self._buffer, self._cursor)
                if self._cursor >= len(self._buffer):
                    return
            parsed = self._read_string(self._buffer, self._cursor)
            if parsed is None:
                return
            value, self._cursor = parsed
            if not isinstance(value, str) or not value.strip():
                self._mode = "invalid"
                return
            self._on_message(value.strip())
            self._sent += 1


def stream_events(response):
    """解析 chat completions 的 SSE ``data:`` 行。"""
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning(f"[AI Chat] 忽略无法解析的流式事件: {payload[:160]!r}")
            continue
        if isinstance(event, dict):
            yield event
