"""SoAI - Internal protocols for task repository helpers [backend/database/repositories/tasks/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from cryptography.fernet import Fernet

from core.database.protocols import DatabaseCoreProtocol
from core.mutations.storage_composition import MutationStorageComposition

__all__ = (
    "DatabaseTasksCoreAndSecretsOwnerProtocol",
    "DatabaseTasksQueueCoreOwnerProtocol",
)


class DatabaseTasksQueueCoreOwnerProtocol(Protocol):
    @property
    def core(self) -> DatabaseCoreProtocol: ...

    @property
    def mutation_storage(self) -> MutationStorageComposition | None: ...


class DatabaseTasksCoreAndSecretsOwnerProtocol(DatabaseTasksQueueCoreOwnerProtocol, Protocol):
    @property
    def fernets(self) -> tuple[Fernet, ...]: ...
