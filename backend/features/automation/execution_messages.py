"""SoAI - Automation conversation and message persistence [backend/features/automation/execution_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.assistant_turn_variant_identity import (
    AssistantTurnVariantIdentity,
)
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.timing.epoch import epoch_ms
from features.assistant_timeline.assistant_placeholder_publication import (
    persist_streaming_assistant_placeholder,
)
from features.assistant_timeline.message_write_versions import (
    require_assistant_timeline_message_write,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.runtime_construction import create_chat_stream_runtime
from features.automation.events import publish_automation_conversation_message_events
from features.automation.execution_stream_lifecycle import (
    cleanup_failed_automation_stream_reservation,
    register_automation_stream_runtime,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "AutomationConversationSession",
    "ReservedAutomationAssistantMessage",
    "append_turn_user_message",
    "commit_turn_assistant_message",
    "create_automation_conversation",
    "reserve_turn_assistant_message",
)


@dataclass(slots=True)
class AutomationConversationSession:
    conv_id: str
    user_id: int
    conversation_record: JSONDict
    message_count: int = 0
    last_timestamp: int | None = None


@dataclass(frozen=True, slots=True)
class ReservedAutomationAssistantMessage:
    runtime: AssistantTimelineRuntime


def _next_message_timestamp(last_timestamp: int | None) -> int:
    now_ms = epoch_ms()
    if last_timestamp is None:
        return now_ms
    return max(now_ms, last_timestamp + 1)


async def _ensure_session_state(
    api_dependencies: ApiDependencies,
    session: AutomationConversationSession,
) -> None:
    if session.message_count > 0 and session.last_timestamp is not None:
        return
    latest_timestamp = await api_dependencies.database_messages.get_latest_message_timestamp(
        session.conv_id,
        session.user_id,
    )
    if latest_timestamp is not None:
        session.last_timestamp = int(latest_timestamp)
    message_count = await api_dependencies.database_messages.count_messages(
        session.conv_id,
        session.user_id,
    )
    if message_count is None:
        raise StateError("Automation conversation message state is unavailable.")
    session.message_count = int(message_count)


async def create_automation_conversation(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    title: str,
    model_settings: JSONDict,
) -> AutomationConversationSession:
    conversation_record = await api_dependencies.database_conversations.create_conversation(
        user_id,
        title,
        model_settings,
        True,
    )
    conv_id_value = conversation_record.get("id")
    if not isinstance(conv_id_value, str) or not conv_id_value.strip():
        raise StateError("Automation conversation id is invalid.")
    return AutomationConversationSession(
        conv_id=conv_id_value.strip(),
        user_id=user_id,
        conversation_record=dict(conversation_record),
    )


async def append_turn_user_message(
    api_dependencies: ApiDependencies,
    session: AutomationConversationSession,
    *,
    content: str,
) -> None:
    await _ensure_session_state(api_dependencies, session)
    timestamp = _next_message_timestamp(session.last_timestamp)
    write_result = await api_dependencies.database_messages.append_messages(
        session.conv_id,
        session.user_id,
        [{"role": "user", "timestamp": timestamp, "content": content}],
    )
    session.last_timestamp = timestamp
    session.message_count = write_result.message_count
    await publish_automation_conversation_message_events(
        api_dependencies.event_bus,
        user_id=session.user_id,
        conv_id=session.conv_id,
        message_count=session.message_count,
        last_modified_at_ms=write_result.last_modified_at_ms,
    )


async def reserve_turn_assistant_message(
    api_dependencies: ApiDependencies,
    session: AutomationConversationSession,
    *,
    model_id: str | None,
    request_id: str,
    task_cancellation_id: str,
) -> ReservedAutomationAssistantMessage:
    await _ensure_session_state(api_dependencies, session)
    assistant_at_ms = _next_message_timestamp(session.last_timestamp)
    runtime = _build_reserved_runtime(
        session,
        assistant_at_ms=assistant_at_ms,
        model_id=model_id,
        request_id=request_id,
        task_cancellation_id=task_cancellation_id,
    )
    await register_automation_stream_runtime(api_dependencies, runtime)
    try:
        await persist_streaming_assistant_placeholder(
            database_messages=api_dependencies.database_messages,
            runtime=runtime,
        )
    except asyncio.CancelledError:
        await cleanup_failed_automation_stream_reservation(api_dependencies, runtime)
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await cleanup_failed_automation_stream_reservation(api_dependencies, runtime)
        raise
    if runtime.latest_message_write_count is None:
        await cleanup_failed_automation_stream_reservation(api_dependencies, runtime)
        raise StateError("Automation assistant placeholder reservation failed.")
    try:
        session.message_count = require_assistant_timeline_message_write(runtime).message_count
    except StateError:
        await cleanup_failed_automation_stream_reservation(api_dependencies, runtime)
        raise
    session.last_timestamp = assistant_at_ms
    return ReservedAutomationAssistantMessage(
        runtime=runtime,
    )


async def commit_turn_assistant_message(
    api_dependencies: ApiDependencies,
    session: AutomationConversationSession,
    *,
    assistant_at_ms: int,
) -> None:
    _ = api_dependencies
    session.last_timestamp = assistant_at_ms


def _build_reserved_runtime(
    session: AutomationConversationSession,
    *,
    assistant_at_ms: int,
    model_id: str | None,
    request_id: str,
    task_cancellation_id: str,
) -> AssistantTimelineRuntime:
    return create_chat_stream_runtime(
        conv_id=session.conv_id,
        request_id=request_id,
        identity=AssistantTurnVariantIdentity(
            assistant_at_ms=assistant_at_ms,
            assistant_turn_at_ms=assistant_at_ms,
            model_variant_index=0,
        ),
        user_id=session.user_id,
        message_index=session.message_count,
        model_id=model_id,
        task_cancellation_id=task_cancellation_id,
    )
