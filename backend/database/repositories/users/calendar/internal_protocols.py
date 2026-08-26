"""SoAI - Calendar repository internal protocols [backend/database/repositories/users/calendar/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.database.protocols import DatabaseCoreProtocol

__all__ = ("DatabaseCalendarCoreOwnerProtocol",)


class DatabaseCalendarCoreOwnerProtocol(Protocol):
    core: DatabaseCoreProtocol
