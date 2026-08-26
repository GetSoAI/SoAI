"""SoAI - MCP RAG config error mapping [backend/mcp/handlers/tools/rag_config_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from mcp.protocol.types import MCPJSONRPCError

__all__ = ("build_stored_rag_config_mcp_error",)


def build_stored_rag_config_mcp_error(
    field_name: str,
    exception: ValidationError,
) -> MCPJSONRPCError:
    if field_name == "enabled":
        return MCPJSONRPCError(-32603, str(exception))
    return MCPJSONRPCError(-32603, f"Invalid stored RAG {field_name}")
