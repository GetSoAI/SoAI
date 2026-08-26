"""SoAI - MCP request cancellation handlers [backend/mcp/registry/cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol
from mcp.server.state import MCPServerPendingRequestKey

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_notification_cancelled",)

LOGGER_NAME = "SoAI.mcp.registry.cancellation"


async def handle_notification_cancelled(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
    *,
    session_id: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not session_id:
        return
    rpc_id = parameters.get("rpc_id")
    if rpc_id is None:
        rpc_id = parameters.get("rpcId")
    if rpc_id is None:
        return
    if not isinstance(rpc_id, str | int) or isinstance(rpc_id, bool):
        logger.warning("Invalid rpc_id type in notifications/cancelled: %s", type(rpc_id).__name__)
        return
    request_key = MCPServerPendingRequestKey(session_id=session_id, rpc_id=rpc_id)
    async with manager.pending_server_requests_lock:
        task = manager.pending_server_requests.get(request_key)
        if task is None:
            return
        if manager.task_method_map.get(task) == "initialize":
            logger.warning(
                "Client attempted to cancel initialize request (not allowed per MCP spec)",
            )
            return
        manager.pending_server_requests.pop(request_key, None)
    if not task.done():
        task.cancel()
    logger.debug(
        "Cancelled pending request %s: %s",
        rpc_id,
        parameters.get("reason", "Client cancelled request"),
    )
