"""SoAI - Tool result prompt shaping cache [backend/core/tool_calls/tool_result_prompt_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from core.tool_calls.tool_result_prompt_primitives import safe_json_dumps
from core.tool_calls.tool_result_prompt_shaping import shape_tool_result_json_for_prompt
from core.types.json import JSONValue

__all__ = ("ToolResultPromptShapeCache",)


@dataclass(frozen=True, slots=True)
class _ToolResultPromptShapeKey:
    tool_name: str
    payload_sha256: str
    payload_chars: int
    max_chars: int
    max_depth: int
    max_items: int
    max_keys: int


@dataclass(frozen=True, slots=True)
class _ToolResultPromptShapeEntry:
    payload_json: str
    shaped_json: str


class ToolResultPromptShapeCache:
    __slots__ = ("_entries", "_max_entries")

    def __init__(self, *, max_entries: int = 512) -> None:
        self._entries: dict[_ToolResultPromptShapeKey, list[_ToolResultPromptShapeEntry]] = {}
        self._max_entries = max(1, max_entries)

    def shape(
        self,
        *,
        tool_name: str,
        tool_result: JSONValue,
        max_chars: int,
        max_depth: int,
        max_items: int,
        max_keys: int,
    ) -> str:
        payload_text = safe_json_dumps(tool_result)
        key = _ToolResultPromptShapeKey(
            tool_name=str(tool_name or "").strip(),
            payload_sha256=hashlib.sha256(
                payload_text.encode("utf-8", errors="surrogatepass"),
            ).hexdigest(),
            payload_chars=len(payload_text),
            max_chars=max_chars,
            max_depth=max_depth,
            max_items=max_items,
            max_keys=max_keys,
        )
        entries = self._entries.get(key)
        if entries is not None:
            for entry in entries:
                if entry.payload_json == payload_text:
                    return entry.shaped_json
        shaped_json, _stats = shape_tool_result_json_for_prompt(
            tool_name=tool_name,
            tool_result=tool_result,
            max_chars=max_chars,
            max_depth=max_depth,
            max_items=max_items,
            max_keys=max_keys,
        )
        if len(self._entries) >= self._max_entries:
            self._entries.clear()
        bucket = self._entries.get(key)
        if bucket is None:
            self._entries[key] = [_ToolResultPromptShapeEntry(payload_text, shaped_json)]
        else:
            bucket.append(_ToolResultPromptShapeEntry(payload_text, shaped_json))
        return shaped_json
