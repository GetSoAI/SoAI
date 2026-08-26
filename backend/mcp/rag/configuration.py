"""SoAI - MCP RAG configuration helpers [backend/mcp/rag/configuration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.rag.config_metadata import parse_rag_config_metadata_value
from core.rag.parameter_validation import validate_chunking_window

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import (
        MCPRAGInternalProtocol,
        MCPRAGSearchContextProtocol,
    )

__all__ = (
    "get_rag_config_metadata",
    "validate_chunking_params",
)


def validate_chunking_params(
    self: MCPRAGInternalProtocol,
    chunk_size: int,
    chunk_overlap: int,
    chunking_strategy: str,
    file_type: str | None = None,
) -> None:
    validate_chunking_window(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_strategy=chunking_strategy,
    )
    if file_type is not None and file_type not in self.worker.parsers:
        raise ValidationError(
            f"Unsupported file type: {file_type}. Supported types: {list(self.worker.parsers.keys())}",
        )


async def get_rag_config_metadata(self: MCPRAGSearchContextProtocol, conv_id: str) -> JSONDict:
    config = await self.database_files.get_rag_config(conv_id)
    if not config:
        return {}
    return parse_rag_config_metadata_value(config.get("config_metadata"))
