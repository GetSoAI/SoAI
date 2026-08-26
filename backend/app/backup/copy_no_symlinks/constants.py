"""SoAI - Backup copy constants [backend/app/backup/copy_no_symlinks/constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

UPDATER_EXCLUSIONS: frozenset[str] = frozenset(
    (
        "logs",
        "temp",
        "data",
        "cache",
        "models",
        "backends",
        "*_venv",
        "*.pyc",
        "__pycache__",
        "config",
        "node_modules",
    ),
)
