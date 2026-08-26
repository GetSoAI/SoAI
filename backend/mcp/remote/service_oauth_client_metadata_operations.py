"""SoAI - MCP remote OAuth client metadata operations [backend/mcp/remote/service_oauth_client_metadata_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.oauth.management_urls import build_mcp_oauth_urls, resolve_oauth_public_origin
from core.types.json import JSONDict
from mcp.remote.internal_protocols import MCPRemoteOAuthOperationsSurface

__all__ = ("build_oauth_client_metadata_document_method",)


def build_oauth_client_metadata_document_method(self: MCPRemoteOAuthOperationsSurface) -> JSONDict:
    normalized = resolve_oauth_public_origin(str(self.public_origin or ""))
    callback_url, client_id = build_mcp_oauth_urls(normalized)
    return {
        "client_id": client_id,
        "client_name": "SoAI MCP Client",
        "client_uri": normalized,
        "redirect_uris": [callback_url],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
