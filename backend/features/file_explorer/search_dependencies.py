"""SoAI - File explorer search service dependencies [backend/features/file_explorer/search_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies

__all__ = ("FileExplorerSearchServiceDependencies",)


@dataclass(frozen=True, slots=True)
class FileExplorerSearchServiceDependencies:
    config: ConfigProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerSearchServiceDependencies",
            config=self.config,
        )
