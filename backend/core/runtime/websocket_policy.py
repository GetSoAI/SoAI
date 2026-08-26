"""SoAI - Runtime WebSocket network policy enforcement [backend/core/runtime/websocket_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.dns_cache import DnsResolutionCache
from core.network.policy import (
    enforce_url_local_only_policy_ws,
    enforce_url_network_policy_ws,
)
from core.runtime.network_policy import (
    OfflineModeError,
    get_dns_validation_timeout_sec,
    is_block_private_network_egress_enabled,
    is_offline_mode_enabled,
)

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("validate_runtime_websocket_url",)

LOGGER_NAME = "SoAI.core.runtime.websocket_policy"
OPERATION_VALIDATE_WEBSOCKET_URL = "core.runtime.websocket_policy.validate_url"


async def validate_runtime_websocket_url(
    flags: RuntimeFlagsViewProtocol,
    url: str,
    *,
    source: str,
    dns_cache: DnsResolutionCache | None = None,
    block_private_networks: bool | None = None,
) -> str | None:
    if is_offline_mode_enabled(flags):
        try:
            return await enforce_url_local_only_policy_ws(
                url,
                dns_timeout_sec=get_dns_validation_timeout_sec(flags),
                source=source,
                dns_cache=dns_cache,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            log_exception(
                logger,
                exception,
                message="Failed to validate local-only WebSocket policy.",
                operation=OPERATION_VALIDATE_WEBSOCKET_URL,
                details={"source": source, "url": url},
            )
            raise OfflineModeError(
                f"SYSTEM.RUNTIME.STAY_OFFLINE is enabled. {source} cannot access external resources: {url}",
            ) from exception
    should_block_private_networks = (
        is_block_private_network_egress_enabled(flags)
        if block_private_networks is None
        else bool(block_private_networks)
    )
    if not should_block_private_networks:
        return None
    return await enforce_url_network_policy_ws(
        url,
        block_private_networks=True,
        dns_timeout_sec=get_dns_validation_timeout_sec(flags),
        source=source,
        dns_cache=dns_cache,
    )
