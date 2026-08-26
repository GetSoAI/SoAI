"""SoAI - Agent single tool-call execution [backend/features/agent/runtime/tool_execution_single_call.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.public_projection import project_public_error
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.code_diffs import normalize_code_diffs_payload
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tool_calls.protocols import ToolCallProcessingProtocol
from features.agent.events.types import AgentPlanUpdatedEvent, AgentTodoUpdatedEvent
from features.agent.runtime.tool_call_execution_support import (
    AgentToolCallExecutionOutcome,
    AgentToolCallPostprocessContext,
    AgentToolCallPostprocessResult,
    coerce_in_progress_tool_result_to_error,
)

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("execute_single_tool_call_with_agent_events",)

OPERATION_AGENT_TOOL_EXECUTION_POSTPROCESS_TOOL_RESULT = (
    "agent.tool_execution.postprocess_tool_result"
)


async def execute_single_tool_call_with_agent_events(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call_processor: ToolCallProcessingProtocol,
    tool_call: JSONDict,
    message_index: int,
    logger: LoggerProtocol,
    started_at_ms: int,
    started_at_monotonic: float,
    turn_id: str,
    iteration_index: int,
    user_id: int,
    conv_id: str,
    tool_arguments: str | None,
    next_action_sequence: Callable[[], Awaitable[int]],
    publish_event: Callable[[Event], Awaitable[None]],
    deadline_monotonic: float | None = None,
    postprocess_tool_result: (
        Callable[[AgentToolCallPostprocessContext], Awaitable[AgentToolCallPostprocessResult]]
        | None
    ) = None,
) -> AgentToolCallExecutionOutcome:
    updated_tool_context = MCPToolContext(
        conv_id=tool_context.conv_id,
        message_index=message_index,
        user_id=tool_context.user_id,
        tool_map=tool_context.tool_map,
        visible_tool_names=tool_context.visible_tool_names,
        tool_approval_required=tool_context.tool_approval_required,
        assistant_at_ms=tool_context.assistant_at_ms,
        assistant_turn_at_ms=tool_context.assistant_turn_at_ms,
        model_variant_index=tool_context.model_variant_index,
        user_interaction_timeout_ms=tool_context.user_interaction_timeout_ms,
    )
    tool_call_id = str(tool_call.get("id") or "").strip()
    tool_name = str(tool_call.get("name") or "").strip()
    result_payload: JSONValue
    single_results = await tool_call_processor.execute_tool_calls_with_events(
        request_context=request_context,
        tool_context=updated_tool_context,
        raw_tool_calls=[tool_call],
        logger=logger,
        deadline_monotonic=deadline_monotonic,
    )
    first_result = single_results[0] if single_results else None
    result_payload = coerce_in_progress_tool_result_to_error(first_result)
    code_diffs = (
        normalize_code_diffs_payload(result_payload.get("code_diffs"))
        if isinstance(result_payload, dict)
        else None
    )
    completion_sequence = await next_action_sequence()
    postprocess_result: AgentToolCallPostprocessResult | None = None
    if postprocess_tool_result is not None and isinstance(result_payload, dict):
        try:
            postprocess_result = await postprocess_tool_result(
                AgentToolCallPostprocessContext(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments,
                    completion_sequence=int(completion_sequence),
                    result_payload=dict(result_payload),
                    code_diffs=code_diffs,
                ),
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_AGENT_TOOL_EXECUTION_POSTPROCESS_TOOL_RESULT,
            )
            log_exception(
                logger,
                coerced,
                message="Tool result postprocessing failed.",
                operation=OPERATION_AGENT_TOOL_EXECUTION_POSTPROCESS_TOOL_RESULT,
                level="warning",
                details={"tool_name": tool_name, "tool_call_id": tool_call_id},
            )
            public_error = project_public_error(coerced)
            postprocess_error_payload: JSONDict = {
                "error": public_error.message,
                "code": public_error.code,
            }
            postprocess_result = AgentToolCallPostprocessResult(
                result_payload=postprocess_error_payload,
                code_diffs=None,
            )
    if postprocess_result is not None:
        result_payload = coerce_in_progress_tool_result_to_error(postprocess_result.result_payload)
        code_diffs = postprocess_result.code_diffs
    if (
        postprocess_result is not None
        and postprocess_result.todo_updated
        and postprocess_result.todo is not None
        and postprocess_result.todo_revision is not None
    ):
        await uncancel_then_cleanup(
            publish_event(
                AgentTodoUpdatedEvent(
                    user_id=user_id,
                    conv_id=conv_id,
                    turn_id=turn_id,
                    iteration_index=iteration_index,
                    sequence=int(postprocess_result.todo_revision),
                    revision=int(postprocess_result.todo_revision),
                    explanation=postprocess_result.todo_explanation,
                    todo=[dict(entry) for entry in postprocess_result.todo],
                ),
            ),
        )
    if (
        postprocess_result is not None
        and postprocess_result.plan_updated
        and postprocess_result.plan_revision is not None
    ):
        await uncancel_then_cleanup(
            publish_event(
                AgentPlanUpdatedEvent(
                    user_id=user_id,
                    conv_id=conv_id,
                    turn_id=turn_id,
                    iteration_index=iteration_index,
                    sequence=int(postprocess_result.plan_revision),
                    revision=int(postprocess_result.plan_revision),
                    title=postprocess_result.plan_title,
                    markdown=postprocess_result.plan_markdown,
                ),
            ),
        )
    return AgentToolCallExecutionOutcome(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        started_at_ms=int(started_at_ms),
        duration_ms=max(0, int((time.monotonic() - started_at_monotonic) * 1000)),
        result_payload=result_payload,
        code_diffs=code_diffs,
    )
