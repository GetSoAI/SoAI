"""SoAI - Database repositories plugin internal protocols [backend/database/repositories/plugins/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.database.protocols import DatabaseCoreProtocol
    from core.events.protocols import EventBusProtocol

__all__ = (
    "DatabasePluginsBackendVariantCountSurface",
    "DatabasePluginsProviderMethodsSurface",
    "DatabasePluginsRuntimeProcessesSurface",
)


class DatabasePluginsProviderMethodsSurface(Protocol):
    core: DatabaseCoreProtocol
    event_bus: EventBusProtocol | None
    fernet: tuple[Fernet, ...]


class DatabasePluginsRuntimeProcessesSurface(Protocol):
    core: DatabaseCoreProtocol


class DatabasePluginsBackendVariantCountSurface(Protocol):
    core: DatabaseCoreProtocol
