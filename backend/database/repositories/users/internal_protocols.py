"""SoAI - Database repositories user internal protocols [backend/database/repositories/users/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.database.protocols import DatabaseCoreProtocol

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.plugins.protocols_instance import FilesProtocol
    from core.types.json import JSONValue

__all__ = (
    "DatabaseCoreOwnerProtocol",
    "DatabaseDomainEventOwnerProtocol",
    "DatabaseMessagesCoreOwnerProtocol",
    "DatabaseMessagesStorageOwnerProtocol",
    "EpochMsReaderProtocol",
)


class DatabaseCoreOwnerProtocol(Protocol):
    core: DatabaseCoreProtocol


class DatabaseMessagesCoreOwnerProtocol(Protocol):
    core: DatabaseCoreProtocol


class DatabaseDomainEventOwnerProtocol(DatabaseMessagesCoreOwnerProtocol, Protocol):
    event_bus: EventBusProtocol | None


class DatabaseMessagesStorageOwnerProtocol(DatabaseMessagesCoreOwnerProtocol, Protocol):
    storage_root: str | None
    files: FilesProtocol | None


class EpochMsReaderProtocol(Protocol):
    def __call__(
        self,
        value: JSONValue | int | None,
        *,
        label: str = "timestamp",
    ) -> int | None: ...
