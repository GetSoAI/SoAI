"""SoAI - Remote media access policy enforcement [backend/webui/manager/media_preview_remote_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.network.dns_cache import DnsResolutionCache
from webui.manager.remote_asset_policy import build_remote_asset_url_validator

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("RemoteMediaPolicy",)


class RemoteMediaPolicy:
    __slots__ = ("_dns_cache", "_settings")

    def __init__(self, settings: MediaPreviewSettings, dns_cache: DnsResolutionCache) -> None:
        self._settings = settings
        self._dns_cache = dns_cache

    async def enforce(
        self,
        runtime_flags: RuntimeFlagsViewProtocol,
        normalized_url: str,
        *,
        source: str,
    ) -> str | None:
        url_validator = build_remote_asset_url_validator(
            runtime_flags=runtime_flags,
            block_private_networks=self._settings.block_private_networks,
            dns_timeout_sec=self._settings.dns_timeout_sec,
            source=source,
            dns_cache=self._dns_cache,
        )
        return await url_validator(normalized_url)
