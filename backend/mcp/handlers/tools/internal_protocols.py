"""SoAI - MCP tool handler internal protocols [backend/mcp/handlers/tools/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.config.protocols import ConfigProtocol

if TYPE_CHECKING:
    from core.files.protocols import DatabaseFilesProtocol

__all__ = (
    "RagServiceProtocol",
    "RetrievalParamsSourceProtocol",
)


class RagServiceProtocol(Protocol):
    config: ConfigProtocol


class RetrievalParamsSourceProtocol(Protocol):
    config: ConfigProtocol
    database_files: DatabaseFilesProtocol
