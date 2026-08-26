"""SoAI - Internal protocols for files repository helpers [backend/database/repositories/files/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.database.protocols import DatabaseCoreProtocol

__all__ = (
    "DatabaseFilesCatalogProtocol",
    "DatabaseFilesRagProtocol",
)


class DatabaseFilesCatalogProtocol(Protocol):
    core: DatabaseCoreProtocol


class DatabaseFilesRagProtocol(Protocol):
    core: DatabaseCoreProtocol
