"""SoAI - Canonical conversation timeline session construction [backend/features/chat/conversation_timeline_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.websocket_chat_stream.status_preview import (
    build_ws_chat_stream_status_preview_executor,
)
from features.assistant_timeline.assistant_timeline_session import (
    AssistantTimelineSession,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("create_assistant_timeline_session",)


def create_assistant_timeline_session(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    collect_tool_calls: bool,
    status_preview_enabled: bool,
) -> AssistantTimelineSession:
    runtime.agent_tool_events_authoritative = collect_tool_calls
    status_preview_executor = (
        build_ws_chat_stream_status_preview_executor() if status_preview_enabled else None
    )
    return AssistantTimelineSession(
        runtime=runtime,
        event_bus=api_dependencies.event_bus,
        database_messages=api_dependencies.database_messages,
        database_tool_calls=api_dependencies.database_tool_calls,
        task_registry=api_dependencies.task_registry,
        task_registry_queries=api_dependencies.task_registry_queries,
        track_background_task=api_dependencies.application_control.track_background_task,
        prompt_token_counter=api_dependencies.prompt_token_counter,
        status_preview_executor=status_preview_executor,
        collect_tool_calls=collect_tool_calls,
    )
