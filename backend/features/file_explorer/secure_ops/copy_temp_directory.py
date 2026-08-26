"""SoAI - Secure copy temporary directory allocation [backend/features/file_explorer/secure_ops/copy_temp_directory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError

__all__ = (
    "allocate_copy_temp_directory",
    "build_copy_directory_temp_path",
)


def build_copy_directory_temp_path(destination_path: str) -> str:
    parent_dir = os.path.dirname(destination_path)
    base_name = os.path.basename(destination_path)
    token = os.urandom(8).hex()
    return os.path.join(parent_dir, f".{base_name}.copying_{token}")


def allocate_copy_temp_directory(
    destination_path: str,
    *,
    operation: str,
    mode: int | None,
) -> str:
    temp_path = ""
    for _ in range(10):
        temp_path = build_copy_directory_temp_path(destination_path)
        try:
            if mode is None:
                os.mkdir(temp_path)
            else:
                os.mkdir(temp_path, mode)
        except FileExistsError:
            continue
        return temp_path
    raise StateError(
        "Failed to allocate temporary directory for copy.",
        operation=operation,
    )
