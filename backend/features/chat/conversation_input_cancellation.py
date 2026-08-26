"""SoAI - Active durable conversation input cancellation [backend/features/chat/conversation_input_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.runtime.cancellation_ids import build_chat_stream_task_cancellation_id
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import create_system_id
from core.tasks.cancellation_scope import (
    publish_and_verify_cancellation_scope_noncritical,
)
from core.tasks.task_cancellation import cancel
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.chat.conversation_stream_cancellation import (
    cancel_conversation_stream_runtime,
    mark_conversation_stream_runtime_cancellation_requested,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "cancel_active_conversation_input",
    "prepare_forced_steers_before_cancellation",
)

LOGGER_NAME = "SoAI.features.chat.conversation_input_cancellation"


async def prepare_forced_steers_before_cancellation(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    conv_id: str,
    request_id: str | None = None,
    agent_turn_id: str | None = None,
) -> bool:
    result = await api_dependencies.database_input_queue.force_pending_steers(
        conv_id=conv_id,
        user_id=user_id,
        request_id=request_id,
        agent_turn_id=agent_turn_id,
    )
    if result.get("created") is not True:
        return False
    await publish_current_input_queue_changed(
        api_dependencies=api_dependencies,
        user_id=user_id,
        conv_id=conv_id,
    )
    return True


async def _publish_persisted_input_cancellation(
    api_dependencies: ApiDependencies,
    *,
    context: RequestContext,
    conv_id: str,
    user_id: int,
    input_id: str,
    reason: str,
) -> bool:
    active_inputs = await api_dependencies.database_input_queue.list_active_inputs(
        conv_id=conv_id,
        user_id=user_id,
    )
    matches = [item for item in active_inputs if item.get("input_id") == input_id]
    if len(matches) != 1:
        return False
    request_id = coerce_optional_trimmed_str(matches[0].get("request_id"))
    if request_id is None:
        return False
    cancellation_id = build_chat_stream_task_cancellation_id(
        context_cancellation_id=create_system_id(
            subsystem="conversation_input",
            owner=input_id,
            include_random_suffix=False,
        ),
        request_id=request_id,
    )
    cancellation_published = await publish_and_verify_cancellation_scope_noncritical(
        event_bus=api_dependencies.event_bus,
        cancellation_coordinator=api_dependencies.cancellation_coordinator,
        cancellation_history=api_dependencies.cancellation_history,
        context=context,
        reason=reason,
        cancellation_id=cancellation_id,
        logger=get_logger(LOGGER_NAME),
        publish_message="Failed to publish persisted conversation input cancellation.",
        verify_message="Failed to verify persisted conversation input cancellation.",
        level="warning",
        details={"conv_id": conv_id, "input_id": input_id},
    )
    if not cancellation_published:
        return False
    task_id = coerce_optional_trimmed_str(matches[0].get("task_id"))
    if task_id is not None:
        await cancel(
            api_dependencies.task_registry,
            task_id,
            reason=reason,
            context=context,
        )
    return True


async def cancel_active_conversation_input(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    conv_id: str,
    input_id: str,
    reason: str,
) -> bool:
    runtime = await api_dependencies.chat_stream_registry.get(
        user_id=user_id,
        conv_id=conv_id,
    )
    trace_id = create_system_id(
        subsystem="conversation_input_cancel",
        owner=input_id,
        include_random_suffix=False,
    )
    context = RequestContext(
        trace_id=trace_id,
        client_ip="internal",
        user_id=user_id,
        task_id=input_id,
        cancellation_id=trace_id,
    )
    if runtime is None:
        return await _publish_persisted_input_cancellation(
            api_dependencies,
            context=context,
            conv_id=conv_id,
            user_id=user_id,
            input_id=input_id,
            reason=reason,
        )
    input_finalization = runtime.input_finalization
    if input_finalization is None or input_finalization.input_id != input_id:
        return False
    mark_conversation_stream_runtime_cancellation_requested(runtime, reason)
    await cancel_conversation_stream_runtime(
        api_dependencies=api_dependencies,
        context=context,
        runtime=runtime,
        reason=reason,
    )
    return True
