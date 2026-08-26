"""SoAI - Database path validation and normalization [backend/database/core/paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.errors.exceptions import ConfigurationError

__all__ = (
    "DatabasePaths",
    "resolve_database_paths",
)


@dataclass(frozen=True, slots=True)
class DatabasePaths:
    db_path: str
    is_shared_memory_mode: bool
    db_file_paths: tuple[str, str, str]


def resolve_database_paths(db_path: str) -> DatabasePaths:
    if db_path is None:
        raise ConfigurationError("Database path cannot be None.")
    if isinstance(db_path, os.PathLike):
        db_path = os.fspath(db_path)
    if not isinstance(db_path, str) or not db_path.strip():
        raise ConfigurationError("Database path must be a non-empty string.")
    if db_path == ":memory:":
        resolved_db_path = "file::memory:?cache=shared"
        is_shared_memory_mode = True
    else:
        resolved_db_path = os.path.normpath(db_path)
        is_shared_memory_mode = False
    return DatabasePaths(
        db_path=resolved_db_path,
        is_shared_memory_mode=is_shared_memory_mode,
        db_file_paths=(
            resolved_db_path,
            f"{resolved_db_path}-wal",
            f"{resolved_db_path}-shm",
        ),
    )
