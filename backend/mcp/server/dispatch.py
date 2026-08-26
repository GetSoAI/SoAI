"""SoAI - MCP server request dispatch [backend/mcp/server/dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.locks import bounded_lock_for_cleanup
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.external_service_exception import MCPError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.jsonrpc_messages import resolve_jsonrpc_params_object
from core.mcp.jsonrpc_responses import build_error_response, build_success_response
from core.mcp.mcp_2025_11_25 import JSON_RPC_VERSION, validate_jsonrpc_id
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_REQUESTS_FAILED,
    MCP_SERVER_COUNTER_REQUESTS_HANDLED,
    MCP_SERVER_COUNTER_REQUESTS_TOTAL,
    MCP_SERVER_TIMING_REQUEST_LATENCY_MS,
)
from core.timing.monotonic import monotonic_ms
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.cancellation import handle_notification_cancelled
from mcp.registry.handler_maps import (
    resolve_server_mode_client_handler,
    resolve_server_mode_params_only_handler,
    resolve_task_method_handler,
)
from mcp.registry.initialization import handle_initialize, handle_logging_set_level
from mcp.server.internal_protocols import MCPServerDispatchSurface
from mcp.server.state import MCPServerPendingRequestKey

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("handle_mcp_request",)

LOGGER_NAME = "SoAI.mcp.server.dispatch"
OPERATION = "mcp.server.handle_request"


async def handle_mcp_request(
    self: MCPServerDispatchSurface,
    request_data: JSONDict,
    client_id: str,
    session_id: str | None = None,
    protocol_version: str | None = None,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    self.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_REQUESTS_TOTAL)
    start_time_ms = monotonic_ms()
    if not self.server_mode_active:
        return build_error_response(None, -32603, "MCP Server Mode is not active")
    if request_data.get("jsonrpc") != JSON_RPC_VERSION:
        return build_error_response(
            None,
            -32600,
            f"Invalid JSON-RPC version: {request_data.get('jsonrpc')}",
        )
    raw_rpc_id = request_data.get("id")
    if raw_rpc_id is not None and (
        not isinstance(raw_rpc_id, str | int) or isinstance(raw_rpc_id, bool)
    ):
        return build_error_response(
            None,
            -32600,
            f"Invalid JSON-RPC id type: {type(raw_rpc_id).__name__}",
        )
    id_valid, rpc_id = validate_jsonrpc_id(raw_rpc_id)
    if not id_valid:
        return build_error_response(
            None,
            -32600,
            f"Invalid JSON-RPC id type: {type(raw_rpc_id).__name__}",
        )
    method_value = request_data.get("method")
    if (
        not isinstance(method_value, str)
        or not method_value
        or method_value != method_value.strip()
    ):
        return build_error_response(rpc_id, -32600, "Missing method")
    method = method_value
    try:
        parameters = resolve_jsonrpc_params_object(request_data.get("params", {}))
    except ValidationError as exception:
        return build_error_response(rpc_id, -32602, str(exception))
    effective_session_id = session_id or self.session.resolve_session_id(client_id)
    await self.session.update_session_activity(effective_session_id)
    pending_key: MCPServerPendingRequestKey | None = None
    if rpc_id is not None:
        pending_key = MCPServerPendingRequestKey(session_id=effective_session_id, rpc_id=rpc_id)
        async with self.pending_server_requests_lock:
            existing_task = self.pending_server_requests.get(pending_key)
            if existing_task is not None and not existing_task.done():
                return build_error_response(
                    rpc_id,
                    -32600,
                    f"Duplicate request ID: a request with id {rpc_id} is already pending",
                )
            task = create_ephemeral_task(
                _dispatch_method(
                    self,
                    method,
                    parameters,
                    client_id,
                    effective_session_id,
                    protocol_version,
                ),
            )
            self.pending_server_requests[pending_key] = task
    else:
        task = create_ephemeral_task(
            _dispatch_method(
                self,
                method,
                parameters,
                client_id,
                effective_session_id,
                protocol_version,
            ),
        )
    self.task_method_map[task] = method
    try:
        result = await task
        self.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_REQUESTS_HANDLED)
        return build_success_response(rpc_id, result)
    except asyncio.CancelledError:
        if not task.done():
            await cancel_and_await(
                [task],
                logger=logger,
                task_label="mcp server request task",
                timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            )
        self.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_REQUESTS_FAILED)
        return build_error_response(rpc_id, -32602, "Request cancelled")
    except MCPJSONRPCError as exception:
        self.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_REQUESTS_FAILED)
        return build_error_response(rpc_id, exception.rpc_code, exception.message, exception.data)
    except MCPError as exception:
        self.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_REQUESTS_FAILED)
        exception_data = exception.rpc_data
        return build_error_response(
            rpc_id,
            exception.rpc_code,
            exception.message,
            exception_data,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Unhandled error in MCP request handler",
            operation=OPERATION,
            details={"method": method, "client_id": client_id},
        )
        self.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_REQUESTS_FAILED)
        return build_error_response(rpc_id, -32603, "Internal error")
    finally:
        self.task_method_map.pop(task, None)
        if pending_key is not None:
            async with bounded_lock_for_cleanup(self.pending_server_requests_lock) as lock_result:
                if lock_result.acquired:
                    self.pending_server_requests.pop(pending_key, None)
        self.metrics_manager.record_timing(
            *MCP_SERVER_TIMING_REQUEST_LATENCY_MS,
            duration_ms=float(monotonic_ms() - start_time_ms),
        )


async def _dispatch_method(
    self: MCPServerDispatchSurface,
    method: str,
    parameters: JSONDict,
    client_id: str,
    session_id: str | None = None,
    protocol_version: str | None = None,
) -> JSONValue:
    token = self.context.set_active_client_context(client_id)
    user_id = self.session.get_session_user_id(session_id or client_id)
    user_id_token = self.context.set_active_user_id_context(user_id)
    try:
        if method == "initialize":
            return await handle_initialize(
                self,
                parameters,
                client_id,
                session_id=session_id,
                protocol_version=protocol_version,
            )
        if method in ("initialized", "notifications/initialized"):
            return None
        if method == "ping":
            return {}
        if method == "notifications/cancelled":
            resolved_session_id = session_id or client_id
            await handle_notification_cancelled(self, parameters, session_id=resolved_session_id)
            return None
        if method == "logging/setLevel":
            return await handle_logging_set_level(self, parameters, session_id or client_id)
        params_only_handler = resolve_server_mode_params_only_handler(method)
        if params_only_handler is not None:
            return await params_only_handler(self, parameters)
        client_handler = resolve_server_mode_client_handler(method)
        if client_handler is not None:
            return await client_handler(self, parameters, session_id or client_id)
        task_handler = resolve_task_method_handler(method)
        if task_handler is not None:
            return await task_handler(self, parameters, session_id or client_id)
        raise MCPJSONRPCError(-32601, f"Method not found: {method}")
    finally:
        self.context.reset_active_user_id_context(user_id_token)
        self.context.reset_active_client_context(token)
