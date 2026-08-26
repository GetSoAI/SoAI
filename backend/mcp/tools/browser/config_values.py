"""SoAI - Browser config value coercion helpers [backend/mcp/tools/browser/config_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric_lenient import (
    coerce_lenient_bounded_float,
    coerce_lenient_clamped_int,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "browser_bool",
    "browser_bounded_int",
    "browser_min_float",
    "browser_min_int",
    "resolve_browser_default_nav_timeout_sec",
    "resolve_browser_dns_timeout_sec",
    "resolve_browser_max_concurrent_pages",
    "resolve_browser_render_stabilize_ms",
    "resolve_web_fetch_block_private_networks",
    "resolve_web_fetch_dns_timeout_sec",
)

BROWSER_MAX_CONCURRENT_PAGES_KEY = "TOOLS.MCP.BROWSER.MAX_CONCURRENT_PAGES"
DEFAULT_BROWSER_MAX_CONCURRENT_PAGES = 10
HARD_MAX_BROWSER_CONCURRENT_PAGES = 32


def browser_bool(config: ConfigProtocol, key: str) -> bool:
    return bool(config.get_bool(key))


def browser_min_int(config: ConfigProtocol, key: str, default: int, *, min_value: int) -> int:
    return coerce_lenient_clamped_int(
        config.get(key),
        default=default,
        minimum=min_value,
    )


def browser_bounded_int(
    config: ConfigProtocol,
    key: str,
    default: int,
    *,
    min_value: int,
    max_value: int,
) -> int:
    return coerce_lenient_clamped_int(
        config.get(key),
        default=default,
        minimum=min_value,
        maximum=max_value,
    )


def browser_min_float(
    config: ConfigProtocol,
    key: str,
    default: float,
    *,
    min_value: float,
) -> float:
    return coerce_lenient_bounded_float(
        config.get(key),
        default=default,
        minimum=min_value,
    )


def resolve_browser_default_nav_timeout_sec(config: ConfigProtocol) -> int:
    return browser_min_int(config, "TOOLS.MCP.BROWSER.DEFAULT_NAV_TIMEOUT_SEC", 30, min_value=1)


def resolve_browser_render_stabilize_ms(config: ConfigProtocol) -> int:
    return browser_bounded_int(
        config,
        "TOOLS.MCP.BROWSER.RENDER_STABILIZE_MS",
        250,
        min_value=0,
        max_value=60_000,
    )


def resolve_browser_max_concurrent_pages(config: ConfigProtocol) -> int:
    return browser_bounded_int(
        config,
        BROWSER_MAX_CONCURRENT_PAGES_KEY,
        DEFAULT_BROWSER_MAX_CONCURRENT_PAGES,
        min_value=1,
        max_value=HARD_MAX_BROWSER_CONCURRENT_PAGES,
    )


def resolve_browser_dns_timeout_sec(config: ConfigProtocol) -> float:
    return coerce_lenient_bounded_float(
        config.get("TOOLS.MCP.BROWSER.DNS_TIMEOUT_SEC"),
        default=5.0,
        minimum=0.5,
        maximum=30.0,
    )


def resolve_web_fetch_block_private_networks(config: ConfigProtocol) -> bool:
    return bool(config.get_bool("TOOLS.MCP.WEB_FETCH.BLOCK_PRIVATE_NETWORK_EGRESS"))


def resolve_web_fetch_dns_timeout_sec(config: ConfigProtocol) -> float:
    return coerce_lenient_bounded_float(
        config.get("TOOLS.MCP.WEB_FETCH.DNS_TIMEOUT_SEC"),
        default=5.0,
        minimum=0.5,
        maximum=30.0,
    )
