"""SoAI - Shared inline image preparation [backend/core/files/inline_image_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image, ImageOps, UnidentifiedImageError

from core.files.image_signature import validate_image_signature
from core.files.inline_image_jpeg_preparation import prepare_opened_image_as_jpeg
from core.files.inline_image_payload import (
    MAX_INLINE_IMAGE_BASE64_CHARS,
    build_inline_image_payload,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "DEFAULT_PROMPT_RELAY_IMAGE_JPEG_QUALITY",
    "DEFAULT_PROMPT_RELAY_IMAGE_MAX_PIXELS",
    "DEFAULT_PROMPT_RELAY_IMAGE_MAX_SOURCE_BYTES",
    "PreparedInlineImage",
    "prepare_inline_image_for_prompt_relay",
)

DEFAULT_PROMPT_RELAY_IMAGE_MAX_PIXELS = 4_000_000
DEFAULT_PROMPT_RELAY_IMAGE_JPEG_QUALITY = 85
DEFAULT_PROMPT_RELAY_IMAGE_MAX_SOURCE_BYTES = 134_217_728


@dataclass(frozen=True, slots=True)
class PreparedInlineImage:
    content_type: str
    payload: JSONDict
    source_bytes: int
    encoded_chars: int
    source_width: int
    source_height: int
    prepared_width: int
    prepared_height: int
    prepared_bytes: int


def prepare_inline_image_for_prompt_relay(
    *,
    image_bytes: bytes,
    declared_content_type: str | None,
    max_source_bytes: int = DEFAULT_PROMPT_RELAY_IMAGE_MAX_SOURCE_BYTES,
    max_encoded_chars: int = MAX_INLINE_IMAGE_BASE64_CHARS,
    max_pixels: int = DEFAULT_PROMPT_RELAY_IMAGE_MAX_PIXELS,
    jpeg_quality: int = DEFAULT_PROMPT_RELAY_IMAGE_JPEG_QUALITY,
    allow_image_candidate: bool = False,
) -> tuple[PreparedInlineImage | None, str | None]:
    if len(image_bytes) > max(1, int(max_source_bytes)):
        return (None, "Image source exceeded the size limit.")
    detected_content_type = _resolve_detected_content_type(image_bytes=image_bytes)
    if (
        detected_content_type is None
        and not _declared_image_candidate(declared_content_type)
        and not allow_image_candidate
    ):
        return (None, "Unsupported image signature.")
    try:
        prepared_bytes, width, height, prepared_width, prepared_height = _prepare_image_bytes(
            image_bytes=image_bytes,
            max_pixels=max_pixels,
            max_encoded_chars=max_encoded_chars,
            jpeg_quality=jpeg_quality,
        )
    except (
        OSError,
        SyntaxError,
        UnidentifiedImageError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return (None, "Image processing failed; image data is corrupt or unsupported.")
    inline_payload, failure_reason = build_inline_image_payload(
        content_type="image/jpeg",
        image_bytes=prepared_bytes,
        max_base64_chars=max_encoded_chars,
    )
    if inline_payload is None:
        return (None, failure_reason or "Inline image exceeded the size limit.")
    encoded_value = inline_payload.get("image_base64")
    if not isinstance(encoded_value, str) or not encoded_value:
        return (None, "Inline image encoding failed.")
    return (
        PreparedInlineImage(
            content_type="image/jpeg",
            payload=inline_payload,
            source_bytes=len(image_bytes),
            encoded_chars=len(encoded_value),
            source_width=width,
            source_height=height,
            prepared_width=prepared_width,
            prepared_height=prepared_height,
            prepared_bytes=len(prepared_bytes),
        ),
        None,
    )


def _resolve_detected_content_type(
    *,
    image_bytes: bytes,
) -> str | None:
    is_valid, detected_content_type = validate_image_signature(image_bytes[:32])
    if not is_valid or detected_content_type is None:
        return None
    return detected_content_type


def _declared_image_candidate(declared_content_type: str | None) -> bool:
    if declared_content_type is None:
        return False
    normalized = declared_content_type.strip().lower()
    return normalized.startswith("image/") and normalized != "image/svg+xml"


def _prepare_image_bytes(
    *,
    image_bytes: bytes,
    max_pixels: int,
    max_encoded_chars: int,
    jpeg_quality: int,
) -> tuple[bytes, int, int, int, int]:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.verify()
        with Image.open(io.BytesIO(image_bytes)) as source_image:
            transposed_image = ImageOps.exif_transpose(source_image)
            return prepare_opened_image_as_jpeg(
                image=transposed_image,
                max_pixels=max_pixels,
                max_encoded_chars=max_encoded_chars,
                jpeg_quality=jpeg_quality,
            )
