"""SoAI - Inline image payload encoding helpers [backend/core/files/inline_image_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.serialization.base64_values import encode_base64_ascii

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "MAX_INLINE_IMAGE_BASE64_CHARS",
    "build_inline_image_payload",
    "estimate_inline_image_base64_chars",
)

MAX_INLINE_IMAGE_BASE64_CHARS: int = 128 * MIB_BYTES


def estimate_inline_image_base64_chars(byte_count: int) -> int:
    return ((max(0, int(byte_count)) + 2) // 3) * 4


def build_inline_image_payload(
    *,
    content_type: str,
    image_bytes: bytes,
    max_base64_chars: int | None = None,
) -> tuple[JSONDict | None, str | None]:
    if max_base64_chars is not None and estimate_inline_image_base64_chars(len(image_bytes)) > int(
        max_base64_chars,
    ):
        return (None, "Inline image exceeded the size limit.")
    encoded = encode_base64_ascii(image_bytes)
    return (
        {
            "content_type": content_type,
            "image_base64": encoded,
        },
        None,
    )
