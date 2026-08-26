"""SoAI - Default config schema: file manager [backend/core/config/default_schema/file_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_file_manager_defaults",)


def build_file_manager_defaults() -> ConfigDict:
    return {
        "FILES": {
            "RECONCILIATION_CONCURRENCY": 32,
            "INITIAL_CLEANUP_ENABLED": True,
            "DIRECTORY_SCAN_TIMEOUT_SEC": 600.0,
        },
    }
