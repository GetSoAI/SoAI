"""SoAI - MCP remote OAuth authorization error handling [backend/mcp/remote/oauth_auth_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.external_accounts.oauth_updates import build_oauth_auth_error_updates
from core.mcp.protocols_storage import DatabaseMCPProtocol
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from mcp.protocol.types import MCPServerStatus

__all__ = ("extract_mcp_auth_error_details", "persist_mcp_oauth_auth_error")


def extract_mcp_auth_error_details(
    details: JSONDict | None,
    *,
    default_status: int,
) -> tuple[int, str | None]:
    auth_details = details or {}
    status_value = auth_details.get("status_code")
    status_code = int(status_value) if is_strict_int(status_value) else default_status
    www_value = auth_details.get("www_authenticate")
    www_authenticate = www_value if isinstance(www_value, str) else None
    return status_code, www_authenticate


async def persist_mcp_oauth_auth_error(
    db_mcp: DatabaseMCPProtocol,
    *,
    server_id: str,
    status_code: int,
    www_authenticate: str | None,
    auth_type: str,
) -> None:
    error_message: str
    updates: JSONDict = {}
    if auth_type == "oauth":
        updates, error_message = build_oauth_auth_error_updates(
            status_code=status_code,
            www_authenticate=www_authenticate,
        )
    else:
        error_message = f"HTTP {status_code} authorization error."
    if updates:
        await db_mcp.update_mcp_server(server_id, updates)
    await db_mcp.update_mcp_server_status(
        server_id,
        MCPServerStatus.AUTH_REQUIRED.value,
        error_message,
    )
