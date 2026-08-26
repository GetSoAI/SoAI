"""SoAI - Agent turn retry-message history updates [backend/features/agent/runtime/turn_loop_retry_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.internal_retry_prompt import is_internal_retry_message
from core.types.json import JSONDict
from features.agent.runtime.tool_image_relay_messages import (
    is_tool_image_relay_message,
)

__all__ = ("append_turn_retry_message",)


def append_turn_retry_message(
    *,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    assistant_text: str | None,
    retry_message: JSONDict,
) -> None:
    _append_turn_retry_message(
        message_history=message_history,
        assistant_text=assistant_text,
        retry_message=retry_message,
    )
    _append_turn_retry_message(
        message_history=boundary_source_messages,
        assistant_text=assistant_text,
        retry_message=retry_message,
    )


def _append_turn_retry_message(
    *,
    message_history: list[JSONDict],
    assistant_text: str | None,
    retry_message: JSONDict,
) -> None:
    next_retry_message = dict(retry_message)
    if is_internal_retry_message(next_retry_message):
        if assistant_text is not None and assistant_text.strip():
            message_history.append({"role": "assistant", "content": assistant_text})
        message_history.append(next_retry_message)
        return
    if assistant_text is not None and assistant_text.strip():
        message_history.append({"role": "assistant", "content": assistant_text})
        message_history.append(next_retry_message)
        return
    if (
        message_history
        and message_history[-1].get("role") == "user"
        and not is_tool_image_relay_message(message_history[-1])
        and next_retry_message.get("role") == "user"
    ):
        last_user = dict(message_history[-1])
        last_content = last_user.get("content")
        retry_content = next_retry_message.get("content")
        if isinstance(last_content, str) and isinstance(retry_content, str):
            merged = last_content.rstrip()
            suffix = retry_content.strip()
            last_user["content"] = f"{merged}\n\n{suffix}" if merged else suffix
            message_history[-1] = last_user
            return
        if isinstance(last_content, list):
            next_parts = list(last_content)
            if isinstance(retry_content, str) and retry_content.strip():
                next_parts.append({"type": "text", "text": retry_content})
            elif isinstance(retry_content, list):
                next_parts.extend(retry_content)
            last_user["content"] = next_parts
            message_history[-1] = last_user
            return
    message_history.append(next_retry_message)
