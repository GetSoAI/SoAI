"""SoAI - Single MCP tool call execution helpers [backend/orchestrator/tool_calls/execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError
from core.errors.external_service_exception import MCPError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tool_calls.plan_mode_policy import plan_mode_block_reason
from core.tool_calls.visibility import should_persist_visible_tool_call_rows
from orchestrator.tool_calls.claimed_call_wait import wait_for_claimed_tool_call_result
from orchestrator.tool_calls.deferred_acceptance import (
    persist_deferred_tool_call_acceptance,
)
from orchestrator.tool_calls.dependencies import ToolCallProcessorDependencies
from orchestrator.tool_calls.execution_availability import (
    persist_unavailable_tool_call_error,
)
from orchestrator.tool_calls.execution_error_results import (
    build_execution_boundary_error_payload,
    persist_execution_error_result_or_return_payload,
    persist_mcp_error_result_or_return_payload,
)
from orchestrator.tool_calls.execution_identity import (
    resolve_tool_call_executor_identity,
)
from orchestrator.tool_calls.execution_inputs import prepare_tool_call_execution_input
from orchestrator.tool_calls.execution_persistence import (
    persist_blocked_plan_mode_tool_call,
    persist_cancelled_tool_call_noncritical,
    persist_tool_call_arguments_error,
    persist_tool_call_completed_result,
    persist_tool_call_start_state,
)
from orchestrator.tool_calls.persistence import (
    ToolCallExecutionRecord,
    ToolCallPersistenceContext,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("execute_single_tool_call",)

OPERATION_EXECUTE_SINGLE_TOOL_CALL = "orchestrator.tool_calls.execute_single_tool_call"


async def execute_single_tool_call(
    deps: ToolCallProcessorDependencies,
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call: JSONDict,
    logger: LoggerProtocol,
    deadline_monotonic: float | None = None,
) -> JSONValue:
    persistence_context = ToolCallPersistenceContext(
        database_tool_calls=deps.database_tool_calls,
        event_bus=deps.event_bus,
        logger=logger,
        request_context=request_context,
        tool_context=tool_context,
        persist_visible_rows=should_persist_visible_tool_call_rows(request_context),
        publish_events=deps.event_bus is not None,
    )
    prepared_input = prepare_tool_call_execution_input(
        request_context=request_context,
        tool_context=tool_context,
        tool_call=tool_call,
    )
    tool_call_record = ToolCallExecutionRecord(
        storage_call_identifier=prepared_input.storage_call_identifier,
        call_identifier=prepared_input.call_identifier,
        tool_name=prepared_input.tool_name,
        arguments_json=None,
        chronology=prepared_input.chronology,
    )
    tool_entry = tool_context.tool_map.get(prepared_input.tool_name)
    if not isinstance(tool_entry, dict):
        try:
            unavailable_result = await uncancel_then_cleanup(
                persist_unavailable_tool_call_error(
                    persistence_context,
                    record=tool_call_record,
                    tool_name=prepared_input.tool_name,
                    tool_map=tool_context.tool_map,
                ),
            )
        except ConflictError:
            return await wait_for_claimed_tool_call_result(
                database_tool_calls=deps.database_tool_calls,
                persistence_context=persistence_context,
                record=tool_call_record,
                tool_context=tool_context,
                storage_call_identifier=prepared_input.storage_call_identifier,
                logger=logger,
                deadline_monotonic=deadline_monotonic,
            )
        return unavailable_result
    tool_call_record = ToolCallExecutionRecord(
        storage_call_identifier=prepared_input.storage_call_identifier,
        call_identifier=prepared_input.call_identifier,
        tool_name=prepared_input.tool_name,
        arguments_json=prepared_input.arguments_json,
        chronology=prepared_input.chronology,
    )
    mode_value = request_context.agent_mode
    if mode_value == "plan":
        block_reason = plan_mode_block_reason(prepared_input.tool_name, tool_entry)
        if block_reason is not None:
            try:
                blocked_result = await uncancel_then_cleanup(
                    persist_blocked_plan_mode_tool_call(
                        persistence_context,
                        record=tool_call_record,
                        block_reason=block_reason,
                    ),
                )
                return blocked_result
            except ConflictError:
                return await wait_for_claimed_tool_call_result(
                    database_tool_calls=deps.database_tool_calls,
                    persistence_context=persistence_context,
                    record=tool_call_record,
                    tool_context=tool_context,
                    storage_call_identifier=prepared_input.storage_call_identifier,
                    logger=logger,
                    deadline_monotonic=deadline_monotonic,
                )
    if prepared_input.arguments_error:
        try:
            arguments_error_result = await uncancel_then_cleanup(
                persist_tool_call_arguments_error(
                    persistence_context,
                    record=tool_call_record,
                    error_message=prepared_input.arguments_error,
                ),
            )
            return arguments_error_result
        except ConflictError:
            return await wait_for_claimed_tool_call_result(
                database_tool_calls=deps.database_tool_calls,
                persistence_context=persistence_context,
                record=tool_call_record,
                tool_context=tool_context,
                storage_call_identifier=prepared_input.storage_call_identifier,
                logger=logger,
                deadline_monotonic=deadline_monotonic,
            )
    try:
        await uncancel_then_cleanup(
            persist_tool_call_start_state(
                persistence_context,
                record=tool_call_record,
            ),
        )
    except ConflictError:
        return await wait_for_claimed_tool_call_result(
            database_tool_calls=deps.database_tool_calls,
            persistence_context=persistence_context,
            record=tool_call_record,
            tool_context=tool_context,
            storage_call_identifier=prepared_input.storage_call_identifier,
            logger=logger,
            deadline_monotonic=deadline_monotonic,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception=exception,
            operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
        )
        log_exception(
            logger,
            coerced,
            message="Tool-call start persistence failed before execution.",
            operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
            level="warning",
        )
        return build_execution_boundary_error_payload(coerced)
    start_time = time.monotonic()
    try:
        executor_identity = resolve_tool_call_executor_identity(
            tool_context=tool_context,
            chronology=prepared_input.chronology,
        )
        raw_result = await deps.tool_executor.execute_openai_tool_call(
            prepared_input.tool_name,
            prepared_input.arguments_payload or {},
            request_context=request_context,
            user_id=tool_context.user_id,
            conv_id=tool_context.conv_id,
            call_id=prepared_input.call_identifier,
            storage_call_id=prepared_input.storage_call_identifier,
            message_index=tool_context.message_index,
            assistant_at_ms=executor_identity.assistant_at_ms,
            assistant_turn_at_ms=executor_identity.assistant_turn_at_ms,
            model_variant_index=executor_identity.model_variant_index,
            sequence_index=executor_identity.sequence_index,
            content_index_before=executor_identity.content_index_before,
            thinking_index_before=executor_identity.thinking_index_before,
        )
        duration_ms = int((time.monotonic() - start_time) * 1000)
        deferred_acceptance = await persist_deferred_tool_call_acceptance(
            persistence_context=persistence_context,
            storage_call_identifier=prepared_input.storage_call_identifier,
            raw_result=raw_result,
        )
        if deferred_acceptance is not None:
            return deferred_acceptance.result
        result = raw_result
        await persist_tool_call_completed_result(
            persistence_context,
            record=tool_call_record,
            result_payload=result,
            duration_ms=duration_ms,
        )
        return result
    except asyncio.CancelledError:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        try:
            await persist_cancelled_tool_call_noncritical(
                persistence_context,
                record=tool_call_record,
                duration_ms=duration_ms,
            )
        finally:
            raise
    except MCPError as exception:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return await persist_mcp_error_result_or_return_payload(
            logger=logger,
            persistence_context=persistence_context,
            record=tool_call_record,
            duration_ms=duration_ms,
            exception=exception,
            tool_name=prepared_input.tool_name,
            call_identifier=prepared_input.call_identifier,
            storage_call_identifier=prepared_input.storage_call_identifier,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return await persist_execution_error_result_or_return_payload(
            logger=logger,
            persistence_context=persistence_context,
            record=tool_call_record,
            duration_ms=duration_ms,
            exception=exception,
            tool_name=prepared_input.tool_name,
            call_identifier=prepared_input.call_identifier,
            storage_call_identifier=prepared_input.storage_call_identifier,
            log_message="Tool call failed with a handled runtime exception",
        )
