"""SoAI - MCP tools/call handler [backend/mcp/registry/tools_call.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.licensing.admission import LicensingOperationClass
from core.licensing.enforcement import LICENSING_RESTRICTED_MESSAGE
from core.logging.trace import get_logger
from core.mcp.tool_call_arguments import parse_mcp_tool_call_arguments
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
    MCP_SERVER_COUNTER_TOOLS_CALLS_SUCCEEDED,
    MCP_SERVER_COUNTER_TOOLS_CALLS_TOTAL,
    MCP_SERVER_TIMING_TOOL_EXECUTION_MS,
)
from core.tasks.asyncio_task_spawner import create_tracked_and_track_task
from core.timing.monotonic import monotonic_ms
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol
from mcp.registry.tool_execution_context import activate_registry_tool_context
from mcp.registry.tool_execution_kernel import (
    execute_registered_tool,
    initialize_registered_tool_workspace,
)
from mcp.registry.tool_handler_execution import format_tool_timeout_message
from mcp.registry.tool_name_candidates import build_registry_unknown_tool_error
from mcp.registry.tool_result_envelopes import build_inline_tool_result
from mcp.registry.tools_remote_routing import try_route_to_remote_server_tool
from mcp.registry.tools_task_execution import execute_tool_as_task
from mcp.server.handlers.task_payloads import build_task_response

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_tools_call",)

LOGGER_NAME = "SoAI.mcp.registry.tools_call"
OPERATION_MCP_REGISTRY_TOOLS_CALL_BIND_TASK = "mcp.registry.tools_call.bind_task"
OPERATION_MCP_REGISTRY_TOOLS_CALL_FAIL_TASK_AFTER_BIND_ERROR = (
    "mcp.registry.tools_call.fail_task_after_bind_error"
)
OPERATION_MCP_REGISTRY_TOOLS_CALL_INLINE_TOOL_HANDLER_FAILED = (
    "mcp.registry.tools_call.inline_tool_handler_failed"
)
OPERATION_MCP_REGISTRY_TOOLS_CALL_WORKSPACE_INIT_FAILED = (
    "mcp.registry.tools_call.workspace_init_failed"
)


async def handle_tools_call(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_TOTAL)
    start_time = time.monotonic()
    start_time_ms = monotonic_ms()
    tool_call = parse_mcp_tool_call_arguments(
        parameters,
        build_error=MCPJSONRPCError,
    )
    name = tool_call.name
    arguments = tool_call.arguments
    task_requested = tool_call.task_requested
    try:
        licensing_admission = await manager.licensing_status.admission(
            LicensingOperationClass.ORDINARY
        )
        if not licensing_admission.allowed:
            manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
            raise MCPJSONRPCError(
                -32003,
                LICENSING_RESTRICTED_MESSAGE,
                data={
                    "code": "licensing_restricted",
                    "reason": licensing_admission.reason,
                },
            )
        async with activate_registry_tool_context(manager, client_id=client_id) as context:
            remote_result = await try_route_to_remote_server_tool(
                manager,
                name,
                arguments,
                start_time,
            )
            if remote_result is not None:
                return remote_result
            if name and name in manager.state.registration.registered_tools:
                if task_requested and not manager.tasks_enabled:
                    manager.metrics_manager.increment_counter(
                        *MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
                    )
                    raise MCPJSONRPCError(-32602, "MCP task execution is disabled.")
                if task_requested:
                    try:
                        await initialize_registered_tool_workspace(
                            manager,
                            client_id=client_id,
                            user_id=context.user_id,
                            tool_name=name,
                            arguments=arguments,
                        )
                    except MCPJSONRPCError:
                        manager.metrics_manager.increment_counter(
                            *MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
                        )
                        raise
                    except RECOVERABLE_EXCEPTIONS as exception:
                        manager.metrics_manager.increment_counter(
                            *MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
                        )
                        log_exception(
                            logger,
                            exception,
                            message="Failed to initialize runtime files root before tool execution.",
                            operation=OPERATION_MCP_REGISTRY_TOOLS_CALL_WORKSPACE_INIT_FAILED,
                            details={"tool": name, "client_id": client_id},
                            level="warning",
                        )
                        raise MCPJSONRPCError(-32603, str(exception)) from exception
                    except asyncio.CancelledError:
                        manager.metrics_manager.increment_counter(
                            *MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
                        )
                        raise
                    task = await manager.task.create_task(
                        client_id,
                        f"tools/call:{name}",
                        parameters,
                    )
                    try:
                        tool_task = await create_tracked_and_track_task(
                            execute_tool_as_task(
                                manager,
                                task.task_id,
                                name,
                                arguments,
                                client_id,
                            ),
                            cancellation_binder=manager.cancellation_binder,
                            cancellation_id=task.cancellation_id,
                            owner="mcp_client",
                            track_task=manager.track_background_task,
                            name=f"mcp-tool-{name}-{task.task_id}",
                            logger=logger,
                            metadata={"task_id": task.task_id},
                        )
                    except RECOVERABLE_EXCEPTIONS as exception:
                        log_exception(
                            logger,
                            exception,
                            message=(
                                "Failed to bind tool task to cancellation registry. "
                                "Cancelling task."
                            ),
                            operation=OPERATION_MCP_REGISTRY_TOOLS_CALL_BIND_TASK,
                            details={
                                "task_id": task.task_id,
                                "tool": name,
                                "client_id": client_id,
                            },
                            level="warning",
                        )
                        manager.metrics_manager.increment_counter(
                            *MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
                        )
                        try:
                            await manager.task.fail_task(
                                task.task_id,
                                -32603,
                                "Failed to schedule tool task.",
                            )
                        except RECOVERABLE_EXCEPTIONS as fail_exception:
                            log_handled_exception(
                                logger,
                                fail_exception,
                                message=(
                                    "Failed to mark tool task as failed after bind failure "
                                    "(non-critical)."
                                ),
                                operation=OPERATION_MCP_REGISTRY_TOOLS_CALL_FAIL_TASK_AFTER_BIND_ERROR,
                                details={
                                    "task_id": task.task_id,
                                    "tool": name,
                                    "client_id": client_id,
                                },
                                level="debug",
                            )
                        raise MCPJSONRPCError(
                            -32603,
                            "Failed to schedule tool task.",
                        ) from exception
                    manager.state.task.task_coroutines[task.task_id] = tool_task
                    return {"task": build_task_response(task)}
                timeout_sec = 0.0
                try:
                    execution = await execute_registered_tool(
                        manager,
                        client_id=client_id,
                        user_id=context.user_id,
                        tool_name=name,
                        arguments=arguments,
                        logger=logger,
                    )
                    timeout_sec = execution.timeout_sec
                    manager.metrics_manager.increment_counter(
                        *MCP_SERVER_COUNTER_TOOLS_CALLS_SUCCEEDED,
                    )
                    return build_inline_tool_result(execution.result_payload)
                except TimeoutError as exception:
                    manager.metrics_manager.increment_counter(
                        *MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
                    )
                    raise MCPJSONRPCError(
                        -32603,
                        format_tool_timeout_message(name, timeout_sec),
                    ) from exception
                except MCPJSONRPCError:
                    manager.metrics_manager.increment_counter(
                        *MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
                    )
                    raise
                except RECOVERABLE_EXCEPTIONS as exception:
                    manager.metrics_manager.increment_counter(
                        *MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
                    )
                    log_exception(
                        logger,
                        exception,
                        message="Inline tool handler raised a recoverable exception.",
                        operation=OPERATION_MCP_REGISTRY_TOOLS_CALL_INLINE_TOOL_HANDLER_FAILED,
                        details={"tool": name, "client_id": client_id},
                        level="warning",
                    )
                    raise MCPJSONRPCError(-32603, str(exception)) from exception
                except asyncio.CancelledError:
                    logger.debug(
                        "Inline tool handler cancelled before completion for tool %s and client %s.",
                        name,
                        client_id,
                    )
                    raise
            manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
            raise await build_registry_unknown_tool_error(manager, tool_name=name)
    finally:
        manager.metrics_manager.record_timing(
            *MCP_SERVER_TIMING_TOOL_EXECUTION_MS,
            duration_ms=float(monotonic_ms() - start_time_ms),
        )
