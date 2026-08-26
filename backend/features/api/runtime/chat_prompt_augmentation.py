"""SoAI - WebUI chat prompt augmentation helpers [backend/features/api/runtime/chat_prompt_augmentation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.content_text_coercion import coerce_openai_content_text
from features.api.runtime.content_preview_feedback import (
    build_content_preview_feedback_system_message,
)
from features.api.runtime.preview_contract_capability_message import (
    build_preview_contract_capability_system_message,
)
from features.api.runtime.preview_contract_feedback import (
    build_preview_contract_feedback_system_message,
)
from features.api.runtime.preview_contract_persisted_feedback import (
    resolve_latest_persisted_preview_contract_feedback,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.content_preview_feedback import ContentPreviewFeedback
    from features.api.runtime.preview_contract_persisted_feedback import (
        PreviewContractFeedback,
    )

__all__ = (
    "build_webui_chat_extra_system_messages",
    "extract_latest_user_message_excerpt",
    "request_requires_preview_contract",
)

_PREVIEW_CONTRACT_REQUIREMENT_TAG = "<soai_preview_contract>"


def request_requires_preview_contract(request_json: JSONDict) -> bool:
    messages_value = request_json.get("messages")
    if not isinstance(messages_value, list):
        return False
    for entry in messages_value:
        if not isinstance(entry, dict):
            continue
        if entry.get("role") != "system":
            continue
        content_value = entry.get("content")
        content = content_value.strip() if isinstance(content_value, str) else ""
        if content.startswith(_PREVIEW_CONTRACT_REQUIREMENT_TAG):
            return True
    return False


def extract_latest_user_message_excerpt(request_json: JSONDict) -> str:
    messages_value = request_json.get("messages")
    if not isinstance(messages_value, list):
        return ""
    for entry in reversed(messages_value):
        if not isinstance(entry, dict):
            continue
        if entry.get("role") != "user":
            continue
        text = coerce_openai_content_text(entry.get("content")).strip()
        if not text:
            return ""
        return text[:2048]
    return ""


def build_webui_chat_extra_system_messages(
    *,
    persisted_messages: list[JSONDict],
    content_preview_feedback: ContentPreviewFeedback | None,
    preview_contract_feedback: PreviewContractFeedback | None,
    assistant_turn_at_ms: int,
) -> tuple[str, ...]:
    system_messages: list[str] = []
    system_messages.append(build_preview_contract_capability_system_message())
    if content_preview_feedback is not None:
        system_message = build_content_preview_feedback_system_message(content_preview_feedback)
        if isinstance(system_message, str) and system_message.strip():
            system_messages.append(system_message)
    resolved_preview_contract_feedback = (
        preview_contract_feedback
        if preview_contract_feedback is not None
        else resolve_latest_persisted_preview_contract_feedback(
            messages=persisted_messages,
            before_timestamp_exclusive=assistant_turn_at_ms,
        )
    )
    if resolved_preview_contract_feedback is not None:
        system_message = build_preview_contract_feedback_system_message(
            resolved_preview_contract_feedback,
        )
        if isinstance(system_message, str) and system_message.strip():
            system_messages.append(system_message)
    return tuple(system_messages)
