"""SoAI - HTTP download response metadata parsing [backend/core/network/http_download_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.network.errors import HTTPDownloadSizeLimitError

__all__ = (
    "HTTPDownloadResponseMetadata",
    "read_http_download_response_metadata",
    "DownloadResponseRange",
    "resolve_download_response_range",
)


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
        raise HTTPDownloadSizeLimitError(
            f"Content-Length ({declared_content_length} bytes) exceeds maximum size ({max_bytes} bytes).",
        )
    content_type_header = headers.get("Content-Type")
    return HTTPDownloadResponseMetadata(
        declared_content_length=declared_content_length,
        content_type=str(content_type_header).strip() if content_type_header else None,
    )


@dataclass(frozen=True, slots=True)
class DownloadResponseRange:
    offset: int
    total_length: int | None


def resolve_download_response_range(
    *,
    status_code: int,
    headers: Mapping[str, str],
    offset: int,
    content_length: int | None,
) -> DownloadResponseRange:
    content_range = headers.get("Content-Range") or headers.get("content-range")
    if status_code == 200 and content_range is None:
        return DownloadResponseRange(offset=0, total_length=content_length)
    if status_code != 206 or offset <= 0 or content_range is None:
        raise ValidationError("The artifact server returned an invalid download response.")
    range_match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", content_range)
    if range_match is None:
        raise ValidationError("The artifact server returned an invalid download range.")
    try:
        range_start, range_end, total_length = (int(value) for value in range_match.groups())
    except ValueError as exception:
        raise ValidationError(
            "The artifact server returned an invalid download range."
        ) from exception
    if range_start != offset or range_end < range_start or range_end != total_length - 1:
        raise ValidationError("The artifact server returned an incomplete or mismatched range.")
    if content_length is not None and content_length != total_length - range_start:
        raise ValidationError("The artifact server returned inconsistent download lengths.")
    return DownloadResponseRange(offset=range_start, total_length=total_length)
