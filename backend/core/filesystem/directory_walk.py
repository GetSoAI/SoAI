"""SoAI - Strict directory traversal error propagation [backend/core/filesystem/directory_walk.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("raise_directory_walk_error",)


def raise_directory_walk_error(error: OSError) -> None:
    raise error
