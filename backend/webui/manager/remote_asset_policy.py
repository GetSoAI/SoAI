"""SoAI - Shared remote asset URL policy validators [backend/webui/manager/remote_asset_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.network.policy import enforce_url_network_policy
from core.runtime.network_policy import is_offline_mode_enabled, validate_local_only_url

if TYPE_CHECKING:
    from core.network.dns_cache import DnsResolutionCache
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("build_remote_asset_url_validator",)


def build_remote_asset_url_validator(
    *,
    runtime_flags: RuntimeFlagsViewProtocol,
    block_private_networks: bool,
    dns_timeout_sec: float,
    source: str,
    dns_cache: DnsResolutionCache | None = None,
) -> Callable[[str], Awaitable[str | None]]:
    async def url_validator(check_url: str) -> str | None:
        pinned_host = await validate_local_only_url(
            runtime_flags,
            check_url,
            source=source,
            dns_cache=dns_cache,
        )
        if is_offline_mode_enabled(runtime_flags):
            return pinned_host
        if not block_private_networks:
            return None
        return await enforce_url_network_policy(
            check_url,
            block_private_networks=True,
            dns_timeout_sec=dns_timeout_sec,
            source=source,
            dns_cache=dns_cache,
        )

    return url_validator
