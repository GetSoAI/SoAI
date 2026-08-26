"""SoAI - Windows reparse point detection [backend/core/files/windows_reparse_points.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.protocols_stat import WindowsStatResultProtocol

__all__ = ("is_windows_reparse_point",)

_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def is_windows_reparse_point(stat_result: os.stat_result | WindowsStatResultProtocol) -> bool:
    if os.name != "nt" or not isinstance(stat_result, WindowsStatResultProtocol):
        return False
    return bool(stat_result.st_file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT)
