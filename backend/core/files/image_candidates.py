"""SoAI - Core image file candidate detection [backend/core/files/image_candidates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.content_types import content_type_is_image, normalize_content_type
from core.files.extensions.media import IMAGE_EXTENSIONS

__all__ = ("is_supported_image_candidate", "normalize_file_extension")


def normalize_file_extension(path: str) -> str:
    _, extension = os.path.splitext(str(path or ""))
    return extension.lstrip(".").strip().lower()


def is_supported_image_candidate(*, path: str, content_type: str | None) -> bool:
    extension = normalize_file_extension(path)
    if extension == "svg" or normalize_content_type(content_type) == "image/svg+xml":
        return False
    if extension in IMAGE_EXTENSIONS:
        return True
    return content_type_is_image(content_type)
