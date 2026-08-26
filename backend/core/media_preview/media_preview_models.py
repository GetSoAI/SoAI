"""SoAI - WebUI link, text, and proxy media preview models [backend/core/media_preview/media_preview_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "MediaLinkPreview",
    "ProxyFile",
    "TextPreview",
)


@dataclass(frozen=True, slots=True)
class MediaLinkPreview:
    type: str
    title: str | None
    description: str | None
    thumbnail_url: str | None
    preview_url: str | None
    embed_url: str | None
    source_url: str
    download_url: str | None
    excerpt_available: bool


@dataclass(frozen=True, slots=True)
class TextPreview:
    source_url: str
    final_url: str
    excerpt: str
    content_type: str


@dataclass(frozen=True, slots=True)
class ProxyFile:
    status_code: int
    media_type: str
    headers: dict[str, str]
    file_path: str
