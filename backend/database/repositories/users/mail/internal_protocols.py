"""SoAI - Mail repository internal protocols [backend/database/repositories/users/mail/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.database.protocols import DatabaseCoreProtocol

__all__ = ("DatabaseMailCoreOwnerProtocol",)


class DatabaseMailCoreOwnerProtocol(Protocol):
    core: DatabaseCoreProtocol
