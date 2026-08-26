"""SoAI - OpenAI chat inference request failure handling [backend/features/api/routes/openai/chat/inference_request_failure_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.runtime.request_context import RequestContext
from features.agent.runtime.turn_finalization import cancel_active_subagent_turns
from features.agent.runtime.turn_lifecycle.finalize import (
    finalize_running_turn_noncritical,
)
from features.agent.runtime.turn_lifecycle.noncritical_finalization_request import (
    build_terminal_turn_noncritical_finalization_request,
)
from features.api.runtime.openai_quota_reservations import (
    release_token_quota_reservation_if_present,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "finalize_openai_running_turn_error_noncritical",
    "finalize_openai_running_turn_noncritical",
    "handle_inference_request_failure",
)

OPERATION_QUOTA_RELEASE = "api_openai.handle_inference_request.unhandled.quota_release"
OPERATION_UNHANDLED = "api_openai.handle_inference_request.unhandled"
OPERATION_FINALIZE_CLAIMED_TURN = "api_openai.handle_inference_request.claimed_turn_unhandled"


async def finalize_openai_running_turn_noncritical(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    context: RequestContext,
    tool_context: MCPToolContext | None,
    status: str,
    reached_max_iterations: bool,
    error_message: str | None,
    error_type: str | None,
    operation: str,
    log_message: str,
) -> None:
    if tool_context is None:
        return
    if context.agent_turn_scope != TURN_SCOPE_SUBAGENT and context.agent_turn_id:
        await uncancel_then_cleanup(
            cancel_active_subagent_turns(
                database_agent_turns=api_context.dependencies.database_agent_turns,
                task_registry=api_context.dependencies.task_registry,
                conv_id=tool_context.conv_id,
                user_id=tool_context.user_id,
                parent_turn_id=context.agent_turn_id,
            ),
        )
    await finalize_running_turn_noncritical(
        database_agent_turns=api_context.dependencies.database_agent_turns,
        logger=logger,
        request=build_terminal_turn_noncritical_finalization_request(
            trace_id=str(context.trace_id or ""),
            conv_id=tool_context.conv_id,
            user_id=tool_context.user_id,
            turn_id=context.agent_turn_id,
            execution_token=context.agent_turn_execution_token,
            status=status,
            reached_max_iterations=reached_max_iterations,
            error_message=error_message,
            error_type=error_type,
            operation=operation,
            log_message=log_message,
        ),
    )


async def finalize_openai_running_turn_error_noncritical(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    context: RequestContext,
    tool_context: MCPToolContext | None,
    error_message: str | None,
    error_type: str | None,
    operation: str,
    log_message: str,
) -> None:
    await finalize_openai_running_turn_noncritical(
        api_context=api_context,
        logger=logger,
        context=context,
        tool_context=tool_context,
        status="error",
        reached_max_iterations=False,
        error_message=error_message,
        error_type=error_type,
        operation=operation,
        log_message=log_message,
    )


async def handle_inference_request_failure(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    context: RequestContext,
    tool_context: MCPToolContext | None,
    claimed_agent_turn: bool,
    api_key_id: str | None,
    quota_reservation: JSONDict | None,
    exception: BaseException,
    log_message: str,
    level: str,
    finalize_log_message: str,
) -> None:
    await release_token_quota_reservation_if_present(
        api_context,
        api_key_id,
        quota_reservation,
        trace_id=context.trace_id,
        operation=OPERATION_QUOTA_RELEASE,
    )
    coerced = coerce_to_soai_error(exception, operation=OPERATION_UNHANDLED)
    log_exception(
        logger,
        coerced,
        message=log_message,
        trace_id=context.trace_id,
        operation=OPERATION_UNHANDLED,
        level=level,
    )
    if claimed_agent_turn and tool_context is not None:
        await finalize_openai_running_turn_error_noncritical(
            api_context=api_context,
            logger=logger,
            context=context,
            tool_context=tool_context,
            error_message=coerced.message,
            error_type=str(coerced.code),
            operation=OPERATION_FINALIZE_CLAIMED_TURN,
            log_message=finalize_log_message,
        )
