"""SoAI - Playwright runtime option resolution [backend/mcp/tools/browser/playwright_runtime_options.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.browser.config_values import (
    browser_bounded_int,
    resolve_browser_dns_timeout_sec,
)
from mcp.tools.browser.profile_config import resolve_profile_config

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "PlaywrightRuntimeOptions",
    "resolve_playwright_runtime_options",
)


@dataclass(frozen=True, slots=True)
class PlaywrightRuntimeOptions:
    headless: bool
    channel: str | None
    runtime_key: str
    cdp_url: str | None
    dns_timeout_sec: float
    cdp_connect_timeout_ms: int


def resolve_playwright_runtime_options(
    config: ConfigProtocol,
    *,
    profile: str,
) -> PlaywrightRuntimeOptions:
    profile_cfg = resolve_profile_config(config, profile=profile)
    headless = (
        bool(config.get_bool("TOOLS.MCP.BROWSER.HEADLESS"))
        if profile_cfg.headless is None
        else bool(profile_cfg.headless)
    )
    channel_key = profile_cfg.channel if profile_cfg.channel is not None else "bundled"
    runtime_key = f"local:channel={channel_key}:headless={str(headless).lower()}"
    if profile_cfg.cdp_url is not None:
        runtime_key = f"cdp:{profile_cfg.name}"
    return PlaywrightRuntimeOptions(
        headless=headless,
        channel=profile_cfg.channel,
        runtime_key=runtime_key,
        cdp_url=profile_cfg.cdp_url,
        dns_timeout_sec=resolve_browser_dns_timeout_sec(config),
        cdp_connect_timeout_ms=browser_bounded_int(
            config,
            "TOOLS.MCP.BROWSER.CDP_CONNECT_TIMEOUT_MS",
            30000,
            min_value=1000,
            max_value=300000,
        ),
    )
