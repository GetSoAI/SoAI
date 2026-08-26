"""SoAI - WebUI conversation message storage record types [backend/core/conversations/conversation_message_storage_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NotRequired, Required, TypedDict

from core.types.json import JSONDict

__all__ = ("ConversationMessageStoragePayload",)


class ConversationMessageStoragePayload(TypedDict):
    role: Required[str]
    message_type: Required[str]
    content_json: Required[str]
    created_at_ms: Required[int]
    assistant_turn_at_ms: NotRequired[int]
    model_variant_index: NotRequired[int]
    assistant_event_timeline: NotRequired[list[JSONDict] | None]
    tool_call_id: NotRequired[str]
    model_id: NotRequired[str]
    request_id: NotRequired[str]
    prompt_tokens: NotRequired[int]
    completion_tokens: NotRequired[int]
    total_tokens: NotRequired[int]
    usage_source: NotRequired[str]
    generation_latency_ms: NotRequired[int]
    finish_reason: NotRequired[str]
    thinking_tail_duration_ms: NotRequired[int]
