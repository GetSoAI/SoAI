"""SoAI - Synchronous text file read with missing-file tolerance [backend/core/filesystem/text_read.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.filesystem.open_files import open_text

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

__all__ = ("read_text_if_exists",)


def read_text_if_exists(path: PathInput) -> str | None:
    content: str | None
    try:
        with open_text(path, encoding="utf-8", errors="replace") as handle:
            content = handle.read()
    except OSError:
        content = None
    return content
