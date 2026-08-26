"""SoAI - MCP registered tool handler execution [backend/mcp/registry/tool_handler_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import math
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.external_service_exception import MCPError
from core.timing.constants import SETUP_TIMEOUT_SEC
from core.types.json_value import is_json_value
from mcp.protocol.types import MCPJSONRPCError
from mcp.shared.exception_boundary import (
    resolve_mcp_boundary_rpc_code,
    resolve_mcp_boundary_rpc_data,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.protocol.types import ToolHandler

__all__ = (
    "format_tool_timeout_message",
    "invoke_tool_handler_with_timeout",
    "resolve_tool_timeout_sec",
)

OPERATION_MCP_REGISTRY_TOOL_HANDLER_EXECUTION = "mcp.registry.tool_handler_execution"


def resolve_tool_timeout_sec(configured_timeout_sec: float) -> float:
    timeout_sec = float(configured_timeout_sec)
    if not math.isfinite(timeout_sec):
        raise ValidationError("TOOLS.MCP.TASKS.TOOL_TIMEOUT_SEC must be finite.")
    if timeout_sec <= 0.0:
        return float(SETUP_TIMEOUT_SEC)
    return timeout_sec


def format_tool_timeout_message(tool_name: str, timeout_sec: float) -> str:
    return (
        f"Tool '{tool_name}' timed out after {int(max(0.0, timeout_sec))}s "
        "(config: TOOLS.MCP.TASKS.TOOL_TIMEOUT_SEC)."
    )


async def invoke_tool_handler_with_timeout(
    *,
    handler: ToolHandler,
    arguments: JSONDict,
    tool_name: str,
    timeout_sec: float,
    logger: LoggerProtocol,
) -> JSONValue:
    effective_timeout_sec = resolve_tool_timeout_sec(timeout_sec)
    handler_task: asyncio.Task[JSONValue] | None = None

    async def invoke_handler() -> JSONValue:
        return await handler(arguments)

    try:
        handler_task = create_ephemeral_task(
            invoke_handler(),
            name=f"mcp-tool-handler-{tool_name}",
            log_exceptions=False,
        )
        done, _pending = await asyncio.wait({handler_task}, timeout=effective_timeout_sec)
        if not done and handler_task.done() and not handler_task.cancelled():
            done = {handler_task}
        if not done:
            await cancel_and_await(
                [handler_task],
                logger=logger,
                task_label=f"tool '{tool_name}' handler",
                log_level=logging.DEBUG,
                timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            )
            raise TimeoutError
        result_payload = handler_task.result()
        if not is_json_value(result_payload):
            raise MCPJSONRPCError(
                -32603,
                f"Tool '{tool_name}' returned a non-JSON value: {type(result_payload).__name__}",
            )
        return result_payload
    except asyncio.CancelledError:
        if handler_task is not None and not handler_task.done():
            await uncancel_then_cleanup(
                cancel_and_await(
                    [handler_task],
                    logger=logger,
                    task_label=f"tool '{tool_name}' handler",
                    log_level=logging.DEBUG,
                    timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
                ),
            )
        raise
    except TimeoutError:
        raise
    except MCPJSONRPCError:
        raise
    except MCPError as exception:
        raise MCPJSONRPCError(
            exception.rpc_code,
            exception.message,
            exception.rpc_data,
        ) from exception
    except Exception as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_REGISTRY_TOOL_HANDLER_EXECUTION,
        )
        log_exception(
            logger,
            coerced,
            operation=OPERATION_MCP_REGISTRY_TOOL_HANDLER_EXECUTION,
            message="MCP registered tool handler failed.",
            details={"tool_name": tool_name},
        )
        raise MCPJSONRPCError(
            resolve_mcp_boundary_rpc_code(exception),
            coerced.message,
            resolve_mcp_boundary_rpc_data(exception),
        ) from exception
    finally:
        if handler_task is not None and handler_task.done() and not handler_task.cancelled():
            handler_task.exception()
