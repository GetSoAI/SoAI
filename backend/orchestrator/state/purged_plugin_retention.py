"""SoAI - Purged plugin retention policy [backend/orchestrator/state/purged_plugin_retention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("prune_purged_plugins",)

PURGED_PLUGIN_TTL_SECONDS: float = 3600.0
PURGED_PLUGIN_MAX_SIZE: int = 4096
PURGED_PLUGIN_PRUNE_INTERVAL_SECONDS: float = 300.0


def prune_purged_plugins(
    purged_plugins: dict[str, float],
    now_monotonic: float,
    next_prune_at: float,
    *,
    force: bool = False,
) -> float:
    if (not force) and now_monotonic < next_prune_at:
        return next_prune_at
    min_allowed_timestamp = now_monotonic - PURGED_PLUGIN_TTL_SECONDS
    expired_plugin_names = [
        plugin_name
        for plugin_name, purged_at_monotonic in purged_plugins.items()
        if purged_at_monotonic <= min_allowed_timestamp
    ]
    for plugin_name in expired_plugin_names:
        purged_plugins.pop(plugin_name, None)
    overflow_count = len(purged_plugins) - PURGED_PLUGIN_MAX_SIZE
    if overflow_count > 0:
        oldest_entries = sorted(purged_plugins.items(), key=lambda item: item[1])[:overflow_count]
        for plugin_name, _ in oldest_entries:
            purged_plugins.pop(plugin_name, None)
    return now_monotonic + PURGED_PLUGIN_PRUNE_INTERVAL_SECONDS
