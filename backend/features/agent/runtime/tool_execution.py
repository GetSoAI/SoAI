"""SoAI - Agent tool execution and events [backend/features/agent/runtime/tool_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.timing.epoch import epoch_ms
from core.tool_calls.conversation_stop_signal import (
    STOP_CONVERSATION_TOOL_NAME,
    is_stop_conversation_signal,
)
from core.tool_calls.protocols import ToolCallProcessingProtocol
from core.tool_calls.visibility import should_persist_visible_tool_call_rows
from features.agent.runtime.tool_approval_denial_events import (
    build_user_denied_tool_call_result_payload,
    publish_user_denied_tool_call_events,
)
from features.agent.runtime.tool_approval_gate import resolve_tool_approval_decision
from features.agent.runtime.tool_call_execution_support import (
    AgentToolCallExecutionOutcome,
    AgentToolCallPostprocessContext,
    AgentToolCallPostprocessResult,
    serialize_tool_arguments_for_event,
)
from features.agent.runtime.tool_call_projection_persistence import (
    persist_cancelled_visible_tool_call_projection,
    persist_error_visible_tool_call_projection,
    persist_pending_visible_tool_call_projection,
    persist_user_denied_visible_tool_call,
)
from features.agent.runtime.tool_execution_single_call import (
    execute_single_tool_call_with_agent_events,
)
from features.agent.runtime.tool_execution_steer_interrupt import (
    AgentTurnInterruptedBySteer,
    should_interrupt_turn_for_steer,
)
from features.agent.runtime.tool_execution_tool_approval_context import (
    ToolApprovalContext,
    resolve_tool_approval_context,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversation_inputs import (
        DatabaseConversationInputsProtocol,
    )
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.tasks.protocols import CancellationHistoryProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict
    from core.users.protocols_database import DatabaseUsersProtocol

__all__ = ("execute_tool_calls_with_agent_events",)

OPERATION_TOOL_APPROVAL_WAIT = "agent.tool_execution.tool_approval_wait"


async def execute_tool_calls_with_agent_events(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call_processor: ToolCallProcessingProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry: TaskRegistryProtocol | None = None,
    database_notifications: DatabaseNotificationsProtocol,
    conversation_attention: ConversationAttentionCoordinatorProtocol,
    database_input_queue: DatabaseConversationInputsProtocol,
    database_users: DatabaseUsersProtocol | None = None,
    raw_tool_calls: list[JSONDict],
    message_index: int,
    logger: LoggerProtocol,
    cancellation_history: CancellationHistoryProtocol | None,
    cancellation_id: str,
    turn_id: str,
    iteration_index: int,
    next_action_sequence: Callable[[], Awaitable[int]],
    publish_event: Callable[[Event], Awaitable[None]],
    deadline_monotonic: float | None = None,
    persist_progress: (
        Callable[[list[JSONDict], list[AgentToolCallExecutionOutcome]], Awaitable[None]] | None
    ) = None,
    postprocess_tool_result: (
        Callable[[AgentToolCallPostprocessContext], Awaitable[AgentToolCallPostprocessResult]]
        | None
    ) = None,
) -> list[AgentToolCallExecutionOutcome]:
    iteration_request_context = clone_request_context(
        request_context,
        cancellation_id=cancellation_id,
        agent_iteration_index=iteration_index,
    )
    persist_visible_rows = should_persist_visible_tool_call_rows(iteration_request_context)
    approval_context: ToolApprovalContext | None = await resolve_tool_approval_context(
        request_context=request_context,
        tool_context=tool_context,
        task_registry=task_registry,
        database_users=database_users,
    )
    approval_task_registry: TaskRegistryProtocol | None = (
        approval_context.task_registry if approval_context is not None else None
    )
    approved_tool_permissions: set[str] | None = (
        approval_context.approved_tool_permissions if approval_context is not None else None
    )
    outcomes: list[AgentToolCallExecutionOutcome] = []
    for tool_call in raw_tool_calls:
        if cancellation_history is not None and await cancellation_history.is_cancelled(
            cancellation_id,
        ):
            raise asyncio.CancelledError()
        tool_call_id = str(tool_call.get("id") or "").strip()
        if not tool_call_id:
            tool_call_id = create_prefixed_hex_id("call")
            tool_call["id"] = tool_call_id
        tool_name = str(tool_call.get("name") or "").strip()
        tool_arguments = serialize_tool_arguments_for_event(tool_call)
        started_at_ms = int(epoch_ms())
        started_at_monotonic = time.monotonic()
        tool_call["started_at_ms"] = started_at_ms
        tool_call.pop("duration_ms", None)
        approval_projection_persisted = False
        if approval_task_registry is not None and persist_visible_rows:
            await uncancel_then_cleanup(
                persist_pending_visible_tool_call_projection(
                    database_tool_calls=database_tool_calls,
                    request_context=iteration_request_context,
                    tool_context=tool_context,
                    tool_call=tool_call,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments,
                    created_at_ms=started_at_ms,
                ),
            )
            approval_projection_persisted = True
        approved: bool | None = True
        try:
            if persist_progress is not None:
                await persist_progress(raw_tool_calls, outcomes)
            if approval_task_registry is not None:
                approved = await resolve_tool_approval_decision(
                    request_context=request_context,
                    tool_context=tool_context,
                    task_registry=approval_task_registry,
                    database_notifications=database_notifications,
                    conversation_attention=conversation_attention,
                    cancellation_history=cancellation_history,
                    cancellation_id=cancellation_id,
                    logger=logger,
                    turn_id=turn_id,
                    iteration_index=iteration_index,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments,
                    approved_tool_permissions=approved_tool_permissions,
                )
            if approved is None:
                raise asyncio.CancelledError()
        except asyncio.CancelledError:
            if approval_projection_persisted:
                await uncancel_then_cleanup(
                    persist_cancelled_visible_tool_call_projection(
                        database_tool_calls=database_tool_calls,
                        request_context=iteration_request_context,
                        tool_context=tool_context,
                        tool_call=tool_call,
                        error_message="Tool approval cancelled.",
                    ),
                )
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if approval_projection_persisted:
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_TOOL_APPROVAL_WAIT,
                )
                await uncancel_then_cleanup(
                    persist_error_visible_tool_call_projection(
                        database_tool_calls=database_tool_calls,
                        request_context=iteration_request_context,
                        tool_context=tool_context,
                        tool_call=tool_call,
                        error_message=coerced.message,
                    ),
                )
            raise
        if approved is False:
            denied_payload = build_user_denied_tool_call_result_payload()
            if persist_visible_rows:
                await uncancel_then_cleanup(
                    persist_user_denied_visible_tool_call(
                        database_tool_calls=database_tool_calls,
                        request_context=iteration_request_context,
                        tool_context=tool_context,
                        tool_call=tool_call,
                        result_payload=denied_payload,
                    ),
                )
            await uncancel_then_cleanup(
                publish_user_denied_tool_call_events(
                    request_context=iteration_request_context,
                    tool_call=tool_call,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments,
                    user_id=int(tool_context.user_id),
                    conv_id=str(tool_context.conv_id),
                    message_index=message_index,
                    result_payload=denied_payload,
                    publish_event=publish_event,
                ),
            )
            outcomes.append(
                AgentToolCallExecutionOutcome(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments,
                    started_at_ms=started_at_ms,
                    duration_ms=0,
                    result_payload=denied_payload,
                    code_diffs=None,
                ),
            )
            tool_call["duration_ms"] = 0
            if persist_progress is not None:
                await persist_progress(raw_tool_calls, outcomes)
            continue
        tool_outcome = await execute_single_tool_call_with_agent_events(
            request_context=iteration_request_context,
            tool_context=tool_context,
            tool_call_processor=tool_call_processor,
            tool_call=tool_call,
            message_index=message_index,
            logger=logger,
            started_at_ms=started_at_ms,
            started_at_monotonic=started_at_monotonic,
            turn_id=turn_id,
            iteration_index=iteration_index,
            user_id=int(tool_context.user_id),
            conv_id=str(tool_context.conv_id),
            tool_arguments=tool_arguments,
            next_action_sequence=next_action_sequence,
            publish_event=publish_event,
            deadline_monotonic=deadline_monotonic,
            postprocess_tool_result=postprocess_tool_result,
        )
        outcomes.append(tool_outcome)
        tool_call["duration_ms"] = tool_outcome.duration_ms
        if persist_progress is not None:
            await persist_progress(raw_tool_calls, outcomes)
        if tool_name == STOP_CONVERSATION_TOOL_NAME and is_stop_conversation_signal(
            tool_outcome.result_payload,
        ):
            break
        if await should_interrupt_turn_for_steer(
            database_input_queue=database_input_queue,
            tool_context=tool_context,
        ):
            raise AgentTurnInterruptedBySteer(len(outcomes))
    return outcomes
