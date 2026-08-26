"""SoAI - Config reload revision tracking [backend/orchestrator/lifecycle/config_reload_revision_tracker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from orchestrator.lifecycle.config_reload_result import (
    PluginConfigReloadOutcome,
    PluginConfigReloadResult,
)

__all__ = ("ConfigReloadRevisionTracker",)


class ConfigReloadRevisionTracker:
    def __init__(self) -> None:
        self._latest_seen_config_revision_by_name: dict[str, int] = {}
        self._latest_applied_config_revision_by_name: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def record_seen(
        self,
        plugin_name: str,
        revision: int,
    ) -> PluginConfigReloadResult | None:
        async with self._lock:
            latest_applied = int(self._latest_applied_config_revision_by_name.get(plugin_name, 0))
            if revision <= latest_applied:
                return PluginConfigReloadResult(PluginConfigReloadOutcome.SUPERSEDED)
            latest_seen = int(self._latest_seen_config_revision_by_name.get(plugin_name, 0))
            if revision < latest_seen:
                return PluginConfigReloadResult(PluginConfigReloadOutcome.SUPERSEDED)
            if revision > latest_seen:
                self._latest_seen_config_revision_by_name[plugin_name] = revision
            return None

    async def record_applied(self, plugin_name: str, revision: int) -> None:
        async with self._lock:
            latest_applied = int(self._latest_applied_config_revision_by_name.get(plugin_name, 0))
            if revision > latest_applied:
                self._latest_applied_config_revision_by_name[plugin_name] = revision
            latest_seen = int(self._latest_seen_config_revision_by_name.get(plugin_name, 0))
            if revision > latest_seen:
                self._latest_seen_config_revision_by_name[plugin_name] = revision
