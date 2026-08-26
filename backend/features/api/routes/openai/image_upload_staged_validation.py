"""SoAI - Staged image file validation for OpenAI image routes [backend/features/api/routes/openai/image_upload_staged_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.image_upload_validation import validate_staged_image_upload

if TYPE_CHECKING:
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingStagedPart,
    )

__all__ = ("validate_staged_image_parts",)


def validate_staged_image_parts(
    *,
    parts: list[StreamingStagedPart],
    max_upload_bytes: int,
) -> None:
    for part in parts:
        validate_staged_image_upload(
            staged_file_path=part.temp_path,
            original_filename=part.original_filename,
            content_type=None,
            declared_size_bytes=part.size_bytes,
            max_size_bytes=max_upload_bytes,
        )
