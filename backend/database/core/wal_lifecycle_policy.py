"""SoAI - SQLite WAL lifecycle configuration policy [backend/database/core/wal_lifecycle_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.sqlite.policy import SQLITE_JOURNAL_SIZE_LIMIT_BYTES

__all__ = (
    "ANCHOR_READ_SQL",
    "USER_VERSION_READ_SQL",
    "WalLifecycleDependencies",
)

ANCHOR_READ_SQL = "PRAGMA user_version;"
USER_VERSION_READ_SQL = "PRAGMA user_version;"


@dataclass(frozen=True, slots=True)
class WalLifecycleDependencies:
    db_path: str
    is_shared_memory_mode: bool
    connect_timeout: float
    write_pragmas: tuple[str, ...]
    publish_connection: Callable[[sqlite3.Connection | None], None]
    rotation_size_bytes: int = SQLITE_JOURNAL_SIZE_LIMIT_BYTES
    rotation_check_interval_sec: float = 1.0
    rotation_busy_retry_interval_sec: float = 60.0

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WalLifecycleDependencies",
            connect_timeout=self.connect_timeout,
            db_path=self.db_path,
            is_shared_memory_mode=self.is_shared_memory_mode,
            publish_connection=self.publish_connection,
            rotation_busy_retry_interval_sec=self.rotation_busy_retry_interval_sec,
            rotation_check_interval_sec=self.rotation_check_interval_sec,
            rotation_size_bytes=self.rotation_size_bytes,
            write_pragmas=self.write_pragmas,
        )
        if self.rotation_size_bytes <= 0:
            raise ValueError("WAL lifecycle rotation size must be positive.")
        if self.rotation_check_interval_sec < 0.0:
            raise ValueError("WAL lifecycle rotation check interval cannot be negative.")
        if self.rotation_busy_retry_interval_sec <= 0.0:
            raise ValueError("WAL lifecycle busy retry interval must be positive.")
