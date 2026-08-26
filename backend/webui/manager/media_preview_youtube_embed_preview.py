"""SoAI - YouTube embed preview assembly for WebUI media previews [backend/webui/manager/media_preview_youtube_embed_preview.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import NotFoundError, ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.media_preview.media_preview_models import MediaLinkPreview
from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.runtime.network_policy import OfflineModeError
from webui.manager.media_preview_fetcher import BoundedMediaFetcher
from webui.manager.media_preview_link_preview_output import (
    build_embed_link_preview,
    build_proxy_preview_url,
)
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy
from webui.manager.media_preview_youtube_oembed import resolve_youtube_oembed_title

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("build_youtube_embed_link_preview",)

OPERATION_LINK_PREVIEW_YOUTUBE_OEMBED = "webui.media.link_preview.youtube_oembed"
OPERATION_LINK_PREVIEW_YOUTUBE_THUMBNAIL = "webui.media.link_preview.youtube_thumbnail"
YOUTUBE_TITLE_LOOKUP_EXCEPTIONS = HTTP_RECOVERABLE_EXCEPTIONS + (NotFoundError, ValidationError)


async def _resolve_youtube_title(
    http_client: httpx2.AsyncClient,
    settings: MediaPreviewSettings,
    fetcher: BoundedMediaFetcher,
    runtime_flags: RuntimeFlagsViewProtocol,
    source_url: str,
    logger: LoggerProtocol,
) -> str | None:
    try:
        return await resolve_youtube_oembed_title(
            http_client,
            settings,
            fetcher,
            runtime_flags,
            source_url,
        )
    except YOUTUBE_TITLE_LOOKUP_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="YouTube oEmbed title lookup failed; returning embed preview without title.",
            operation=OPERATION_LINK_PREVIEW_YOUTUBE_OEMBED,
            details={"source_url": source_url},
            level="debug",
        )
        return None


async def _resolve_youtube_thumbnail_url(
    policy: RemoteMediaPolicy,
    runtime_flags: RuntimeFlagsViewProtocol,
    thumb_url: str,
    logger: LoggerProtocol,
) -> str | None:
    try:
        await policy.enforce(
            runtime_flags,
            thumb_url,
            source="webui media youtube thumbnail",
        )
        return build_proxy_preview_url(thumb_url, download=False)
    except (OfflineModeError, ValidationError) as exception:
        log_handled_exception(
            logger,
            exception,
            message="YouTube thumbnail was blocked; returning embed preview without thumbnail.",
            operation=OPERATION_LINK_PREVIEW_YOUTUBE_THUMBNAIL,
            details={"thumbnail_url": thumb_url},
            level="debug",
        )
        return None


async def build_youtube_embed_link_preview(
    *,
    http_client: httpx2.AsyncClient,
    settings: MediaPreviewSettings,
    fetcher: BoundedMediaFetcher,
    policy: RemoteMediaPolicy,
    runtime_flags: RuntimeFlagsViewProtocol,
    source_url: str,
    embed_url: str,
    thumb_url: str,
    logger: LoggerProtocol,
) -> MediaLinkPreview:
    title = await _resolve_youtube_title(
        http_client,
        settings,
        fetcher,
        runtime_flags,
        source_url,
        logger,
    )
    thumbnail_url = await _resolve_youtube_thumbnail_url(policy, runtime_flags, thumb_url, logger)
    return build_embed_link_preview(
        source_url=source_url,
        embed_url=embed_url,
        title=title,
        thumbnail_url=thumbnail_url,
    )
