"""SoAI - Input parsing and validation helpers for MCP RAG tools [backend/mcp/handlers/tools/inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.rag.config_values import RagConfigDefaults, resolve_rag_config_defaults
from core.rag.tool_parameters import resolve_rag_ingest_params
from mcp.handlers.tools.internal_protocols import RagServiceProtocol
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "extract_ingest_params",
    "rag_config_defaults",
)


def rag_config_defaults(rag: RagServiceProtocol) -> RagConfigDefaults:
    return resolve_rag_config_defaults(rag.config)


def extract_ingest_params(rag: RagServiceProtocol, arguments: JSONDict) -> dict[str, JSONValue]:
    try:
        return resolve_rag_ingest_params(
            defaults=rag_config_defaults(rag),
            arguments=arguments,
        )
    except ValidationError as exception:
        raise MCPJSONRPCError(-32602, str(exception)) from exception
