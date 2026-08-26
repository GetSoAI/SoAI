"""SoAI - Text preview excerpt fetch service [backend/webui/manager/media_preview_text_preview_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.concurrency.ttl_cache import TTLCache, TTLCacheDependencies
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.files.content_types import (
    content_type_is_html,
    content_type_is_javascript,
    normalize_content_type,
    resolve_content_type_charset,
)
from core.media_preview.media_preview_models import TextPreview
from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.network.urls import normalize_http_url
from core.web.html_metadata import extract_html_text_excerpt
from webui.manager.media_preview_fetcher import BoundedMediaFetcher
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "TextPreviewService",
    "TextPreviewServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class TextPreviewServiceDependencies:
    settings: MediaPreviewSettings
    policy: RemoteMediaPolicy
    fetcher: BoundedMediaFetcher

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TextPreviewServiceDependencies",
            fetcher=self.fetcher,
            policy=self.policy,
            settings=self.settings,
        )


class TextPreviewService:
    __slots__ = ("_cache", "_deps")

    def __init__(self, deps: TextPreviewServiceDependencies) -> None:
        self._deps = deps
        self._cache: TTLCache[str, TextPreview] = TTLCache(
            TTLCacheDependencies(ttl_seconds=300.0, max_size=2048),
        )

    async def get_text_preview(
        self,
        http_client: httpx2.AsyncClient,
        runtime_flags: RuntimeFlagsViewProtocol,
        source_url: str,
    ) -> TextPreview:
        normalized = normalize_http_url(source_url)
        cached = self._cache.get(normalized)
        if cached is not None:
            return cached
        await self._deps.policy.enforce(
            runtime_flags,
            normalized,
            source="webui media text_preview",
        )
        fetch_result = await self._deps.fetcher.fetch_bytes_bounded(
            http_client,
            normalized,
            runtime_flags,
            max_bytes=self._deps.settings.text_preview_max_bytes,
            timeout=self._deps.settings.timeout_sec,
            headers={"Accept": "text/plain,text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"},
            source="webui media text_preview fetch",
        )
        if fetch_result.blocked_response is not None:
            raise ValidationError("Upstream blocked text preview retrieval.")
        final_url = fetch_result.final_url
        content_type = fetch_result.content_type
        payload_bytes = fetch_result.payload_bytes
        normalized_content_type = normalize_content_type(content_type)
        if normalized_content_type and content_type_is_javascript(normalized_content_type):
            raise ValidationError(
                f"Unsupported text preview content-type: {normalized_content_type!r}.",
            )
        decoded = payload_bytes.decode(resolve_content_type_charset(content_type), errors="replace")
        excerpt: str
        if content_type_is_html(content_type):
            excerpt = extract_html_text_excerpt(
                html_text=decoded,
                max_chars=min(4000, max(200, self._deps.settings.text_preview_max_bytes)),
            )
        else:
            excerpt = decoded.replace("\r\n", "\n").replace("\r", "\n")
            if len(excerpt) > 4000:
                excerpt = excerpt[:4000]
        if not isinstance(excerpt, str):
            raise ValidationError("Text preview excerpt must be a string.")
        preview = TextPreview(
            source_url=normalized,
            final_url=final_url,
            excerpt=excerpt,
            content_type=(content_type or "text/plain; charset=utf-8"),
        )
        self._cache.put(normalized, preview)
        return preview
