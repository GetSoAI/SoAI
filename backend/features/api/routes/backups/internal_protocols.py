"""SoAI - Backup routes internal protocols [backend/features/api/routes/backups/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol

__all__ = ("BackupTaskStarterProtocol",)


class BackupTaskStarterProtocol(Protocol):
    def __call__(self, backup_id: str, *, user_id: int) -> Awaitable[str]: ...
