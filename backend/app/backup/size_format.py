"""SoAI - Compact backup byte-size formatting [backend/app/backup/size_format.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.byte_sizes import GIB_BYTES, MIB_BYTES

__all__ = ("format_size",)


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < MIB_BYTES:
        return f"{size_bytes / 1024:.2f}KB"
    if size_bytes < GIB_BYTES:
        return f"{size_bytes / MIB_BYTES:.2f}MB"
    return f"{size_bytes / GIB_BYTES:.2f}GB"
