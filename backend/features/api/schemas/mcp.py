"""SoAI - MCP request/response schemas [backend/features/api/schemas/mcp.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr

from core.mcp.server_write_fields import (
    MCP_SERVER_TIMEOUT_DEFAULT_MS,
    MCP_SERVER_TIMEOUT_MAX_MS,
    MCP_SERVER_TIMEOUT_MIN_MS,
)
from core.meta.soai_v1 import SoAIV1StrictModel
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = (
    "MCPHostInteractionResolve",
    "MCPHostRootsUpdate",
    "MCPServerCreate",
    "MCPServerUpdate",
)


class MCPServerCreate(SoAIV1StrictModel):
    name: StrictStr = Field(..., min_length=1, max_length=128)
    transport_type: StrictStr = Field(..., pattern="^(stdio|streamable_http)$")
    endpoint: StrictStr = Field(..., min_length=1)
    args: list[StrictStr] | None = None
    env: dict[str, StrictStr] | None = None
    headers: dict[str, StrictStr] | None = None
    api_key: StrictStr | None = None
    timeout_ms: StrictInt = Field(
        default=MCP_SERVER_TIMEOUT_DEFAULT_MS,
        ge=MCP_SERVER_TIMEOUT_MIN_MS,
        le=MCP_SERVER_TIMEOUT_MAX_MS,
    )
    auto_reconnect: StrictBool = True


class MCPServerUpdate(SoAIV1StrictModel):
    name: StrictStr | None = Field(default=None, min_length=1, max_length=128)
    transport_type: StrictStr | None = Field(default=None, pattern="^(stdio|streamable_http)$")
    endpoint: StrictStr | None = Field(default=None, min_length=1)
    args: list[StrictStr] | None = None
    env: dict[str, StrictStr] | None = None
    headers: dict[str, StrictStr] | None = None
    auth_type: Literal["none", "api_key", "oauth"] | None = None
    api_key: StrictStr | None = None
    oauth_client_id: StrictStr | None = None
    oauth_client_secret: StrictStr | None = None
    timeout_ms: StrictInt | None = Field(
        default=None,
        ge=MCP_SERVER_TIMEOUT_MIN_MS,
        le=MCP_SERVER_TIMEOUT_MAX_MS,
    )
    auto_reconnect: StrictBool | None = None
    enabled: StrictBool | None = None


class MCPHostInteractionResolve(SoAIV1StrictModel):
    action: Literal["approve", "accept", "decline", "cancel"]
    content: dict[str, PydanticJSONValue] | None = None


class MCPHostRootsUpdate(SoAIV1StrictModel):
    roots: list[StrictStr | dict[str, PydanticJSONValue]]
