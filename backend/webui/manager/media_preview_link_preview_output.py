"""SoAI - Link preview output shaping helpers [backend/webui/manager/media_preview_link_preview_output.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import quote

from core.media_preview.media_preview_classification import (
    MEDIA_TYPE_EMBED,
    MEDIA_TYPE_IMAGE,
    MEDIA_TYPE_LINK,
    MEDIA_TYPE_TEXT,
)
from core.media_preview.media_preview_models import MediaLinkPreview
from core.system_api.route_paths import SOAI_WEBUI_PREFIX

__all__ = (
    "build_blocked_link_preview",
    "build_direct_media_link_preview",
    "build_download_link_preview",
    "build_embed_link_preview",
    "build_page_link_preview",
    "build_page_screenshot_preview_url",
    "build_proxy_preview_url",
    "build_text_link_preview",
    "build_text_preview_url",
)


def build_proxy_preview_url(source_url: str, *, download: bool) -> str:
    encoded = quote(source_url, safe="")
    flag = "1" if download else "0"
    return f"{SOAI_WEBUI_PREFIX}/previews/proxy?url={encoded}&download={flag}"


def build_text_preview_url(source_url: str) -> str:
    encoded = quote(source_url, safe="")
    return f"{SOAI_WEBUI_PREFIX}/previews/text_preview?url={encoded}"


def build_page_screenshot_preview_url(source_url: str) -> str:
    encoded = quote(source_url, safe="")
    return f"{SOAI_WEBUI_PREFIX}/previews/page_screenshot?url={encoded}"


def build_embed_link_preview(
    *,
    source_url: str,
    embed_url: str,
    title: str | None,
    thumbnail_url: str | None,
) -> MediaLinkPreview:
    return MediaLinkPreview(
        type=MEDIA_TYPE_EMBED,
        title=title,
        description=None,
        thumbnail_url=thumbnail_url,
        preview_url=embed_url,
        embed_url=embed_url,
        source_url=source_url,
        download_url=None,
        excerpt_available=False,
    )


def build_direct_media_link_preview(
    *,
    media_type: str,
    source_url: str,
    final_url: str,
) -> MediaLinkPreview:
    preview_url = build_proxy_preview_url(final_url, download=False)
    return MediaLinkPreview(
        type=media_type,
        title=None,
        description=None,
        thumbnail_url=preview_url if media_type == MEDIA_TYPE_IMAGE else None,
        preview_url=preview_url,
        embed_url=None,
        source_url=source_url,
        download_url=build_proxy_preview_url(final_url, download=True),
        excerpt_available=False,
    )


def build_download_link_preview(
    *,
    media_type: str,
    source_url: str,
    final_url: str,
) -> MediaLinkPreview:
    return MediaLinkPreview(
        type=media_type,
        title=None,
        description=None,
        thumbnail_url=None,
        preview_url=None,
        embed_url=None,
        source_url=source_url,
        download_url=build_proxy_preview_url(final_url, download=True),
        excerpt_available=False,
    )


def build_text_link_preview(*, source_url: str, final_url: str) -> MediaLinkPreview:
    return MediaLinkPreview(
        type=MEDIA_TYPE_TEXT,
        title=None,
        description=None,
        thumbnail_url=None,
        preview_url=build_text_preview_url(final_url),
        embed_url=None,
        source_url=source_url,
        download_url=build_proxy_preview_url(final_url, download=True),
        excerpt_available=True,
    )


def build_blocked_link_preview(*, source_url: str) -> MediaLinkPreview:
    return MediaLinkPreview(
        type=MEDIA_TYPE_LINK,
        title=None,
        description=None,
        thumbnail_url=None,
        preview_url=None,
        embed_url=None,
        source_url=source_url,
        download_url=None,
        excerpt_available=False,
    )


def build_page_link_preview(
    *,
    source_url: str,
    final_url: str,
    title: str | None,
    description: str | None,
    thumbnail_url: str | None,
) -> MediaLinkPreview:
    return MediaLinkPreview(
        type=MEDIA_TYPE_LINK,
        title=title,
        description=description,
        thumbnail_url=thumbnail_url,
        preview_url=build_text_preview_url(final_url),
        embed_url=None,
        source_url=source_url,
        download_url=None,
        excerpt_available=True,
    )
