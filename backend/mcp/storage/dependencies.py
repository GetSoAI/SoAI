"""SoAI - MCP storage dependencies [backend/mcp/storage/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.ipc.managed_worker import ManagedIpcWorkerDependencies
    from core.ipc.protocols import ManagedIpcWorkerProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("MCPStorageDependencies",)


@dataclass(frozen=True, slots=True)
class MCPStorageDependencies:
    database_files: DatabaseFilesProtocol
    event_bus: EventBusProtocol
    config: ConfigProtocol
    shutdown_event: asyncio.Event
    chroma_path: str
    managed_ipc_worker_builder: Callable[[ManagedIpcWorkerDependencies], ManagedIpcWorkerProtocol]
    storage_manager: StorageManagerProtocol
    task_registry: TaskRegistryProtocol
    metrics_manager: MetricsManagerProtocol
    embedding_timeout: int
    model_resolution_service: ModelResolutionServiceProtocol | None
    model_information_service: ModelInformationServiceProtocol | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPStorageDependencies",
            chroma_path=self.chroma_path,
            config=self.config,
            database_files=self.database_files,
            embedding_timeout=self.embedding_timeout,
            event_bus=self.event_bus,
            managed_ipc_worker_builder=self.managed_ipc_worker_builder,
            metrics_manager=self.metrics_manager,
            shutdown_event=self.shutdown_event,
            storage_manager=self.storage_manager,
            task_registry=self.task_registry,
        )
