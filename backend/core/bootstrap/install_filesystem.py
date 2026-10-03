"""SoAI - Install filesystem helpers [backend/core/bootstrap/install_filesystem.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.filesystem.path_coercion import normalize_filesystem_path

__all__ = ("rmdir_if_exists", "unlink_if_exists")


def unlink_if_exists(path: str) -> bool:
    removed = False
    try:
        os.unlink(normalize_filesystem_path(path))
        removed = True
    except FileNotFoundError:
        removed = False
    return removed


def rmdir_if_exists(path: str) -> bool:
    removed = False
    try:
        os.rmdir(normalize_filesystem_path(path))
        removed = True
    except FileNotFoundError:
        removed = False
    except OSError:
        removed = False
    return removed
