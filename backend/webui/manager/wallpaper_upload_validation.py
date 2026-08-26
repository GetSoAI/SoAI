"""SoAI - Wallpaper staged upload validation [backend/webui/manager/wallpaper_upload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.files.image_upload_validation import (
    ValidatedStagedImage,
    validate_staged_image_upload,
)

__all__ = ("validate_staged_image_file",)


async def validate_staged_image_file(
    *,
    staged_file_path: str,
    filename: str,
    content_type: str | None,
    declared_size_bytes: int | None,
    max_size_bytes: int,
) -> ValidatedStagedImage:
    return await asyncio.to_thread(
        validate_staged_image_upload,
        staged_file_path=staged_file_path,
        original_filename=filename,
        content_type=content_type,
        declared_size_bytes=declared_size_bytes,
        max_size_bytes=max_size_bytes,
    )
