"""SoAI - Guardian plugin candidate filtering [backend/plugins/guardian/candidates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.protocols_instance import PluginInstanceProtocol
from plugins.guardian.check_context import GuardianCheckContext

__all__ = (
    "collect_available_guardian_plugin_names",
    "collect_unlocked_guardian_plugin_names",
    "is_persistent_plugin_instance",
)


def collect_available_guardian_plugin_names(check_context: GuardianCheckContext) -> set[str]:
    return {
        plugin_name
        for plugin_name in check_context.unlocked_plugins
        if plugin_name not in check_context.recovery_in_progress
        and plugin_name not in check_context.busy_plugins
    }


def collect_unlocked_guardian_plugin_names(check_context: GuardianCheckContext) -> list[str]:
    return sorted(
        plugin_name
        for plugin_name in check_context.plugin_states
        if plugin_name and plugin_name in check_context.unlocked_plugins
    )


def is_persistent_plugin_instance(instance: PluginInstanceProtocol) -> bool:
    return bool(instance.PERSISTENT)
