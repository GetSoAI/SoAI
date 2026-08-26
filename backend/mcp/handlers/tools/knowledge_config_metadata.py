"""SoAI - RAG knowledge config metadata normalization [backend/mcp/handlers/tools/knowledge_config_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.rag.config_metadata import normalize_rag_config_metadata
from core.types.json_value import filter_json_mapping
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("apply_knowledge_config_metadata_values",)


def apply_knowledge_config_metadata_values(result: JSONDict, *, metadata: JSONDict) -> None:
    try:
        result.update(filter_json_mapping(normalize_rag_config_metadata(metadata)))
    except ValidationError as exception:
        raise MCPJSONRPCError(-32603, str(exception)) from exception
