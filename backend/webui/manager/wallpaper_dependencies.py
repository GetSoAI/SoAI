"""SoAI - WallpaperManager dependencies dataclass [backend/webui/manager/wallpaper_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.files.protocols import FilesPathResolverProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TokenCollectionProtocol,
)

__all__ = ("WallpaperManagerDependencies",)


@dataclass(frozen=True, slots=True)
class WallpaperManagerDependencies:
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    storage_manager: StorageManagerProtocol
    token_collection: TokenCollectionProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WallpaperManagerDependencies",
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            config=self.config,
            files=self.files,
            runtime_flags=self.runtime_flags,
            storage_manager=self.storage_manager,
            token_collection=self.token_collection,
        )
