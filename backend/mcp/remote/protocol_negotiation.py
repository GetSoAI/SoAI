"""SoAI - MCP remote protocol negotiation [backend/mcp/remote/protocol_negotiation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.protocol_versions import MCP_PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS
from core.serialization.json import normalize_for_json
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.jsonrpc import (
    build_core_app_info,
    build_jsonrpc_notification,
    get_preferred_protocol_versions,
    is_protocol_version_error,
)
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.mcp.protocols_storage import DatabaseMCPProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MCPProtocolNegotiator",
    "MCPProtocolNegotiatorDependencies",
)

LOGGER_NAME = "SoAI.mcp.remote.protocol_negotiation"
OPERATION = "mcp.remote.persist_capabilities"


@dataclass(frozen=True, slots=True)
class MCPProtocolNegotiatorDependencies:
    db_mcp: DatabaseMCPProtocol
    decrypt_api_key: Callable[[str], str | None]
    build_client_capabilities: Callable[[], JSONDict]
    send_host_mode_message: Callable[[MCPServerConnection, JSONDict], Awaitable[None]]
    protocol_version: str = MCP_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPProtocolNegotiatorDependencies",
            build_client_capabilities=self.build_client_capabilities,
            db_mcp=self.db_mcp,
            decrypt_api_key=self.decrypt_api_key,
            protocol_version=self.protocol_version,
            send_host_mode_message=self.send_host_mode_message,
        )


class MCPProtocolNegotiator:

    def __init__(self, deps: MCPProtocolNegotiatorDependencies) -> None:
        self._db_mcp = deps.db_mcp
        self._build_client_capabilities = deps.build_client_capabilities
        self._send_host_mode_message = deps.send_host_mode_message
        self._protocol_version = deps.protocol_version

    def build_initialize_params(self, protocol_version: str | None = None) -> JSONDict:
        effective_version = protocol_version or self._protocol_version
        if effective_version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise MCPJSONRPCError(-32602, f"Unsupported protocol version: {effective_version}")
        return {
            "protocolVersion": effective_version,
            "supportedProtocolVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
            "capabilities": self._build_client_capabilities(),
            "clientInfo": build_core_app_info(),
        }

    async def initialize_connection(
        self,
        connection: MCPServerConnection,
        request_sender: Callable[[str, JSONDict], Awaitable[JSONValue | None]],
    ) -> bool:
        logger = get_logger(LOGGER_NAME)
        init_response: JSONDict | None = None
        negotiated: str | None = None
        last_error: MCPJSONRPCError | None = None
        for version in get_preferred_protocol_versions():
            try:
                candidate = await request_sender(
                    "initialize",
                    self.build_initialize_params(version),
                )
            except MCPJSONRPCError as exception:
                if is_protocol_version_error(exception):
                    last_error = exception
                    continue
                raise
            if candidate and isinstance(candidate, dict):
                init_response = candidate
                negotiated_value = candidate.get("protocolVersion")
                if not isinstance(negotiated_value, str):
                    raise MCPJSONRPCError(
                        -32602,
                        "Initialize response missing protocolVersion.",
                    )
                if negotiated_value not in SUPPORTED_PROTOCOL_VERSIONS:
                    raise MCPJSONRPCError(
                        -32602,
                        f"Unsupported negotiated protocol version: {negotiated_value}",
                    )
                negotiated = negotiated_value
                break
        if not init_response or not negotiated:
            if last_error:
                logger.warning(
                    "Failed to negotiate MCP protocol with %s: %s",
                    connection.config.name,
                    last_error.message,
                )
            return False
        connection.protocol_version = negotiated
        capabilities_value = init_response.get("capabilities")
        connection.capabilities = (
            capabilities_value if isinstance(capabilities_value, dict) else None
        )
        await self._persist_capabilities(connection)
        notification = build_jsonrpc_notification("notifications/initialized", {})
        notification_payload: JSONDict = (
            dict(notification) if isinstance(notification, dict) else {}
        )
        await self._send_host_mode_message(connection, notification_payload)
        connection.tools = await self._fetch_all_pages(
            request_sender,
            connection.config.name,
            "tools/list",
            "tools",
        )
        connection.resources = await self._fetch_all_pages(
            request_sender,
            connection.config.name,
            "resources/list",
            "resources",
        )
        if isinstance(connection.capabilities, dict) and "prompts" in connection.capabilities:
            connection.prompts = await self._fetch_all_pages(
                request_sender,
                connection.config.name,
                "prompts/list",
                "prompts",
            )
        else:
            connection.prompts = []
        connection.task_state.initialized = True
        logger.info(
            "Negotiated MCP protocol %s with %s",
            negotiated,
            connection.config.name,
        )
        return True

    async def _persist_capabilities(self, connection: MCPServerConnection) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            persisted_capabilities = (
                connection.capabilities if isinstance(connection.capabilities, dict) else None
            )
            await self._db_mcp.update_mcp_server_capabilities(
                connection.config.id,
                persisted_capabilities,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to persist MCP server capabilities (non-critical).",
                operation=OPERATION,
                details={"server_name": connection.config.name},
                level="debug",
            )

    async def _fetch_all_pages(
        self,
        request_sender: Callable[[str, JSONDict], Awaitable[JSONValue | None]],
        server_name: str,
        method: str,
        key: str,
    ) -> list[JSONDict]:
        logger = get_logger(LOGGER_NAME)
        all_items: list[JSONDict] = []
        cursor: str | None = None
        page = 0
        while page < 100:
            page += 1
            params: JSONDict = {"cursor": cursor} if cursor else {}
            result = await request_sender(method, params)
            if not result or not isinstance(result, dict):
                break
            items_value = result.get(key)
            if isinstance(items_value, list):
                for item in items_value:
                    if isinstance(item, dict):
                        normalized = normalize_for_json(item)
                        if isinstance(normalized, dict):
                            all_items.append(normalized)
            cursor_value = result.get("nextCursor")
            cursor = cursor_value if isinstance(cursor_value, str) else None
            if not cursor:
                break
        if page >= 100:
            logger.warning("Pagination limit reached for %s on %s", method, server_name)
        return all_items
