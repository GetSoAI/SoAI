"""SoAI - Shared conversation event construction and publication [backend/core/events/conversation_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_source import resolve_conversation_source_metadata
from core.conversations.settings_authority import (
    build_settings_authority_payload,
    resolve_conversation_settings_authority,
)
from core.errors.exceptions import StateError, ValidationError
from core.events.types_conversation import (
    ConversationCreatedEvent,
    ConversationUpdatedEvent,
    MessageSavedEvent,
)
from core.prompts.colors import validate_prompt_color
from core.validation.integers import is_non_negative_strict_int, is_strict_int

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import TypedDict

    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict, JSONValue

    class ConversationUpdatedEventFields(TypedDict):
        user_id: int
        conv_id: str
        last_modified_at_ms: int
        title: str | None
        is_favorite: bool | None
        color: str | None
        color_present: bool
        model_settings: JSONDict | None
        is_archived: bool | None
        settings_authority_changed: bool


__all__ = (
    "build_conversation_created_event",
    "build_conversation_updated_event",
    "build_message_saved_event",
    "publish_conversation_created",
    "publish_conversation_updated",
    "publish_conversation_updated_and_message_saved",
)


def build_conversation_created_event(
    *,
    user_id: int,
    conversation_record: Mapping[str, JSONValue],
) -> ConversationCreatedEvent:
    conv_id_value = conversation_record.get("id")
    title_value = conversation_record.get("title")
    created_at_value = conversation_record.get("created_at_ms")
    last_modified_at_value = conversation_record.get("last_modified_at_ms")
    favorite_value = conversation_record.get("is_favorite")
    color_value = conversation_record.get("color")
    is_automation_value = conversation_record.get("is_automation")
    if not isinstance(conv_id_value, str) or not conv_id_value.strip():
        raise StateError("Conversation record id is invalid.")
    if not isinstance(title_value, str) or not title_value.strip():
        raise StateError("Conversation record title is invalid.")
    if not is_strict_int(created_at_value):
        raise StateError("Conversation record created_at_ms is invalid.")
    if not is_strict_int(last_modified_at_value):
        raise StateError("Conversation record last_modified_at_ms is invalid.")
    if not isinstance(favorite_value, bool):
        raise StateError("Conversation record is_favorite is invalid.")
    if color_value is None or isinstance(color_value, str):
        resolved_color = _resolve_color(color_value, "Conversation record color is invalid.")
    else:
        raise StateError("Conversation record color is invalid.")
    if not isinstance(is_automation_value, bool):
        raise StateError("Conversation record is_automation is invalid.")
    source = resolve_conversation_source_metadata(conversation_record)
    authority = resolve_conversation_settings_authority(dict(conversation_record))
    return ConversationCreatedEvent(
        user_id=user_id,
        conv_id=conv_id_value,
        title=title_value,
        created_at_ms=created_at_value,
        last_modified_at_ms=last_modified_at_value,
        is_favorite=favorite_value,
        color=resolved_color,
        is_automation=is_automation_value,
        is_messaging=source.is_messaging,
        messaging_platform=source.messaging_platform,
        messaging_account_label=source.messaging_account_label,
        messaging_account_snapshot_id=source.messaging_account_snapshot_id,
        settings_authority=build_settings_authority_payload(authority),
        is_archived=False,
    )


def build_message_saved_event(
    *,
    user_id: int,
    conv_id: str,
    message_count: int,
    last_modified_at_ms: int,
    message: JSONDict | None = None,
) -> MessageSavedEvent:
    if not conv_id.strip():
        raise StateError("Conversation event conv_id is invalid.")
    if not is_non_negative_strict_int(message_count):
        raise StateError("Conversation event message_count is invalid.")
    return MessageSavedEvent(
        user_id=user_id,
        conv_id=conv_id.strip(),
        message_count=message_count,
        last_modified_at_ms=_resolve_last_modified_at_ms(last_modified_at_ms),
        message=message,
    )


def build_conversation_updated_event(
    *,
    user_id: int,
    conv_id: str,
    last_modified_at_ms: int,
    title: str | None = None,
    is_favorite: bool | None = None,
    color: str | None = None,
    color_present: bool = False,
    model_settings: JSONDict | None = None,
    is_archived: bool | None = None,
    settings_authority_changed: bool = False,
) -> ConversationUpdatedEvent:
    if not conv_id.strip():
        raise StateError("Conversation event conv_id is invalid.")
    if title is not None and not title.strip():
        raise StateError("Conversation event title is invalid.")
    if not color_present and color is not None:
        raise StateError("Conversation event color is invalid.")
    return ConversationUpdatedEvent(
        user_id=user_id,
        conv_id=conv_id.strip(),
        last_modified_at_ms=_resolve_last_modified_at_ms(last_modified_at_ms),
        title=title,
        is_favorite=is_favorite,
        color=(
            _resolve_color(color, "Conversation event color is invalid.") if color_present else None
        ),
        color_present=color_present,
        model_settings=model_settings,
        is_archived=is_archived,
        settings_authority_changed=settings_authority_changed,
    )


def _resolve_last_modified_at_ms(last_modified_at_ms: int | None) -> int:
    if last_modified_at_ms is None:
        raise StateError("Conversation event last_modified_at_ms is required.")
    if (
        isinstance(last_modified_at_ms, bool)
        or not isinstance(last_modified_at_ms, int)
        or last_modified_at_ms <= 0
    ):
        raise StateError("Conversation event last_modified_at_ms is invalid.")
    return last_modified_at_ms


def _resolve_color(color: str | None, error_message: str) -> str | None:
    if color is None:
        return None
    try:
        resolved_color = validate_prompt_color(color)
    except ValidationError as exception:
        raise StateError(error_message) from exception
    if resolved_color is None:
        raise StateError(error_message)
    return resolved_color


async def publish_conversation_created(
    event_bus: EventBusProtocol,
    *,
    user_id: int,
    conversation_record: Mapping[str, JSONValue],
) -> None:
    await event_bus.publish(
        build_conversation_created_event(
            user_id=user_id,
            conversation_record=conversation_record,
        ),
    )


async def publish_conversation_updated(
    event_bus: EventBusProtocol,
    *,
    user_id: int,
    conv_id: str,
    last_modified_at_ms: int,
    title: str | None = None,
    is_favorite: bool | None = None,
    color: str | None = None,
    color_present: bool = False,
    model_settings: JSONDict | None = None,
    is_archived: bool | None = None,
    settings_authority_changed: bool = False,
) -> None:
    payload: ConversationUpdatedEventFields = {
        "user_id": user_id,
        "conv_id": conv_id,
        "last_modified_at_ms": last_modified_at_ms,
        "title": title,
        "is_favorite": is_favorite,
        "color": color,
        "color_present": color_present,
        "model_settings": model_settings,
        "is_archived": is_archived,
        "settings_authority_changed": settings_authority_changed,
    }
    await event_bus.publish(build_conversation_updated_event(**payload))


async def publish_conversation_updated_and_message_saved(
    event_bus: EventBusProtocol,
    *,
    user_id: int,
    conv_id: str,
    message_count: int,
    last_modified_at_ms: int,
    message: JSONDict | None = None,
    title: str | None = None,
) -> None:
    resolved_last_modified_at = _resolve_last_modified_at_ms(last_modified_at_ms)
    await event_bus.publish(
        build_conversation_updated_event(
            user_id=user_id,
            conv_id=conv_id,
            last_modified_at_ms=resolved_last_modified_at,
            title=title,
        ),
    )
    await event_bus.publish(
        build_message_saved_event(
            user_id=user_id,
            conv_id=conv_id,
            message_count=message_count,
            last_modified_at_ms=resolved_last_modified_at,
            message=message,
        ),
    )
