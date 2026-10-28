"""SoAI - Shared lock outcome types [backend/core/concurrency/lock_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("BoundedLockResult", "LockHolderSnapshot")


@dataclass(slots=True)
class BoundedLockResult:
    acquired: bool


@dataclass(frozen=True, slots=True)
class LockHolderSnapshot:
    task_name: str | None
    held_seconds: float
