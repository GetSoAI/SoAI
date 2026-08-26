"""SoAI - MCP protocol type definitions [backend/mcp/protocol/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, override

from core.errors.external_service_exception import MCPError
from core.errors.messages import resolve_error_message
from core.mcp.protocol_versions import DEFAULT_NEGOTIATED_PROTOCOL_VERSION
from core.timing.epoch import epoch_seconds_float
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from collections import deque
    from collections.abc import Awaitable, Callable

    type ToolHandler = Callable[[JSONDict], Awaitable[JSONValue]]
    type ResourceHandler = Callable[[], Awaitable[JSONDict]]
    type PromptHandler = Callable[[JSONDict], Awaitable[JSONDict]]
    type JsonRpcId = str | int | None
    type SSEReplayBuffer = deque[tuple[int, JSONDict]]

__all__ = (
    "MCPClientSession",
    "MCPJSONRPCError",
    "MCPLoggingLevel",
    "MCPServerConfig",
    "MCPServerStatus",
    "MCPTransportType",
)


class MCPTransportType(str, Enum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


class MCPServerStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"
    AUTH_REQUIRED = "auth_required"


class MCPJSONRPCError(MCPError):
    code: str | int

    def __init__(
        self,
        rpc_code: int,
        message: str,
        data: JSONValue | None = None,
        *,
        operation: str | None = None,
        cause: BaseException | None = None,
        trace_id: str | None = None,
    ) -> None:
        resolved_message = resolve_error_message(message, default_message="MCP request failed.")
        super().__init__(
            resolved_message,
            rpc_code=int(rpc_code),
            rpc_data=data,
            operation=operation,
            cause=cause,
            trace_id=trace_id,
        )
        self.code = int(rpc_code)
        self.data = data

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (
            (self.rpc_code, self.message, self.data),
            {"operation": self.operation, "cause": self.cause, "trace_id": self.trace_id},
        )


class MCPLoggingLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    ALERT = "alert"
    EMERGENCY = "emergency"


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    id: str
    name: str
    transport_type: MCPTransportType
    endpoint: str
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    auth_type: str = "none"
    api_key_encrypted: str | None = None
    oauth_status: str = "none"
    oauth_client_id: str | None = None
    oauth_client_secret_encrypted: str | None = None
    oauth_access_token_encrypted: str | None = None
    oauth_refresh_token_encrypted: str | None = None
    oauth_expires_at_ms: int | None = None
    oauth_resource_metadata_url: str | None = None
    oauth_auth_server_issuer: str | None = None
    oauth_authorization_endpoint: str | None = None
    oauth_token_endpoint: str | None = None
    oauth_registration_endpoint: str | None = None
    oauth_token_endpoint_auth_method: str | None = None
    oauth_scopes: tuple[str, ...] | None = None
    oauth_required_scopes: tuple[str, ...] | None = None
    timeout_sec: int = 30
    auto_reconnect: bool = True
    enabled: bool = True


class MCPClientSession:
    __slots__ = (
        "client_capabilities",
        "client_id",
        "conv_id",
        "created_at",
        "last_activity",
        "logging_level",
        "protocol_version",
        "session_id",
        "user_id",
    )

    def __init__(
        self,
        client_id: str,
        session_id: str,
        conv_id: str | None = None,
        user_id: int = 0,
        protocol_version: str = DEFAULT_NEGOTIATED_PROTOCOL_VERSION,
        logging_level: MCPLoggingLevel = MCPLoggingLevel.WARNING,
    ) -> None:
        self.client_id = client_id
        self.session_id = session_id
        self.conv_id = conv_id
        self.user_id = user_id
        self.protocol_version = protocol_version
        self.logging_level = logging_level
        self.created_at = epoch_seconds_float()
        self.last_activity = time.monotonic()
        self.client_capabilities: JSONDict = {}
