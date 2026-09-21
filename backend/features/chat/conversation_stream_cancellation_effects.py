"""SoAI - Accepted Chat cancellation effects [backend/features/chat/conversation_stream_cancellation_effects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.automation.automation_identifiers import build_automation_run_cancellation_id
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.tasks.cancellation_scope import (
    publish_and_verify_cancellation_scope_noncritical,
)
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.chat.conversation_stream_cancellation import (
    cancel_conversation_stream_runtime,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from core.runtime.request_context import RequestContext
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "schedule_cancellation_input_publication",
    "schedule_captured_cancellation_cleanup",
    "schedule_runtime_cancellation",
)

CANCELLATION_EFFECT_DEADLINE_SECONDS = 4.0
LOGGER_NAME = "SoAI.features.chat.conversation_stream_cancellation_effects"


async def _run_cancellation_effect(
    operation: str,
    effect: Awaitable[bool | int | None],
) -> None:
    result = await asyncio.wait_for(effect, timeout=CANCELLATION_EFFECT_DEADLINE_SECONDS)
    if result is False:
        raise StateError(f"Accepted Chat cancellation effect was not confirmed: {operation}.")


def _raise_cancellation_effect_failure(
    results: list[None | BaseException],
) -> None:
    for result in results:
        if isinstance(result, BaseException):
            raise result


async def _cancel_automation_scope(
    *,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    cancellation_id: str,
    reason: str,
    conv_id: str,
    request_id: str,
) -> bool:
    return await publish_and_verify_cancellation_scope_noncritical(
        event_bus=api_dependencies.event_bus,
        cancellation_coordinator=api_dependencies.cancellation_coordinator,
        cancellation_history=api_dependencies.cancellation_history,
        context=context,
        reason=reason,
        cancellation_id=cancellation_id,
        logger=get_logger(LOGGER_NAME),
        publish_message="Failed to publish automation cancellation.",
        verify_message="Failed to verify automation cancellation.",
        level="warning",
        details={"conv_id": conv_id, "request_id": request_id},
    )


def schedule_cancellation_input_publication(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    conv_id: str,
    request_id: str,
) -> None:
    async def publish() -> None:
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=user_id,
            conv_id=conv_id,
        )

    task = create_ephemeral_task(publish(), name=f"chat-stream-cancel-inputs-{request_id}")
    api_dependencies.application_control.track_background_task(task)


async def schedule_runtime_cancellation(
    *,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    runtime: AssistantTimelineRuntime,
    automation_run_ids: tuple[str, ...],
    shell_sessions: tuple[tuple[int, str], ...],
    reason: str,
) -> None:
    existing_task = await api_dependencies.chat_stream_registry.cancellation_task_for(
        user_id=runtime.user_id,
        conv_id=runtime.conv_id,
        request_id=runtime.request_id,
    )
    if existing_task is not None:
        return

    async def cancel_captured_execution() -> None:
        effects: list[Awaitable[None]] = [
            _run_cancellation_effect(
                "chat.stream_cancellation.runtime",
                cancel_conversation_stream_runtime(
                    api_dependencies=api_dependencies,
                    context=context,
                    runtime=runtime,
                    reason=reason,
                ),
            ),
        ]
        effects.extend(
            _run_cancellation_effect(
                "chat.stream_cancellation.automation",
                _cancel_automation_scope(
                    api_dependencies=api_dependencies,
                    context=context,
                    cancellation_id=build_automation_run_cancellation_id(run_id),
                    reason=reason,
                    conv_id=runtime.conv_id,
                    request_id=runtime.request_id,
                ),
            )
            for run_id in automation_run_ids
        )
        effects.append(
            _run_cancellation_effect(
                "chat.stream_cancellation.shell_cleanup",
                api_dependencies.mcp_server.cancel_captured_openai_shell_sessions(
                    user_id=runtime.user_id,
                    conv_id=runtime.conv_id,
                    sessions=shell_sessions,
                ),
            ),
        )
        results = await asyncio.gather(*effects, return_exceptions=True)
        _raise_cancellation_effect_failure(results)

    task = create_ephemeral_task(
        cancel_captured_execution(),
        name=f"chat-stream-cancel-{runtime.conv_id}-{runtime.request_id}",
    )
    await api_dependencies.chat_stream_registry.record_cancellation_task(
        user_id=runtime.user_id,
        conv_id=runtime.conv_id,
        request_id=runtime.request_id,
        task=task,
    )
    api_dependencies.application_control.track_background_task(task)


async def schedule_captured_cancellation_cleanup(
    *,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    user_id: int,
    conv_id: str,
    request_id: str,
    automation_run_ids: tuple[str, ...],
    shell_sessions: tuple[tuple[int, str], ...],
    reason: str,
) -> None:
    existing_task = await api_dependencies.chat_stream_registry.cancellation_task_for(
        user_id=user_id,
        conv_id=conv_id,
        request_id=request_id,
    )
    if existing_task is not None:
        return

    async def cleanup() -> None:
        effects: list[Awaitable[None]] = [
            _run_cancellation_effect(
                "chat.stream_cancellation.automation_cleanup",
                _cancel_automation_scope(
                    api_dependencies=api_dependencies,
                    context=context,
                    cancellation_id=build_automation_run_cancellation_id(run_id),
                    reason=reason,
                    conv_id=conv_id,
                    request_id=request_id,
                ),
            )
            for run_id in automation_run_ids
        ]
        effects.append(
            _run_cancellation_effect(
                "chat.stream_cancellation.shell_cleanup",
                api_dependencies.mcp_server.cancel_captured_openai_shell_sessions(
                    user_id=user_id,
                    conv_id=conv_id,
                    sessions=shell_sessions,
                ),
            ),
        )
        results = await asyncio.gather(*effects, return_exceptions=True)
        _raise_cancellation_effect_failure(results)

    task = create_ephemeral_task(cleanup(), name=f"chat-stream-cancel-cleanup-{conv_id}")
    await api_dependencies.chat_stream_registry.record_cancellation_task(
        user_id=user_id,
        conv_id=conv_id,
        request_id=request_id,
        task=task,
    )
    api_dependencies.application_control.track_background_task(task)
