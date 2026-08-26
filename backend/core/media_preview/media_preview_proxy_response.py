"""SoAI - Media proxy response resolution helpers [backend/core/media_preview/media_preview_proxy_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from urllib.parse import urlparse

from core.errors.exceptions import ValidationError
from core.files.export import build_content_disposition_attachment
from core.files.operations import secure_filename
from core.media_preview.media_preview_classification import (
    MEDIA_TYPE_AUDIO,
    MEDIA_TYPE_DOCUMENT,
    MEDIA_TYPE_FILE,
    MEDIA_TYPE_IMAGE,
    MEDIA_TYPE_LINK,
    MEDIA_TYPE_TEXT,
    MEDIA_TYPE_VIDEO,
    classify_content_type_for_link_preview,
    classify_url_by_extension,
    normalize_content_type,
)

__all__ = (
    "build_proxy_headers",
    "enforce_proxy_type_allowed",
    "is_blocked_proxy_content_type",
    "resolve_download_filename",
    "resolve_effective_media_type",
    "resolve_proxy_type",
)


def is_blocked_proxy_content_type(content_type: str | None) -> bool:
    normalized = normalize_content_type(content_type)
    return normalized in {
        "text/html",
        "application/xhtml+xml",
        "application/javascript",
        "text/javascript",
        "application/ecmascript",
        "text/ecmascript",
    }


def resolve_proxy_type(*, final_url: str, content_type: str | None) -> str:
    normalized = normalize_content_type(content_type)
    if normalized:
        media_type = classify_content_type_for_link_preview(normalized)
        if media_type is not None:
            return media_type
        return MEDIA_TYPE_LINK
    type_by_ext, _mime_by_ext = classify_url_by_extension(final_url)
    if type_by_ext == MEDIA_TYPE_LINK:
        return MEDIA_TYPE_FILE
    return type_by_ext


def resolve_effective_media_type(
    *,
    final_url: str,
    content_type: str | None,
    download: bool,
) -> str:
    if is_blocked_proxy_content_type(content_type):
        raise ValidationError("Blocked content-type.")
    normalized = normalize_content_type(content_type)
    if normalized and not download:
        if normalized.startswith("image/") and normalized != "image/svg+xml":
            return normalized
        if normalized.startswith("audio/"):
            return normalized
        if normalized.startswith("video/"):
            return normalized
        raise ValidationError("Inline proxying is only allowed for images, audio, and video.")
    if normalized and download:
        return normalized
    type_by_ext, mime_by_ext = classify_url_by_extension(final_url)
    if not download:
        if (
            type_by_ext in {MEDIA_TYPE_IMAGE, MEDIA_TYPE_AUDIO, MEDIA_TYPE_VIDEO}
            and mime_by_ext is not None
        ):
            return mime_by_ext
        raise ValidationError("Unsupported inline media type.")
    if (
        type_by_ext in {MEDIA_TYPE_IMAGE, MEDIA_TYPE_AUDIO, MEDIA_TYPE_VIDEO}
        and mime_by_ext is not None
    ):
        return mime_by_ext
    return "application/octet-stream"


def enforce_proxy_type_allowed(*, media_type: str, download: bool) -> None:
    if download:
        if media_type in {
            MEDIA_TYPE_IMAGE,
            MEDIA_TYPE_AUDIO,
            MEDIA_TYPE_VIDEO,
            MEDIA_TYPE_TEXT,
            MEDIA_TYPE_DOCUMENT,
            MEDIA_TYPE_FILE,
        }:
            return
        raise ValidationError("Unsupported download type.")
    if media_type in {MEDIA_TYPE_IMAGE, MEDIA_TYPE_AUDIO, MEDIA_TYPE_VIDEO}:
        return
    raise ValidationError("Inline proxying is only allowed for images, audio, and video.")


def resolve_download_filename(final_url: str) -> str:
    parsed = urlparse(final_url)
    candidate = os.path.basename(parsed.path or "").strip()
    safe = secure_filename(candidate or "download")
    return safe or "download"


def build_proxy_headers(
    *,
    download: bool,
    content_disposition_filename: str,
    cache_ttl_seconds: int,
) -> dict[str, str]:
    if download or cache_ttl_seconds <= 0:
        cache_control = "no-store"
    else:
        cache_control = f"private, max-age={cache_ttl_seconds}, immutable"
    headers: dict[str, str] = {
        "Cache-Control": cache_control,
        "X-Content-Type-Options": "nosniff",
    }
    if download:
        headers["Content-Disposition"] = build_content_disposition_attachment(
            content_disposition_filename,
        )
    return headers
