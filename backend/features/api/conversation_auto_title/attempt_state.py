"""SoAI - Auto-title attempt state loading [backend/features/api/conversation_auto_title/attempt_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.chat.conversation_defaults import read_chat_auto_title_generation_enabled
from core.conversations.default_title_resolution import (
    resolve_default_title_from_user_message,
)
from core.errors.exceptions import StateError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "AutoTitleAttemptState",
    "conversation_title_matches_default",
    "load_auto_title_attempt_state",
    "require_last_modified_at_ms",
)


@dataclass(frozen=True, slots=True)
class AutoTitleAttemptState:
    first_user_message: JSONDict
    first_assistant_message: JSONDict
    default_title: str


async def load_auto_title_attempt_state(
    *,
    api_dependencies: ApiDependencies,
    conv_id: str,
    user_id: int,
) -> AutoTitleAttemptState | None:
    preferences = await api_dependencies.database_users.get_user_preferences(user_id)
    if preferences is None:
        return None
    if not read_chat_auto_title_generation_enabled(preferences):
        return None
    conversation = await api_dependencies.database_conversations.get_conversation(conv_id, user_id)
    if conversation is None:
        return None
    if conversation.get("is_automation") is True:
        return None
    seed_messages = await api_dependencies.database_messages.get_auto_title_seed_messages(
        conv_id,
        user_id,
    )
    if seed_messages is None:
        return None
    first_user_message, first_assistant_message = seed_messages
    if first_user_message is None or first_assistant_message is None:
        return None
    default_title = resolve_default_title_from_user_message(first_user_message)
    if not conversation_title_matches_default(conversation, default_title):
        return None
    return AutoTitleAttemptState(
        first_user_message=first_user_message,
        first_assistant_message=first_assistant_message,
        default_title=default_title,
    )


def conversation_title_matches_default(
    conversation: JSONDict | None,
    default_title: str,
) -> bool:
    if conversation is None:
        return False
    title_value = conversation.get("title")
    return isinstance(title_value, str) and title_value == default_title


def require_last_modified_at_ms(record: JSONDict) -> int:
    value = record.get("last_modified_at_ms")
    if is_strict_int(value) and value > 0:
        return value
    raise StateError("Conversation last_modified_at_ms is invalid after auto-title update.")
