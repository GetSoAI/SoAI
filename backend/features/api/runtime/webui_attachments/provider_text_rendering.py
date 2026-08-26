"""SoAI - WebUI provider text rendering [backend/features/api/runtime/webui_attachments/provider_text_rendering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.attachments.inline_file_content_markers import (
    INLINE_FILE_CONTENT_BEGIN_MARKER,
    INLINE_FILE_CONTENT_END_MARKER,
    INLINE_FILE_CONTENT_TRUNCATED_MARKER,
)

__all__ = (
    "build_file_content_unavailable_text",
    "build_inline_file_content_text",
    "build_missing_text_extraction_text",
    "sanitize_provider_text_field",
)

_FIELD_MAX_CHARS = 240


def sanitize_provider_text_field(value: str | None) -> str | None:
    if value is None:
        return None
    printable = "".join(character if character.isprintable() else " " for character in value)
    collapsed = " ".join(printable.split()).strip()
    if not collapsed:
        return None
    return collapsed[:_FIELD_MAX_CHARS]


def _header_line(header: str | None) -> tuple[str, ...]:
    sanitized = sanitize_provider_text_field(header)
    if sanitized is None:
        return ()
    return (sanitized,)


def build_inline_file_content_text(*, header: str | None, content: str, truncated: bool) -> str:
    lines = [
        *_header_line(header),
        INLINE_FILE_CONTENT_BEGIN_MARKER,
        content,
        INLINE_FILE_CONTENT_END_MARKER,
    ]
    if truncated:
        lines.append(INLINE_FILE_CONTENT_TRUNCATED_MARKER)
    return "\n".join(lines)


def build_missing_text_extraction_text(*, header: str) -> str:
    return "\n".join(
        (
            *_header_line(header),
            "No text could be extracted from this file.",
        ),
    )


def build_file_content_unavailable_text(*, header: str, reason: str | None) -> str:
    sanitized_reason = sanitize_provider_text_field(reason)
    if sanitized_reason is None:
        return "\n".join(
            (
                *_header_line(header),
                "File content is unavailable.",
            ),
        )
    return "\n".join(
        (
            *_header_line(header),
            f"File content is unavailable: {sanitized_reason}",
        ),
    )
