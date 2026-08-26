"""SoAI - User message memory block for context compaction [backend/features/agent/runtime/context_compaction/user_memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.content_text_rendering import render_openai_content_text
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable_strict,
)
from core.serialization.json_parsing import parse_json_value_or_none
from core.types.json_value import coerce_json_dict
from features.agent.runtime.context_compaction.tag_blocks import extract_tag_block_text
from features.agent.runtime.tool_image_relay_messages import (
    is_tool_image_relay_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "UserMessageMemory",
    "build_user_message_memory_message",
    "evict_one_low_priority_entry",
    "extract_user_message_memory_from_message",
    "is_user_message_memory_message",
    "merge_user_message_memory",
    "remove_user_memory_entries_present_as_user_messages",
    "render_user_message_memory_content",
    "strip_user_message_memory_messages",
)

_OPEN_TAG = "<user_message_memory>"
_CLOSE_TAG = "</user_message_memory>"
_TRUNCATED_MEMORY_SUFFIX = " […]"


@dataclass(frozen=True, slots=True)
class UserMessageMemory:
    head: tuple[str, ...]
    tail: tuple[str, ...]
    extra: tuple[str, ...]

    def is_empty(self) -> bool:
        return not (self.head or self.tail or self.extra)


def is_user_message_memory_message(message: JSONDict) -> bool:
    if message.get("role") != "system":
        return False
    content = message.get("content")
    if not isinstance(content, str) or not content:
        return False
    return _OPEN_TAG in content and _CLOSE_TAG in content


def _normalize_text_entries(value: JSONValue) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    entries: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if not normalized:
            continue
        entries.append(normalized)
    return tuple(entries)


def _coerce_memory_payload(payload: JSONValue) -> UserMessageMemory | None:
    normalized = normalize_for_json(payload)
    memory_dict = coerce_json_dict(normalized)
    if memory_dict is None:
        return None
    head = _normalize_text_entries(memory_dict.get("head"))
    tail = _normalize_text_entries(memory_dict.get("tail"))
    extra = _normalize_text_entries(memory_dict.get("extra"))
    if not (head or tail or extra):
        return None
    return UserMessageMemory(head=head, tail=tail, extra=extra)


def parse_user_message_memory_text(text: str) -> UserMessageMemory | None:
    parsed = parse_json_value_or_none(text)
    if parsed is None:
        return None
    return _coerce_memory_payload(parsed)


def extract_user_message_memory_from_message(message: JSONDict) -> UserMessageMemory | None:
    if message.get("role") != "system":
        return None
    content = message.get("content")
    if not isinstance(content, str) or not content:
        return None
    extracted = extract_tag_block_text(content, open_tag=_OPEN_TAG, close_tag=_CLOSE_TAG)
    if extracted is None:
        return None
    return parse_user_message_memory_text(extracted)


def strip_user_message_memory_messages(
    message_history: list[JSONDict],
) -> tuple[UserMessageMemory | None, list[JSONDict]]:
    merged: UserMessageMemory | None = None
    remaining: list[JSONDict] = []
    for message in message_history:
        memory = extract_user_message_memory_from_message(message)
        if memory is None:
            remaining.append(message)
            continue
        merged = merge_user_message_memory(
            merged,
            head=list(memory.head),
            tail=list(memory.tail),
            extra=list(memory.extra),
        )
    return merged, remaining


def merge_user_message_memory(
    existing: UserMessageMemory | None,
    *,
    head: list[str],
    tail: list[str],
    extra: list[str],
) -> UserMessageMemory | None:
    combined_head = list(existing.head) if existing is not None else []
    combined_tail = list(existing.tail) if existing is not None else []
    combined_extra = list(existing.extra) if existing is not None else []
    combined_head.extend(str(item or "").strip() for item in head)
    combined_tail.extend(str(item or "").strip() for item in tail)
    combined_extra.extend(str(item or "").strip() for item in extra)
    seen: set[str] = set()

    def _dedupe(items: list[str]) -> tuple[str, ...]:
        result: list[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return tuple(result)

    head_deduped = _dedupe(combined_head)
    tail_deduped = _dedupe(combined_tail)
    extra_deduped = _dedupe(combined_extra)
    memory = UserMessageMemory(head=head_deduped, tail=tail_deduped, extra=extra_deduped)
    return None if memory.is_empty() else memory


def _entry_present_in_user_messages(entry: str, present_messages: list[str]) -> bool:
    if entry in present_messages:
        return True
    if not entry.endswith(_TRUNCATED_MEMORY_SUFFIX):
        return False
    prefix = entry[: -len(_TRUNCATED_MEMORY_SUFFIX)]
    if not prefix:
        return False
    for message in present_messages:
        if message.startswith(prefix):
            return True
    return False


def remove_user_memory_entries_present_as_user_messages(
    memory: UserMessageMemory | None,
    *,
    message_history: list[JSONDict],
) -> UserMessageMemory | None:
    if memory is None:
        return None
    present_messages: list[str] = []
    for message in message_history:
        if message.get("role") != "user" or is_tool_image_relay_message(message):
            continue
        present_text = render_openai_content_text(message.get("content")).strip()
        if present_text:
            present_messages.append(present_text)
    if not present_messages:
        return memory
    head = tuple(
        item for item in memory.head if not _entry_present_in_user_messages(item, present_messages)
    )
    tail = tuple(
        item for item in memory.tail if not _entry_present_in_user_messages(item, present_messages)
    )
    extra = tuple(
        item for item in memory.extra if not _entry_present_in_user_messages(item, present_messages)
    )
    updated = UserMessageMemory(head=head, tail=tail, extra=extra)
    return None if updated.is_empty() else updated


def render_user_message_memory_content(memory: UserMessageMemory) -> str:
    payload = {
        "v": 1,
        "head": list(memory.head),
        "tail": list(memory.tail),
        "extra": list(memory.extra),
    }
    normalized = normalize_for_json(payload)
    serialized = serialize_json_compact_stable_strict(normalized, ensure_ascii=False)
    return f"{_OPEN_TAG}\n{serialized}\n{_CLOSE_TAG}"


def build_user_message_memory_message(memory: UserMessageMemory) -> JSONDict:
    if memory.is_empty():
        raise ValidationError("UserMessageMemory must not be empty.")
    return {"role": "system", "content": render_user_message_memory_content(memory)}


def evict_one_low_priority_entry(memory: UserMessageMemory) -> UserMessageMemory | None:
    head = list(memory.head)
    tail = list(memory.tail)
    extra = list(memory.extra)
    if extra:
        extra.pop()
    elif tail:
        tail.pop()
    elif head:
        head.pop()
    updated = UserMessageMemory(head=tuple(head), tail=tuple(tail), extra=tuple(extra))
    return None if updated.is_empty() else updated
