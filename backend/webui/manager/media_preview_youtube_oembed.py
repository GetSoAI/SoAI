"""SoAI - YouTube oEmbed title resolution for media previews [backend/webui/manager/media_preview_youtube_oembed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx2

from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.serialization.json_parsing import parse_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from webui.manager.media_preview_fetcher import BoundedMediaFetcher

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("resolve_youtube_oembed_title",)


def _build_youtube_oembed_url(source_url: str) -> str:
    return f"https://www.youtube.com/oembed?url={quote(source_url, safe='')}&format=json"


async def resolve_youtube_oembed_title(
    http_client: httpx2.AsyncClient,
    settings: MediaPreviewSettings,
    fetcher: BoundedMediaFetcher,
    runtime_flags: RuntimeFlagsViewProtocol,
    source_url: str,
) -> str | None:
    oembed_url = _build_youtube_oembed_url(source_url)
    result = await fetcher.fetch_bytes_bounded(
        http_client,
        oembed_url,
        runtime_flags,
        max_bytes=8192,
        timeout=settings.timeout_sec,
        headers={"Accept": "application/json"},
        source="webui media youtube oembed",
    )
    payload = parse_json_dict(result.payload_bytes, field="YouTube oEmbed response")
    return coerce_optional_trimmed_str(payload.get("title"))
