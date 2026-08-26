"""SoAI - Protected SQLite runtime file path checks [backend/core/files/protected_sqlite_runtime_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import SecurityError

__all__ = (
    "ensure_directory_excludes_protected_sqlite_runtime_files",
    "ensure_not_protected_sqlite_runtime_file",
)

_SQLITE_RUNTIME_SUFFIXES: tuple[str, ...] = ("", "-wal", "-shm", "-journal")


def ensure_not_protected_sqlite_runtime_file(
    candidate_path: str,
    database_path: str | None,
    *,
    operation: str,
) -> None:
    for protected_path in _protected_sqlite_runtime_paths(database_path):
        if _is_same_path(candidate_path, protected_path):
            raise SecurityError(
                "Refusing to mutate live SQLite runtime file.",
                operation=operation,
            )


def ensure_directory_excludes_protected_sqlite_runtime_files(
    candidate_path: str,
    database_path: str | None,
    *,
    operation: str,
) -> None:
    candidate_normalized = _normalize_path(candidate_path)
    for protected_path in _protected_sqlite_runtime_paths(database_path):
        if _is_path_within_directory(candidate_normalized, protected_path):
            raise SecurityError(
                "Refusing to mutate directory containing live SQLite runtime files.",
                operation=operation,
            )


def _protected_sqlite_runtime_paths(database_path: str | None) -> tuple[str, ...]:
    if database_path is None:
        return ()
    trimmed = database_path.strip()
    if not trimmed or trimmed == ":memory:" or trimmed.startswith("file:"):
        return ()
    base_path = _normalize_path(trimmed)
    return tuple(f"{base_path}{suffix}" for suffix in _SQLITE_RUNTIME_SUFFIXES)


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _is_same_path(left_path: str, right_path: str) -> bool:
    return _normalize_path(left_path) == _normalize_path(right_path)


def _is_path_within_directory(directory_path: str, candidate_path: str) -> bool:
    try:
        return os.path.commonpath([directory_path, candidate_path]) == directory_path
    except ValueError:
        return False
