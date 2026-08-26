"""SoAI - Default config schema: file explorer [backend/core/config/default_schema/file_explorer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_file_explorer_defaults",)


def build_file_explorer_defaults() -> ConfigDict:
    return {
        "FILE_EXPLORER": {
            "ENABLED": True,
            "ALLOW_SYMLINKS": False,
            "MAX_DOWNLOAD_ARCHIVE_SIZE_MB": 4096,
            "MAX_DOWNLOAD_ARCHIVE_MEMBERS": 100000,
            "TEXT_PREVIEW_LIMIT_KB": 1024,
            "LISTING_PAGINATION_LIMIT": 100,
        },
    }
