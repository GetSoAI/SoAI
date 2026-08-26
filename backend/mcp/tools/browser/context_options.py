"""SoAI - Browser context option resolution [backend/mcp/tools/browser/context_options.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.browser.profile_config import resolve_profile_config

if TYPE_CHECKING:
    from playwright.async_api import ViewportSize

    from core.config.protocols import ConfigProtocol

__all__ = (
    "BrowserContextOptions",
    "resolve_browser_context_options",
)


@dataclass(frozen=True, slots=True)
class BrowserContextOptions:
    locale: str | None
    timezone_id: str | None
    extra_http_headers: dict[str, str] | None
    viewport: ViewportSize | None
    device_scale_factor: float | None


def resolve_browser_context_options(
    config: ConfigProtocol,
    *,
    profile: str,
) -> BrowserContextOptions:
    profile_config = resolve_profile_config(config, profile=profile)
    extra_http_headers = None
    if profile_config.accept_language is not None:
        extra_http_headers = {"Accept-Language": profile_config.accept_language}
    viewport: ViewportSize | None = None
    if profile_config.viewport_width is not None and profile_config.viewport_height is not None:
        viewport = {
            "width": int(profile_config.viewport_width),
            "height": int(profile_config.viewport_height),
        }
    return BrowserContextOptions(
        locale=profile_config.locale,
        timezone_id=profile_config.timezone_id,
        extra_http_headers=extra_http_headers,
        viewport=viewport,
        device_scale_factor=profile_config.device_scale_factor,
    )
