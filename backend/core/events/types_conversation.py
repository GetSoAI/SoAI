"""SoAI - Conversation and chat stream event types [backend/core/events/types_conversation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_base import Event, EventDelivery

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ChatStreamActivityChangedEvent",
    "ChatStreamEvent",
    "ChatStreamStatusPreviewEvent",
    "ConversationAttachmentChangedEvent",
    "ConversationCreatedEvent",
    "ConversationDeletedEvent",
    "ConversationDraftChangedEvent",
    "ConversationUpdatedEvent",
    "KnowledgeAttachmentChangedEvent",
    "MessageSavedEvent",
    "ModelTestStreamEvent",
    "ConversationInputsChangedEvent",
    "ThinkingTailCompletedEvent",
    "ToolCallCompletedEvent",
    "ToolCallCreatedEvent",
    "ToolCallLiveUpdatedEvent",
    "ToolCallOutputDeltaEvent",
    "ToolCallStartedEvent",
)


@dataclass(slots=True)
class ChatStreamActivityChangedEvent(Event):
    user_id: int
    active_conversation_ids: list[str]


@dataclass(slots=True)
class ConversationCreatedEvent(Event):
    user_id: int
    conv_id: str
    title: str
    created_at_ms: int
    last_modified_at_ms: int
    is_favorite: bool = False
    color: str | None = None
    is_automation: bool = False
    is_messaging: bool = False
    messaging_platform: str | None = None
    messaging_account_label: str | None = None
    messaging_account_snapshot_id: str | None = None
    settings_authority: JSONDict | None = None
    is_archived: bool = False


@dataclass(slots=True)
class ConversationUpdatedEvent(Event):
    user_id: int
    conv_id: str
    last_modified_at_ms: int
    title: str | None = None
    is_favorite: bool | None = None
    color: str | None = None
    color_present: bool = False
    model_settings: JSONDict | None = None
    is_archived: bool | None = None
    settings_authority_changed: bool = False


@dataclass(slots=True)
class ConversationDeletedEvent(Event):
    user_id: int
    conv_id: str


@dataclass(slots=True)
class ConversationDraftChangedEvent(Event):
    user_id: int
    conv_id: str
    client_id: str
    updated_at_ms: int
    deleted: bool
    revision: int


@dataclass(slots=True)
class MessageSavedEvent(Event):
    user_id: int
    conv_id: str
    message_count: int
    last_modified_at_ms: int
    message: JSONDict | None = None


@dataclass(slots=True)
class ConversationInputsChangedEvent(Event):
    user_id: int
    conv_id: str
    active_count: int
    last_modified_at_ms: int


@dataclass(slots=True)
class ConversationAttachmentChangedEvent(Event):
    user_id: int
    conv_id: str
    attachment_id: str
    client_attachment_id: str | None
    parse_state: str
    state: str
    attachment_revision: int
    updated_at_ms: int
    attachment: JSONDict


@dataclass(slots=True)
class KnowledgeAttachmentChangedEvent(Event):
    user_id: int
    conv_id: str
    knowledge_attachment_id: str
    task_id: str | None
    processing_state: str
    state: str
    attachment_revision: int
    updated_at_ms: int
    summary: JSONDict


@dataclass(slots=True)
class ToolCallCreatedEvent(Event):
    user_id: int
    conv_id: str
    call_id: str
    tool_name: str
    message_index: int
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None = None
    tool_arguments: str | None = None
    turn_id: str | None = None
    iteration_index: int | None = None


@dataclass(slots=True)
class ToolCallStartedEvent(Event):
    user_id: int
    conv_id: str
    call_id: str
    tool_name: str
    message_index: int
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None = None
    started_at_ms: int | None = None
    tool_arguments: str | None = None
    turn_id: str | None = None
    iteration_index: int | None = None


@dataclass(slots=True)
class ToolCallCompletedEvent(Event):
    user_id: int
    conv_id: str
    call_id: str
    tool_name: str
    status: str
    message_index: int
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None = None
    tool_arguments: str | None = None
    result: JSONValue | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    code_diffs: list[JSONDict] | None = None
    turn_id: str | None = None
    iteration_index: int | None = None


@dataclass(slots=True)
class ToolCallOutputDeltaEvent(Event):
    user_id: int
    conv_id: str
    message_index: int
    call_id: str
    tool_name: str
    delta: str
    turn_id: str | None = None
    iteration_index: int | None = None
    delivery: EventDelivery = EventDelivery.DROPPABLE


@dataclass(slots=True)
class ToolCallLiveUpdatedEvent(Event):
    user_id: int
    conv_id: str
    request_id: str | None
    assistant_at_ms: int
    assistant_turn_at_ms: int
    model_variant_index: int
    call_id: str
    live_sequence: int
    live_revision: int
    last_live_event_at_ms: int
    event_type: str
    tool: JSONDict
    delivery: EventDelivery = EventDelivery.DROPPABLE


@dataclass(slots=True)
class ThinkingTailCompletedEvent(Event):
    user_id: int
    conv_id: str
    message_index: int
    duration_ms: int


@dataclass(slots=True)
class ChatStreamEvent(Event):
    user_id: int
    conv_id: str
    request_id: str
    sequence: int
    event_type: str
    payload: JSONDict


@dataclass(slots=True)
class ChatStreamStatusPreviewEvent(Event):
    user_id: int
    conv_id: str
    request_id: str
    assistant_at_ms: int
    preview_key: str
    preview_args: JSONDict | None
    generated_at_ms: int
    preview_cooldown_ms: int
    trigger: str
    delivery: EventDelivery = EventDelivery.DROPPABLE


@dataclass(slots=True)
class ModelTestStreamEvent(Event):
    user_id: int
    run_id: str
    sequence: int
    event_type: str
    payload: JSONDict
