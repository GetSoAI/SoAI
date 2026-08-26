"""SoAI - Tool call execution persistence flows [backend/orchestrator/tool_calls/execution_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.external_service_exception import MCPError
from core.errors.public_projection import project_public_error
from core.mcp.error_mapping import project_mcp_tool_error_fields
from core.tool_calls.error_payloads import build_tool_call_error_payload
from core.types.json import JSONDict, JSONValue
from orchestrator.tool_calls.persistence import (
    ToolCallExecutionRecord,
    ToolCallPersistenceContext,
)
from orchestrator.tool_calls.persistence_initial import (
    persist_tool_call_error,
    persist_tool_call_execution_started,
)
from orchestrator.tool_calls.persistence_terminal import (
    persist_tool_call_cancelled,
    persist_tool_call_completed,
    persist_tool_call_exception_result,
)

__all__ = (
    "persist_blocked_plan_mode_tool_call",
    "persist_cancelled_tool_call_noncritical",
    "persist_deferred_tool_call_accepted_result",
    "persist_mcp_error_tool_call_result",
    "persist_tool_call_arguments_error",
    "persist_tool_call_completed_result",
    "persist_tool_call_error_payload",
    "persist_tool_call_invalid_tool_error",
    "persist_tool_call_start_state",
    "persist_tool_call_timeout_result",
    "persist_unexpected_tool_call_error_result",
)


async def persist_tool_call_start_state(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
) -> None:
    await persist_tool_call_execution_started(
        persistence_context,
        record=record,
    )


async def persist_tool_call_error_payload(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    result_payload: JSONDict,
    duration_ms: int,
    error_message: str,
) -> JSONDict:
    await persist_tool_call_exception_result(
        persistence_context,
        record=record,
        result_payload=result_payload,
        duration_ms=duration_ms,
        error_message=error_message,
    )
    return result_payload


async def persist_tool_call_timeout_result(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    result_payload: JSONDict,
    duration_ms: int,
) -> JSONDict:
    error_value = result_payload.get("error")
    error_message = error_value if isinstance(error_value, str) else "Tool call timed out."
    return await persist_tool_call_error_payload(
        persistence_context,
        record=record,
        result_payload=result_payload,
        duration_ms=duration_ms,
        error_message=error_message,
    )


async def persist_blocked_plan_mode_tool_call(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    block_reason: str,
) -> JSONDict:
    await persist_tool_call_start_state(
        persistence_context,
        record=record,
    )
    blocked_result = build_tool_call_error_payload(
        error_message=block_reason,
        code="tool_not_allowed",
    )
    return await persist_tool_call_error_payload(
        persistence_context,
        record=record,
        result_payload=blocked_result,
        duration_ms=0,
        error_message=block_reason,
    )


async def persist_cancelled_tool_call_noncritical(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    duration_ms: int,
) -> None:
    error_message = "Tool call cancelled."
    cancelled_result = build_tool_call_error_payload(
        error_message=error_message,
        code="cancelled",
    )
    persistence_task = create_ephemeral_task(
        persist_tool_call_cancelled(
            persistence_context,
            record=record,
            result_payload=cancelled_result,
            duration_ms=duration_ms,
            error_message=error_message,
        ),
        name=f"persist-cancelled-tool-call:{record.call_identifier}",
    )
    await uncancel_and_wait(persistence_task)


async def persist_mcp_error_tool_call_result(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    duration_ms: int,
    exception: MCPError,
) -> JSONDict:
    rpc_code = exception.rpc_code
    public_message, public_data = project_mcp_tool_error_fields(
        rpc_code,
        exception.message,
        exception.rpc_data,
    )
    error_result = build_tool_call_error_payload(
        error_message=public_message,
        code=rpc_code,
        data=public_data,
    )
    return await persist_tool_call_error_payload(
        persistence_context,
        record=record,
        result_payload=error_result,
        duration_ms=duration_ms,
        error_message=public_message,
    )


async def persist_unexpected_tool_call_error_result(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    duration_ms: int,
    exception: BaseException,
) -> JSONDict:
    coerced = coerce_to_soai_error(
        exception,
        operation="orchestrator.tool_calls.execute_single_tool_call",
    )
    public_error = project_public_error(coerced)
    error_result = build_tool_call_error_payload(
        error_message=public_error.message,
        code=public_error.code,
    )
    return await persist_tool_call_error_payload(
        persistence_context,
        record=record,
        result_payload=error_result,
        duration_ms=duration_ms,
        error_message=public_error.message,
    )


async def persist_tool_call_invalid_tool_error(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    result_payload: JSONDict,
) -> JSONDict:
    error_value = result_payload.get("error")
    error_message = error_value.strip() if isinstance(error_value, str) else "Tool call failed."
    await persist_tool_call_error(
        persistence_context,
        record=record,
        error_message=error_message,
        result_payload=result_payload,
    )
    return result_payload


async def persist_tool_call_arguments_error(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    error_message: str,
) -> JSONDict:
    result_payload = build_tool_call_error_payload(
        error_message=error_message,
        code="invalid_tool_arguments_json",
    )
    await persist_tool_call_error(
        persistence_context,
        record=record,
        error_message=error_message,
        result_payload=result_payload,
    )
    return result_payload


async def persist_tool_call_completed_result(
    persistence_context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    result_payload: JSONValue,
    duration_ms: int,
) -> None:
    await persist_tool_call_completed(
        persistence_context,
        record=record,
        result_payload=result_payload,
        duration_ms=duration_ms,
    )


async def persist_deferred_tool_call_accepted_result(
    persistence_context: ToolCallPersistenceContext,
    *,
    storage_call_identifier: str,
    result_json: str,
    owner_task_id: str | None,
) -> None:
    if not persistence_context.persist_visible_rows:
        return
    await persistence_context.database_tool_calls.update_tool_call_result(
        storage_call_identifier,
        status=None,
        tool_result=result_json,
        error_message=None,
        duration_ms=None,
        completed_at_ms=None,
        owner_task_id=owner_task_id,
    )
