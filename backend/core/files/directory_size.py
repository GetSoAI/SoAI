"""SoAI - Directory size calculation helper [backend/core/files/directory_size.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = ("calculate_directory_size_bytes",)


def calculate_directory_size_bytes(directory_path: str) -> int:
    total_size = 0
    for dirpath, _dirnames, filenames in os.walk(directory_path, followlinks=False):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                if os.path.islink(filepath):
                    continue
                total_size += os.path.getsize(filepath)
            except OSError:
                continue
    return total_size
