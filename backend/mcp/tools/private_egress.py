"""SoAI - MCP shared private-network egress resolution for outbound tool URLs [backend/mcp/tools/private_egress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric_lenient import coerce_lenient_bounded_float
from core.network.policy import enforce_url_network_policy
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC, MODERATE_DELAY_SEC

if TYPE_CHECKING:
    from core.config.numeric_lenient import NumericCoercible

__all__ = ("resolve_private_egress_pinned_host",)


async def resolve_private_egress_pinned_host(
    *,
    url: str,
    egress_blocking_enabled: bool,
    offline_mode_enabled: bool,
    dns_timeout_value: NumericCoercible | None,
    source: str,
) -> str | None:
    if not egress_blocking_enabled or offline_mode_enabled:
        return None
    dns_timeout_sec = coerce_lenient_bounded_float(
        dns_timeout_value,
        default=float(LOCAL_IO_TIMEOUT_SEC),
        minimum=MODERATE_DELAY_SEC,
        maximum=float(INTERACTIVE_TIMEOUT_SEC),
    )
    return await enforce_url_network_policy(
        url,
        block_private_networks=True,
        dns_timeout_sec=dns_timeout_sec,
        source=source,
    )
