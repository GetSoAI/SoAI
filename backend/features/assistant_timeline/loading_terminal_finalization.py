"""SoAI - Assistant timeline loading terminal finalization [backend/features/assistant_timeline/loading_terminal_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.assistant_terminal_finalization import (
    TerminalAssistantMessageFinalization,
)
from features.assistant_timeline.loading_activity_payloads import (
    build_loading_activity_event_payload,
    sync_runtime_event_sequence_with_database,
)
from features.assistant_timeline.publish import (
    flush_chat_stream_event_persistence,
    publish_chat_stream_event,
)
from features.assistant_timeline.terminal_event_publication import (
    persist_and_publish_terminal_chat_stream_event,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "publish_loading_activity_event",
    "publish_loading_terminal_events",
)


async def publish_loading_activity_event(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseMessagesProtocol,
    loading_activity: JSONDict,
) -> None:
    await publish_chat_stream_event(
        event_bus,
        runtime,
        database_messages,
        event_type="loading_activity",
        payload=build_loading_activity_event_payload(
            runtime=runtime,
            loading_activity=loading_activity,
        ),
    )


async def publish_loading_terminal_events(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseMessagesProtocol,
    loading_activity: JSONDict,
    terminal_event_type: str,
    terminal_payload: JSONDict,
    finalization: TerminalAssistantMessageFinalization,
) -> None:
    await flush_chat_stream_event_persistence(runtime, database_messages, force=True)
    await sync_runtime_event_sequence_with_database(
        runtime=runtime,
        database_messages=database_messages,
    )
    await publish_loading_activity_event(
        runtime=runtime,
        event_bus=event_bus,
        database_messages=database_messages,
        loading_activity=loading_activity,
    )
    await persist_and_publish_terminal_chat_stream_event(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
        event_type=terminal_event_type,
        payload=terminal_payload,
        finalization=finalization,
    )
