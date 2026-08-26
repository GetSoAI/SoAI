"""SoAI - SQLite runtime version safety contract [backend/core/sqlite/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConfigurationError

__all__ = (
    "MINIMUM_SAFE_SQLITE_VERSION",
    "require_safe_sqlite_runtime",
)

MINIMUM_SAFE_SQLITE_VERSION: tuple[int, int, int] = (3, 51, 3)


def _format_sqlite_version(version: tuple[int, ...]) -> str:
    return ".".join(str(component) for component in version)


def require_safe_sqlite_runtime() -> None:
    installed_version = tuple(int(component) for component in sqlite3.sqlite_version_info)
    if installed_version >= MINIMUM_SAFE_SQLITE_VERSION:
        return
    installed_version_text = _format_sqlite_version(installed_version)
    minimum_version_text = _format_sqlite_version(MINIMUM_SAFE_SQLITE_VERSION)
    raise ConfigurationError(
        f"SQLite {installed_version_text} is unsafe for concurrent WAL access. SQLite {minimum_version_text} or newer is required.",
    )
