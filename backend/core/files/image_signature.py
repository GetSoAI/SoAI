"""SoAI - Image file signature validation using magic bytes [backend/core/files/image_signature.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("validate_image_signature",)

ALLOWED_IMAGE_EXTENSIONS: frozenset[str] = frozenset((".png", ".jpg", ".jpeg", ".gif", ".webp"))

ALLOWED_IMAGE_CONTENT_TYPES: frozenset[str] = frozenset(
    ("image/png", "image/jpeg", "image/gif", "image/webp"),
)

IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),
)


def validate_image_signature(first_bytes: bytes) -> tuple[bool, str | None]:
    for signature, mime_type in IMAGE_SIGNATURES:
        if first_bytes.startswith(signature):
            if mime_type == "image/webp":
                if len(first_bytes) < 12 or first_bytes[8:12] != b"WEBP":
                    continue
            return (True, mime_type)
    return (False, None)
