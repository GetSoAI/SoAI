"""SoAI - Agent context compaction history slicing [backend/features/agent/runtime/context_compaction/history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.chat_role_sets import OPENAI_PINNED_ROLES
from features.agent.runtime.tool_image_relay_messages import (
    is_tool_image_relay_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "combine_compaction_buckets",
    "count_tool_blocks",
    "is_assistant_tool_call_message",
    "resolve_preserved_user_index",
    "split_after_anchor_for_compaction",
    "split_compaction_buckets",
    "take_oldest_compaction_unit",
)

_PINNED_ROLES: frozenset[str] = OPENAI_PINNED_ROLES


def is_assistant_tool_call_message(message: JSONDict) -> bool:
    if message.get("role") != "assistant":
        return False
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return False
    return any(isinstance(item, dict) for item in tool_calls)


def resolve_preserved_user_index(message_history: list[JSONDict]) -> int | None:
    preserved_index: int | None = None
    for index, message in enumerate(message_history):
        role = message.get("role")
        if isinstance(role, str) and role == "user" and not is_tool_image_relay_message(message):
            preserved_index = index
    return preserved_index


def _advance_tool_block_end(message_history: list[JSONDict], start_index: int) -> int:
    index = start_index + 1
    while index < len(message_history):
        candidate = message_history[index]
        if candidate.get("role") != "tool":
            break
        index += 1
    if index < len(message_history) and is_tool_image_relay_message(message_history[index]):
        index += 1
    return index


def split_compaction_buckets(
    message_history: list[JSONDict],
) -> tuple[list[JSONDict], list[JSONDict], JSONDict | None, list[JSONDict]]:
    pinned_prefix: list[JSONDict] = []
    before_anchor: list[JSONDict] = []
    anchor_message: JSONDict | None = None
    after_anchor: list[JSONDict] = []
    preserved_user_index = resolve_preserved_user_index(message_history)
    for index, message in enumerate(message_history):
        role = message.get("role")
        if isinstance(role, str) and role in _PINNED_ROLES:
            pinned_prefix.append(message)
            continue
        if preserved_user_index is not None and index == preserved_user_index:
            anchor_message = message
            continue
        if preserved_user_index is not None and index < preserved_user_index:
            before_anchor.append(message)
            continue
        after_anchor.append(message)
    return pinned_prefix, before_anchor, anchor_message, after_anchor


def combine_compaction_buckets(
    pinned_prefix: list[JSONDict],
    before_anchor: list[JSONDict],
    anchor_message: JSONDict | None,
    after_anchor: list[JSONDict],
    *,
    summary_message: JSONDict | None = None,
) -> list[JSONDict]:
    combined = list(pinned_prefix)
    if summary_message is not None:
        combined.append(summary_message)
    combined.extend(before_anchor)
    if anchor_message is not None:
        combined.append(anchor_message)
    combined.extend(after_anchor)
    return combined


def count_tool_blocks(message_history: list[JSONDict]) -> int:
    blocks = 0
    index = 0
    while index < len(message_history):
        message = message_history[index]
        if is_assistant_tool_call_message(message):
            blocks += 1
            index = _advance_tool_block_end(message_history, index)
            continue
        index += 1
    return blocks


def split_after_anchor_for_compaction(
    after_anchor: list[JSONDict],
    *,
    preserve_tool_blocks: int,
) -> tuple[list[JSONDict], list[JSONDict]]:
    if count_tool_blocks(after_anchor) == 0:
        return list(after_anchor), []
    if preserve_tool_blocks <= 0:
        return list(after_anchor), []
    blocks_seen = 0
    split_index = len(after_anchor)
    index = len(after_anchor) - 1
    while index >= 0:
        message = after_anchor[index]
        if is_tool_image_relay_message(message):
            index -= 1
            continue
        if message.get("role") == "tool":
            while index >= 0:
                candidate = after_anchor[index]
                if candidate.get("role") != "tool":
                    break
                index -= 1
            if index >= 0 and is_assistant_tool_call_message(after_anchor[index]):
                blocks_seen += 1
                split_index = index
                if blocks_seen >= preserve_tool_blocks:
                    break
            continue
        if is_assistant_tool_call_message(message):
            blocks_seen += 1
            split_index = index
            if blocks_seen >= preserve_tool_blocks:
                break
        index -= 1
    if blocks_seen < preserve_tool_blocks:
        return [], list(after_anchor)
    return list(after_anchor[:split_index]), list(after_anchor[split_index:])


def take_oldest_compaction_unit(messages: list[JSONDict]) -> tuple[list[JSONDict], list[JSONDict]]:
    if not messages:
        return [], []
    first = messages[0]
    if is_tool_image_relay_message(first):
        return [first], list(messages[1:])
    if first.get("role") == "user":
        cursor = 1
        if cursor >= len(messages):
            return [first], []
        second = messages[cursor]
        if is_assistant_tool_call_message(second):
            cursor = _advance_tool_block_end(messages, cursor)
            if cursor < len(messages):
                next_message = messages[cursor]
                if next_message.get("role") == "assistant" and not is_assistant_tool_call_message(
                    next_message,
                ):
                    cursor += 1
            return list(messages[:cursor]), list(messages[cursor:])
        if second.get("role") == "assistant":
            return list(messages[:2]), list(messages[2:])
        if second.get("role") == "tool":
            cursor += 1
            while cursor < len(messages):
                candidate = messages[cursor]
                if candidate.get("role") != "tool":
                    break
                cursor += 1
            if cursor < len(messages) and is_tool_image_relay_message(messages[cursor]):
                cursor += 1
            return list(messages[:cursor]), list(messages[cursor:])
        return [first], list(messages[1:])
    if first.get("role") == "tool":
        cursor = 1
        while cursor < len(messages):
            message = messages[cursor]
            if message.get("role") != "tool":
                break
            cursor += 1
        if cursor < len(messages) and is_tool_image_relay_message(messages[cursor]):
            cursor += 1
        return list(messages[:cursor]), list(messages[cursor:])
    if is_assistant_tool_call_message(first):
        cursor = _advance_tool_block_end(messages, 0)
        return list(messages[:cursor]), list(messages[cursor:])
    return [first], list(messages[1:])
