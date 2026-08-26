"""SoAI - MCP tool task execution and completion finalization [backend/mcp/registry/tools_task_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED,
    MCP_SERVER_COUNTER_TOOLS_CALLS_SUCCEEDED,
)
from core.tasks.enums import TaskStatus
from core.tasks.status_transitions import update_progress
from core.tasks.task_cancellation import cancel
from core.types.json_value import coerce_json_dict
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol
from mcp.registry.proxied_task_waiting import await_proxied_task_completion
from mcp.registry.tool_execution_context import activate_registry_tool_context
from mcp.registry.tool_execution_kernel import execute_registered_tool
from mcp.registry.tool_handler_execution import format_tool_timeout_message
from mcp.registry.tool_name_candidates import build_registry_unknown_tool_message
from mcp.registry.tool_result_envelopes import (
    build_proxied_task_completion_payload,
    build_tool_task_completion_result,
    extract_queued_task_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("execute_tool_as_task",)

LOGGER_NAME = "SoAI.mcp.registry.tools_task_execution"
OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK = (
    "mcp.registry.tools_task_execution.execute_tool_as_task"
)
OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK_CANCEL_PROXIED_TASK = (
    "mcp.registry.tools_task_execution.execute_tool_as_task.cancel_proxied_task"
)
OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK_PROGRESS_COMPLETION = (
    "mcp.registry.tools_task_execution.execute_tool_as_task.progress_completion"
)
OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK_PROGRESS_START = (
    "mcp.registry.tools_task_execution.execute_tool_as_task.progress_start"
)


async def execute_tool_as_task(
    manager: MCPRegistryManagerProtocol,
    task_id: str,
    tool_name: str,
    arguments: JSONDict,
    client_id: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    proxied_task_id: str | None = None
    timeout_sec = 0.0
    try:
        async with activate_registry_tool_context(
            manager,
            client_id=client_id,
            task_id=task_id,
        ) as context:
            handler = manager.state.registration.registered_tools.get(tool_name)
            if not handler:
                manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
                await manager.task.fail_task(
                    task_id,
                    -32602,
                    await build_registry_unknown_tool_message(manager, tool_name=tool_name),
                )
                return
            task = await manager.task.get_task(task_id)
            if task and task.status == TaskStatus.CANCELLED:
                return
            try:
                await update_progress(
                    manager.task_registry,
                    task_id,
                    progress_current=1,
                    status_message=f"Executing {tool_name}...",
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Unable to set task progress start (non-critical).",
                    operation=OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK_PROGRESS_START,
                    details={"task_id": task_id, "tool_name": tool_name},
                    level="debug",
                )
            execution = await execute_registered_tool(
                manager,
                client_id=client_id,
                user_id=context.user_id,
                tool_name=tool_name,
                arguments=arguments,
                logger=logger,
                workspace_initialized=True,
            )
            timeout_sec = execution.timeout_sec
            task = await manager.task.get_task(task_id)
            if task and task.status == TaskStatus.CANCELLED:
                return
            result_payload = coerce_json_dict(execution.result_payload)
            if result_payload is not None:
                proxied_task_id = extract_queued_task_id(result_payload)
                if proxied_task_id == task_id:
                    raise MCPJSONRPCError(
                        -32603,
                        "Tool returned a queued task_id equal to the current MCP task_id",
                    )
                if proxied_task_id:
                    child = await await_proxied_task_completion(
                        manager,
                        parent_task_id=task_id,
                        proxied_task_id=proxied_task_id,
                    )
                    if child.status == TaskStatus.CANCELLED:
                        await manager.task.cancel_task(task_id, child.error_message or "Cancelled")
                        return
                    if child.status == TaskStatus.FAILED:
                        await manager.task.fail_task(
                            task_id,
                            child.error_code if child.error_code is not None else -32603,
                            child.error_message or "Task failed",
                        )
                        return
                    payload = dict(result_payload)
                    payload.update(
                        build_proxied_task_completion_payload(
                            task_id=proxied_task_id,
                            status=child.status,
                            result=child.result,
                            error_message=child.error_message,
                        ),
                    )
                    try:
                        await update_progress(
                            manager.task_registry,
                            task_id,
                            progress_current=100,
                            status_message=f"Completed {tool_name}",
                        )
                    except RECOVERABLE_EXCEPTIONS as exception:
                        log_handled_exception(
                            logger,
                            exception,
                            message="Unable to set task progress completion (non-critical).",
                            operation=OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK_PROGRESS_COMPLETION,
                            details={"task_id": task_id, "tool_name": tool_name},
                            level="debug",
                        )
                    await manager.task.complete_task(
                        task_id,
                        build_tool_task_completion_result(payload),
                    )
                    manager.metrics_manager.increment_counter(
                        *MCP_SERVER_COUNTER_TOOLS_CALLS_SUCCEEDED,
                    )
                    return
            try:
                await update_progress(
                    manager.task_registry,
                    task_id,
                    progress_current=100,
                    status_message=f"Completed {tool_name}",
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Unable to set task progress completion (non-critical).",
                    operation=OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK_PROGRESS_COMPLETION,
                    details={"task_id": task_id, "tool_name": tool_name},
                    level="debug",
                )
            await manager.task.complete_task(
                task_id,
                build_tool_task_completion_result(execution.result_payload),
            )
            manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_SUCCEEDED)
    except asyncio.CancelledError:
        logger.debug("Task %s execution cancelled", task_id)
        if proxied_task_id:
            try:
                await cancel(
                    manager.task_registry,
                    proxied_task_id,
                    reason="Cancelled by MCP tool task",
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to cancel proxied task after MCP tool cancellation (non-critical).",
                    operation=OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK_CANCEL_PROXIED_TASK,
                    details={"task_id": task_id, "proxied_task_id": proxied_task_id},
                    level="debug",
                )
        await manager.task.cancel_task(task_id, "Cancelled during execution")
        raise
    except MCPJSONRPCError as exception:
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
        await manager.task.fail_task(task_id, exception.rpc_code, exception.message)
    except TimeoutError:
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
        await manager.task.fail_task(
            task_id,
            -32603,
            format_tool_timeout_message(tool_name, timeout_sec),
        )
        logger.warning("Tool task %s (%s) timed out after %.2fs", task_id, tool_name, timeout_sec)
    except RECOVERABLE_EXCEPTIONS as exception:
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
        log_exception(
            logger,
            exception,
            message="MCP tool task failed with a recoverable exception.",
            operation=OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK,
            details={"task_id": task_id, "tool_name": tool_name},
            level="warning",
        )
        await manager.task.fail_task(task_id, -32603, str(exception))
    except SoAIError as exception:
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
        log_exception(
            logger,
            exception,
            message="MCP tool task failed with a SoAI exception.",
            operation=OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK,
            details={"task_id": task_id, "tool_name": tool_name},
            level="warning",
        )
        await manager.task.fail_task(task_id, -32603, str(exception))
    except (KeyError, RuntimeError, TypeError) as exception:
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TOOLS_CALLS_FAILED)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK,
        )
        log_exception(
            logger,
            coerced,
            message="MCP tool task failed with an unexpected exception.",
            operation=OPERATION_MCP_REGISTRY_TOOLS_TASK_EXECUTION_EXECUTE_TOOL_AS_TASK,
            details={"task_id": task_id, "tool_name": tool_name},
            level="error",
        )
        await manager.task.fail_task(task_id, -32603, str(coerced))
    finally:
        manager.state.task.task_coroutines.pop(task_id, None)
