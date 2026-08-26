"""SoAI - MCP protocol initialization handlers [backend/mcp/registry/initialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.mcp.protocol_versions import validate_protocol_version
from core.types.json_value import coerce_json_dict
from mcp.protocol.types import MCPClientSession, MCPJSONRPCError, MCPLoggingLevel
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "handle_initialize",
    "handle_logging_set_level",
)

LOGGER_NAME = "SoAI.mcp.registry.initialization"


async def handle_initialize(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
    client_id: str,
    session_id: str | None = None,
    protocol_version: str | None = None,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    effective_session_id = session_id or client_id
    parameter_protocol_version = parameters.get("protocolVersion")
    if parameter_protocol_version is not None and (not isinstance(parameter_protocol_version, str)):
        raise MCPJSONRPCError(
            -32602,
            f"Invalid protocolVersion type: {type(parameter_protocol_version).__name__}",
        )
    if parameter_protocol_version is None and protocol_version is None:
        raise MCPJSONRPCError(-32602, "Missing required parameter: protocolVersion")
    requested_version = (
        parameter_protocol_version if parameter_protocol_version is not None else protocol_version
    )
    is_version_valid, negotiated_version = validate_protocol_version(requested_version)
    if not is_version_valid:
        raise MCPJSONRPCError(-32602, f"Unsupported protocol version: {requested_version}")
    client_info_raw = parameters.get("clientInfo", {})
    client_info: JSONDict = coerce_json_dict(client_info_raw) or {}
    logger.info(
        "MCP client connected: %s (session=%s, protocol=%s)",
        client_info.get("name", "unknown"),
        effective_session_id,
        negotiated_version,
    )
    session_state = manager.state.session
    capabilities_value = parameters.get("capabilities", {})
    client_capabilities: JSONDict = coerce_json_dict(capabilities_value) or {}
    async with session_state.client_sessions_lock:
        existing = session_state.client_sessions.get(effective_session_id)
        if existing:
            if existing.client_id not in (effective_session_id, client_id):
                session_state.client_to_session.pop(existing.client_id, None)
            existing.client_id = client_id
            existing.protocol_version = negotiated_version
            existing.client_capabilities = client_capabilities
            existing.last_activity = time.monotonic()
        else:
            session = MCPClientSession(
                client_id=client_id,
                session_id=effective_session_id,
                protocol_version=negotiated_version,
            )
            session.client_capabilities = client_capabilities
            session_state.client_sessions[effective_session_id] = session
        if client_id != effective_session_id:
            session_state.client_to_session[client_id] = effective_session_id
    server_capabilities: JSONDict = {
        "tools": {"listChanged": manager.list_changed_enabled},
        "resources": {"subscribe": True, "listChanged": manager.list_changed_enabled},
        "prompts": {"listChanged": manager.list_changed_enabled},
        "logging": {},
        "completions": {},
    }
    if manager.tasks_enabled:
        server_capabilities["tasks"] = {
            "list": {},
            "cancel": {},
            "requests": {"tools": {"call": {}}},
        }
    return {
        "protocolVersion": negotiated_version,
        "capabilities": server_capabilities,
        "serverInfo": manager.host_mode.build_core_app_info(),
        "instructions": "SoAI provides unified access to multiple LLM backends and inference engines.",
    }


async def handle_logging_set_level(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    logging_level_name = manager.registration.get_argument(parameters, "level")
    try:
        level = MCPLoggingLevel(logging_level_name)
    except ValueError as exception:
        valid_levels = [logging_level.value for logging_level in MCPLoggingLevel]
        raise MCPJSONRPCError(
            -32602,
            f"Invalid logging level: {logging_level_name}. Valid levels: {valid_levels}",
        ) from exception
    session_state = manager.state.session
    async with session_state.client_sessions_lock:
        session = session_state.client_sessions.get(client_id)
        if session:
            session.logging_level = level
            logger.debug("Client %s set logging level to %s", client_id, level.value)
        else:
            session_state.client_sessions[client_id] = MCPClientSession(
                client_id=client_id,
                session_id=client_id,
                logging_level=level,
            )
            logger.debug(
                "Created session for client %s with logging level %s",
                client_id,
                level.value,
            )
    return {}
