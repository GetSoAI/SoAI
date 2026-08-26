"""SoAI - Tool-call execution error result boundaries [backend/orchestrator/tool_calls/execution_error_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.external_service_exception import MCPError
from core.errors.public_projection import project_public_error
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.mcp.error_mapping import project_mcp_tool_error_fields
from core.tool_calls.error_payloads import build_tool_call_error_payload
from orchestrator.tool_calls.execution_persistence import (
    persist_mcp_error_tool_call_result,
    persist_unexpected_tool_call_error_result,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from orchestrator.tool_calls.persistence import (
        ToolCallExecutionRecord,
        ToolCallPersistenceContext,
    )

__all__ = (
    "build_execution_boundary_error_payload",
    "log_execution_boundary_error_and_build_payload",
    "persist_execution_error_result_or_return_payload",
    "persist_mcp_error_result_or_return_payload",
)

OPERATION_EXECUTE_SINGLE_TOOL_CALL = "orchestrator.tool_calls.execute_single_tool_call"


def build_execution_boundary_error_payload(exception: BaseException) -> JSONDict:
    coerced = coerce_to_soai_error(
        exception,
        operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
    )
    public_error = project_public_error(coerced)
    return build_tool_call_error_payload(
        error_message=public_error.message,
        code=public_error.code,
    )


def log_execution_boundary_error_and_build_payload(
    *,
    logger: LoggerProtocol,
    exception: BaseException,
    message: str,
    tool_name: str,
    call_identifier: str,
    storage_call_identifier: str,
) -> JSONDict:
    coerced = coerce_to_soai_error(
        exception,
        operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
    )
    _log_tool_error(
        logger=logger,
        exception=coerced,
        message=message,
        tool_name=tool_name,
        call_identifier=call_identifier,
        storage_call_identifier=storage_call_identifier,
    )
    return build_execution_boundary_error_payload(exception)


def _log_tool_error(
    *,
    logger: LoggerProtocol,
    exception: BaseException,
    message: str,
    tool_name: str,
    call_identifier: str,
    storage_call_identifier: str,
) -> None:
    log_exception(
        logger,
        exception,
        message=message,
        operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
        level="warning",
        details={
            "tool_name": tool_name,
            "call_id": call_identifier,
            "storage_call_id": storage_call_identifier,
        },
    )


async def persist_mcp_error_result_or_return_payload(
    *,
    logger: LoggerProtocol,
    persistence_context: ToolCallPersistenceContext,
    record: ToolCallExecutionRecord,
    duration_ms: int,
    exception: MCPError,
    tool_name: str,
    call_identifier: str,
    storage_call_identifier: str,
) -> JSONDict:
    if int(exception.rpc_code) == -32603:
        log_handled_exception(
            logger,
            exception,
            message="MCP tool call failed.",
            operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
            details={
                "tool_name": tool_name,
                "call_id": call_identifier,
                "storage_call_id": storage_call_identifier,
                "rpc_code": int(exception.rpc_code),
            },
        )
    try:
        return await persist_mcp_error_tool_call_result(
            persistence_context,
            record=record,
            duration_ms=duration_ms,
            exception=exception,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as persistence_exception:
        persistence_error = coerce_to_soai_error(
            persistence_exception,
            operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
        )
        log_exception(
            logger,
            persistence_error,
            message="Tool-call error persistence failed.",
            operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
            level="warning",
            details={
                "tool_name": tool_name,
                "call_id": call_identifier,
                "storage_call_id": storage_call_identifier,
            },
        )
        public_message, public_data = project_mcp_tool_error_fields(
            exception.rpc_code,
            exception.message,
            exception.rpc_data,
        )
        return build_tool_call_error_payload(
            error_message=public_message,
            code=exception.rpc_code,
            data=public_data,
        )


async def persist_execution_error_result_or_return_payload(
    *,
    logger: LoggerProtocol,
    persistence_context: ToolCallPersistenceContext,
    record: ToolCallExecutionRecord,
    duration_ms: int,
    exception: BaseException,
    tool_name: str,
    call_identifier: str,
    storage_call_identifier: str,
    log_message: str,
) -> JSONDict:
    coerced = coerce_to_soai_error(
        exception,
        operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
    )
    _log_tool_error(
        logger=logger,
        exception=coerced,
        message=log_message,
        tool_name=tool_name,
        call_identifier=call_identifier,
        storage_call_identifier=storage_call_identifier,
    )
    try:
        return await persist_unexpected_tool_call_error_result(
            persistence_context,
            record=record,
            duration_ms=duration_ms,
            exception=coerced,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as persistence_exception:
        persistence_error = coerce_to_soai_error(
            persistence_exception,
            operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
        )
        log_exception(
            logger,
            persistence_error,
            message="Tool-call error persistence failed.",
            operation=OPERATION_EXECUTE_SINGLE_TOOL_CALL,
            level="warning",
            details={
                "tool_name": tool_name,
                "call_id": call_identifier,
                "storage_call_id": storage_call_identifier,
            },
        )
        public_error = project_public_error(coerced)
        return build_tool_call_error_payload(
            error_message=public_error.message,
            code=public_error.code,
        )
