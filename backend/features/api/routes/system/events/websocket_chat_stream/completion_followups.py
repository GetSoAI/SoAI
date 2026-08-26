"""SoAI - WebSocket chat stream completion follow-ups [backend/features/api/routes/system/events/websocket_chat_stream/completion_followups.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.enums import TaskStatus
from features.api.conversation_auto_title.service import (
    spawn_auto_title_generation_if_needed,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "handle_non_agent_stream_completion_followups",
    "track_auto_title_generation",
)


def track_auto_title_generation(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    task_name: str,
) -> None:
    auto_title_task = spawn_tracked_task(
        spawn_auto_title_generation_if_needed(
            api_dependencies=api_dependencies,
            runtime=runtime,
            completion_succeeded=True,
        ),
        name=task_name,
        cancellation_binder=api_dependencies.task_cancellation_binder,
        cancellation_id=create_system_id(
            subsystem="conversation_auto_title",
            owner=runtime.conv_id,
            include_random_suffix=True,
        ),
        owner="conversation_auto_title",
        finalizer_tracker=api_dependencies.task_finalizer_tracker,
    )
    api_dependencies.application_control.track_background_task(auto_title_task)


async def handle_non_agent_stream_completion_followups(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    task_id: str,
) -> None:
    refreshed_task = await api_dependencies.task_registry.get(
        task_id,
        force_refresh=True,
    )
    if refreshed_task is None or refreshed_task.status != TaskStatus.COMPLETED:
        return
    track_auto_title_generation(
        api_dependencies=api_dependencies,
        runtime=runtime,
        task_name=f"ws-auto-title-{runtime.conv_id}",
    )
