"""SoAI - Media preview proxy cache entry resolution [backend/webui/manager/media_preview_proxy_cache_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.media_preview.media_preview_models import ProxyFile
from core.media_preview.media_preview_proxy_response import (
    build_proxy_headers,
    enforce_proxy_type_allowed,
    resolve_download_filename,
    resolve_effective_media_type,
    resolve_proxy_type,
)
from webui.manager.media_preview_proxy_cache import (
    touch_cache_file,
    try_read_cache_metadata,
)
from webui.manager.media_preview_proxy_cache_metadata_schema import (
    try_parse_media_preview_cache_metadata_v1,
)

__all__ = (
    "try_prepare_cached_page_screenshot_png",
    "try_prepare_cached_proxy_file",
)


async def try_prepare_cached_proxy_file(
    *,
    data_path: str,
    meta_path: str,
    download: bool,
    cache_ttl_seconds: int,
) -> ProxyFile | None:
    metadata_raw = await try_read_cache_metadata(meta_path)
    if metadata_raw is None:
        return None
    metadata = try_parse_media_preview_cache_metadata_v1(metadata_raw)
    if metadata is None:
        return None
    if not await asyncio.to_thread(os.path.isfile, data_path):
        return None
    final_url = metadata.final_url.strip()
    content_type = metadata.content_type.strip()
    if not final_url:
        return None
    await touch_cache_file(data_path)
    media_type = resolve_effective_media_type(
        final_url=final_url,
        content_type=content_type or None,
        download=download,
    )
    proxy_type = resolve_proxy_type(final_url=final_url, content_type=content_type or None)
    enforce_proxy_type_allowed(media_type=proxy_type, download=download)
    headers = build_proxy_headers(
        download=download,
        content_disposition_filename=resolve_download_filename(final_url),
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return ProxyFile(status_code=200, media_type=media_type, headers=headers, file_path=data_path)


async def try_prepare_cached_page_screenshot_png(
    *,
    data_path: str,
    meta_path: str,
    cache_ttl_seconds: int,
) -> ProxyFile | None:
    metadata_raw = await try_read_cache_metadata(meta_path)
    if metadata_raw is None:
        return None
    metadata = try_parse_media_preview_cache_metadata_v1(metadata_raw)
    if metadata is None:
        return None
    if not await asyncio.to_thread(os.path.isfile, data_path):
        return None
    content_type = metadata.content_type.strip()
    if content_type.lower() != "image/png":
        return None
    await touch_cache_file(data_path)
    headers = build_proxy_headers(
        download=False,
        content_disposition_filename="preview.png",
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return ProxyFile(status_code=200, media_type="image/png", headers=headers, file_path=data_path)
