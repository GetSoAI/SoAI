"""SoAI - Direct attachment upload metadata [backend/core/attachments/direct_upload_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, ValidationError
from core.files.operations import secure_filename
from core.validation.integers import is_strict_int
from core.validation.strings import require_bounded_trimmed_text

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ensure_existing_direct_upload_matches",
    "normalize_direct_upload_declared_size",
    "normalize_direct_upload_mime_type",
    "normalize_direct_upload_suffix",
    "require_direct_upload_client_id",
    "resolve_direct_upload_display_name",
    "resolve_direct_upload_preview_type",
)


def require_direct_upload_client_id(value: str) -> str:
    return require_bounded_trimmed_text(
        value,
        type_message="client_attachment_id must be a string.",
        empty_message="client_attachment_id is required.",
        max_length=128,
        max_length_message="client_attachment_id is too long.",
        nul_message="client_attachment_id must not contain NUL bytes.",
    )


def resolve_direct_upload_display_name(
    display_name: str,
    source_filename: str | None,
) -> str:
    candidate = display_name.strip() if isinstance(display_name, str) else ""
    if not candidate and isinstance(source_filename, str):
        candidate = source_filename.strip()
    safe_filename = secure_filename(candidate)
    if not safe_filename:
        raise ValidationError("display_name is invalid.")
    return safe_filename


def ensure_existing_direct_upload_matches(
    existing: JSONDict,
    *,
    filename: str,
    mime_type: str,
    size_bytes: int | None,
) -> None:
    if size_bytes is None:
        raise ValidationError("Upload size is required for idempotent attachment replay.")
    preview_type = resolve_direct_upload_preview_type(filename, mime_type)
    if (
        existing.get("filename") == filename
        and existing.get("mime_type") == mime_type
        and existing.get("size_bytes") == size_bytes
        and existing.get("preview_type") == preview_type
    ):
        return
    raise ConflictError("Attachment upload idempotency conflict.")


def normalize_direct_upload_declared_size(value: int | None) -> int | None:
    if not is_strict_int(value) or value < 0:
        return None
    return value


def normalize_direct_upload_mime_type(content_type: str | None) -> str:
    if isinstance(content_type, str) and content_type.strip():
        return content_type.strip().lower()
    return "application/octet-stream"


def normalize_direct_upload_suffix(filename: str) -> str:
    root, extension = os.path.splitext(filename)
    _ = root
    if not extension or extension == ".":
        return ""
    normalized = extension.lower()
    if not normalized.startswith("."):
        return ""
    value = normalized[1:]
    if not value or len(value) > 16 or not value.isalnum():
        return ""
    return normalized


def resolve_direct_upload_preview_type(filename: str, mime_type: str) -> str:
    normalized_mime = mime_type.strip().lower()
    extension = os.path.splitext(filename)[1].lower().lstrip(".")
    if normalized_mime.startswith("image/"):
        return "image"
    if normalized_mime.startswith("audio/"):
        return "audio"
    if normalized_mime.startswith("video/"):
        return "video"
    if normalized_mime.startswith("text/"):
        return "text"
    if extension in {
        "pdf",
        "doc",
        "docx",
        "odt",
        "rtf",
        "md",
        "csv",
        "json",
        "html",
        "xml",
    }:
        return "document"
    return "file"
