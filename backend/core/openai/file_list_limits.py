"""SoAI - OpenAI file list limit constants [backend/core/openai/file_list_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Final

__all__ = (
    "OPENAI_FILE_LIST_DEFAULT_LIMIT",
    "OPENAI_FILE_LIST_MAX_LIMIT",
)

OPENAI_FILE_LIST_DEFAULT_LIMIT: Final[int] = 10000
OPENAI_FILE_LIST_MAX_LIMIT: Final[int] = 10000
