"""SoAI - Database repository dependency dataclasses [backend/database/repositories/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.mutations.storage_composition import MutationStorageComposition
from core.plugins.protocols_instance import FilesProtocol

__all__ = ("DatabaseRepositoryDependencies",)


@dataclass(frozen=True, slots=True)
class DatabaseRepositoryDependencies:
    core: DatabaseCoreProtocol
    config: ConfigProtocol
    fernet: tuple[Fernet, ...]
    event_bus: EventBusProtocol | None = None
    files: FilesProtocol | None = None
    mutation_storage: MutationStorageComposition | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DatabaseRepositoryDependencies",
            config=self.config,
            core=self.core,
            fernet=self.fernet,
        )
        if self.files is not None:
            require_dependencies(owner="DatabaseRepositoryDependencies", files=self.files)
