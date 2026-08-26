"""SoAI - WebUI descriptor-backed content responses [backend/features/api/routes/webui/descriptor_content_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
from collections.abc import Iterator

from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.responses import Response, StreamingResponse

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.files.export import (
    build_content_disposition_attachment,
    build_content_disposition_inline,
)

__all__ = (
    "open_descriptor_streaming_response",
    "open_descriptor_thumbnail_response",
)

_STREAM_CHUNK_BYTES = MIB_BYTES
_THUMBNAIL_SIZE: tuple[int, int] = (160, 160)


def _headers(*, filename: str, download: bool, content_length: int | None) -> dict[str, str]:
    headers = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Content-Disposition": (
            build_content_disposition_attachment(filename)
            if download
            else build_content_disposition_inline(filename)
        ),
        "X-Content-Type-Options": "nosniff",
    }
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    return headers


def _iter_descriptor(descriptor: int) -> Iterator[bytes]:
    with os.fdopen(descriptor, "rb", closefd=True) as handle:
        while True:
            chunk = handle.read(_STREAM_CHUNK_BYTES)
            if not chunk:
                break
            yield chunk


def _read_thumbnail_from_descriptor(descriptor: int) -> bytes:
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            with Image.open(handle) as opened:
                normalized = ImageOps.exif_transpose(opened)
                normalized.thumbnail(_THUMBNAIL_SIZE)
                thumbnail = normalized.convert("RGBA")
                output = io.BytesIO()
                thumbnail.save(output, format="PNG", optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError) as exception:
        raise ValidationError("Attachment thumbnail requires an image file.") from exception


def open_descriptor_streaming_response(
    *,
    descriptor: int,
    size_bytes: int,
    filename: str,
    mime_type: str,
    download: bool,
) -> StreamingResponse:
    return StreamingResponse(
        _iter_descriptor(descriptor),
        media_type=mime_type,
        headers=_headers(filename=filename, download=download, content_length=size_bytes),
    )


def open_descriptor_thumbnail_response(
    *,
    descriptor: int,
    filename: str,
) -> Response:
    content = _read_thumbnail_from_descriptor(descriptor)
    return Response(
        content=content,
        media_type="image/png",
        headers=_headers(filename=filename, download=False, content_length=len(content)),
    )
