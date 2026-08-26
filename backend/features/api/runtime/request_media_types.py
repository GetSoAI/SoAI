"""SoAI - Buffered request media type validation [backend/features/api/runtime/request_media_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from python_multipart.multipart import parse_options_header

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from fastapi import Request

__all__ = (
    "is_multipart_media_type",
    "require_non_multipart_media_type",
)


def is_multipart_media_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    media_type, _options = parse_options_header(content_type)
    return media_type.lower().startswith(b"multipart/")


def require_non_multipart_media_type(request: Request) -> None:
    if is_multipart_media_type(request.headers.get("content-type")):
        raise ValidationError("Multipart content is not accepted for this request.")
