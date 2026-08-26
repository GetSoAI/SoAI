"""SoAI - HTTP download response metadata parsing [backend/core/network/http_download_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from core.errors.exceptions import ValidationError

__all__ = ("HTTPDownloadResponseMetadata", "read_http_download_response_metadata")


@dataclass(frozen=True, slots=True)
class HTTPDownloadResponseMetadata:
    declared_content_length: int | None
    content_type: str | None


def read_http_download_response_metadata(
    headers: Mapping[str, str],
    *,
    max_bytes: int | None,
) -> HTTPDownloadResponseMetadata:
    declared_content_length: int | None = None
    content_length_header = headers.get("Content-Length")
    if content_length_header:
        try:
            parsed_length = int(content_length_header)
        except ValueError:
            parsed_length = 0
        if parsed_length > 0:
            declared_content_length = parsed_length
    if (
        max_bytes is not None
        and declared_content_length is not None
        and declared_content_length > max_bytes
    ):
        raise ValidationError(
            f"Content-Length ({declared_content_length} bytes) exceeds maximum size ({max_bytes} bytes).",
        )
    content_type_header = headers.get("Content-Type")
    return HTTPDownloadResponseMetadata(
        declared_content_length=declared_content_length,
        content_type=str(content_type_header).strip() if content_type_header else None,
    )
