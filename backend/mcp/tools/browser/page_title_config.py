"""SoAI - Browser page title retry config [backend/mcp/tools/browser/page_title_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol
from mcp.tools.argument_scalars import parse_int

__all__ = (
    "resolve_title_retry_attempts",
    "resolve_title_retry_delay_ms",
)


def resolve_title_retry_attempts(config: ConfigProtocol) -> int:
    raw = config.get_int("TOOLS.MCP.BROWSER.TITLE_RETRY_ATTEMPTS")
    return parse_int(raw, default=3, min_value=0, max_value=10)


def resolve_title_retry_delay_ms(config: ConfigProtocol) -> int:
    raw = config.get_int("TOOLS.MCP.BROWSER.TITLE_RETRY_DELAY_MS")
    return parse_int(raw, default=100, min_value=0, max_value=2000)
