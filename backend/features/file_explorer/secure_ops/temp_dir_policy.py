"""SoAI - Temporary directory policy for atomic writes [backend/features/file_explorer/secure_ops/temp_dir_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = ("is_same_filesystem_directory",)


def is_same_filesystem_directory(temp_dir: str, parent_dir: str) -> bool:
    if not temp_dir or not parent_dir:
        return False
    if os.name == "nt":
        try:
            temp_drive, _ = os.path.splitdrive(os.path.abspath(temp_dir))
            parent_drive, _ = os.path.splitdrive(os.path.abspath(parent_dir))
        except OSError:
            return False
        return bool(temp_drive) and temp_drive.lower() == parent_drive.lower()
    try:
        temp_stat = os.stat(temp_dir)
        parent_stat = os.stat(parent_dir)
    except OSError:
        return False
    try:
        temp_dev = temp_stat.st_dev
    except AttributeError:
        temp_dev = None
    try:
        parent_dev = parent_stat.st_dev
    except AttributeError:
        parent_dev = None
    return temp_dev is not None and temp_dev == parent_dev
