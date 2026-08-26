"""SoAI - Database core public composition object [backend/database/core/core.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.database.protocols import (
    DatabaseFeatureGateProtocol,
    DatabaseReaderProtocol,
    DatabaseVacuumProtocol,
    DatabaseWriterProtocol,
)

__all__ = ("DatabaseCore",)


@dataclass(frozen=True, slots=True)
class DatabaseCore:
    reader: DatabaseReaderProtocol
    writer: DatabaseWriterProtocol
    vacuum: DatabaseVacuumProtocol
    features: DatabaseFeatureGateProtocol
