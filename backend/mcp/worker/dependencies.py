"""SoAI - MCP worker dependencies [backend/mcp/worker/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.di.validation import require_dependencies
from mcp.shared.worker_dependencies_base import MCPWorkerCoreDependencies

if TYPE_CHECKING:
    from mcp.storage.internal_protocols import MCPStorageProtocol

__all__ = ("MCPWorkerDependencies",)


@dataclass(frozen=True, slots=True)
class MCPWorkerDependencies(MCPWorkerCoreDependencies):
    storage: MCPStorageProtocol

    @override
    def __post_init__(self) -> None:
        MCPWorkerCoreDependencies.__post_init__(self)
        require_dependencies(
            owner="MCPWorkerDependencies",
            storage=self.storage,
        )
