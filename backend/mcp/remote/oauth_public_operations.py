"""SoAI - MCP remote OAuth public operations [backend/mcp/remote/oauth_public_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from mcp.remote.internal_protocols import MCPRemoteOAuthOperationsSurface
from mcp.remote.service_oauth_authorization_operations import (
    connect_to_server_by_id_method,
    start_oauth_authorization_method,
)
from mcp.remote.service_oauth_callback_operations import complete_oauth_callback_method
from mcp.remote.service_oauth_client_metadata_operations import (
    build_oauth_client_metadata_document_method,
)

__all__ = ("MCPRemoteOAuthOperations",)


class MCPRemoteOAuthOperations:
    async def connect_to_server_by_id(
        self: MCPRemoteOAuthOperationsSurface,
        server_id: str,
    ) -> bool:
        return await connect_to_server_by_id_method(self, server_id)

    async def start_oauth_authorization(
        self: MCPRemoteOAuthOperationsSurface,
        *,
        server_id: str,
        user_id: int,
    ) -> JSONDict:
        return await start_oauth_authorization_method(
            self,
            server_id=server_id,
            user_id=user_id,
        )

    async def complete_oauth_callback(
        self: MCPRemoteOAuthOperationsSurface,
        *,
        code: str,
        state_token: str,
        user_id: int,
    ) -> JSONDict:
        return await complete_oauth_callback_method(
            self,
            code=code,
            state_token=state_token,
            user_id=user_id,
        )

    def build_oauth_client_metadata_document(self: MCPRemoteOAuthOperationsSurface) -> JSONDict:
        return build_oauth_client_metadata_document_method(self)
