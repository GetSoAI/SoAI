"""SoAI - MCP management server row loading [backend/features/api/routes/mcp/routes/management_server_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request

from core.errors.exceptions import StateError, ValidationError
from core.mcp.server_config_normalization import (
    normalize_server_config_row,
    require_valid_server_id,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)

if TYPE_CHECKING:
    from core.mcp.protocols_storage import MCPServerConfigProtocol
    from core.types.json import JSONDict

__all__ = (
    "coerce_mcp_server_config_or_raise",
    "load_mcp_server_row_or_raise",
    "require_server_id_or_raise",
)


def require_server_id_or_raise(request: Request, server_id: str) -> str:
    try:
        return require_valid_server_id(server_id)
    except StateError:
        raise_invalid_request(request, "Invalid MCP server id.")


def coerce_mcp_server_config_or_raise(
    request: Request,
    server_row: JSONDict,
) -> MCPServerConfigProtocol:
    try:
        return normalize_server_config_row(server_row)
    except (StateError, ValidationError) as exception:
        raise_server_error(request, str(exception), error_type="invalid_server_state")


async def load_mcp_server_row_or_raise(
    request: Request,
    api_context: ApiContext,
    *,
    server_id: str,
    decrypt_key: bool,
) -> tuple[str, JSONDict]:
    normalized_server_id = require_server_id_or_raise(request, server_id)
    try:
        server_row = await api_context.dependencies.database_mcp.get_mcp_server(
            normalized_server_id,
            decrypt_key=decrypt_key,
        )
    except (StateError, ValidationError) as exception:
        raise_server_error(request, str(exception), error_type="invalid_server_state")
    if not server_row:
        raise_not_found(request, f"MCP server '{normalized_server_id}' not found.")
    return normalized_server_id, server_row
