"""SoAI - Browser download target path allocation [backend/mcp/tools/browser/download_target_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import ValidationError

__all__ = ("allocate_download_target_path",)


def _split_filename(filename: str) -> tuple[str, str]:
    stem, extension = os.path.splitext(filename)
    if not stem:
        return ("download", extension)
    return (stem, extension)


def allocate_download_target_path(
    *,
    downloads_dir: str,
    filename: str,
    reserved_paths: set[str],
) -> str:
    stem, extension = _split_filename(filename)
    for index in range(10_000):
        candidate_name = filename if index == 0 else f"{stem}-{index}{extension}"
        candidate_path = os.path.join(downloads_dir, candidate_name)
        if candidate_path in reserved_paths:
            continue
        if os.path.exists(candidate_path):
            continue
        reserved_paths.add(candidate_path)
        return candidate_path
    raise ValidationError("Unable to allocate a unique browser download filename.")
