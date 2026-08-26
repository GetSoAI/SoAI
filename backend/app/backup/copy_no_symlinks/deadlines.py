"""SoAI - Backup copy deadline helpers [backend/app/backup/copy_no_symlinks/deadlines.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.deadlines import is_deadline_expired
from core.errors.exceptions import StateError

__all__ = ("check_deadline",)


def check_deadline(deadline_monotonic: float | None, *, context: str) -> None:
    if deadline_monotonic is None:
        return
    if is_deadline_expired(deadline_monotonic):
        raise StateError(
            "Copy operation exceeded deadline.",
            details={
                "context": context,
                "deadline_monotonic": deadline_monotonic,
            },
            operation="utils_backup.copy",
        )
