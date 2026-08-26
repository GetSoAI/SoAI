"""SoAI - Plugin scheduler warning throttles [backend/orchestrator/scheduling/plugin_warning_throttles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.rate_limited_logger import RateLimitedLogger

__all__ = (
    "format_suppressed_warning_suffix",
    "get_plugin_warning_throttle",
)


def format_suppressed_warning_suffix(suppressed: int) -> str:
    if suppressed:
        return f" (suppressed {suppressed} repeats)"
    return ""


def get_plugin_warning_throttle(
    warners: dict[str, RateLimitedLogger],
    plugin_name: str,
    *,
    interval_seconds: float,
) -> RateLimitedLogger:
    warner = warners.get(plugin_name)
    if warner is None:
        warner = RateLimitedLogger(interval_seconds=interval_seconds)
        warners[plugin_name] = warner
    return warner
