"""SoAI - Static plugin hash blocklist policy [backend/plugins/hash_blocklist.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.plugins.errors import PluginIncompatibleError
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.compatibility import CompatibilityInfo, IncompatibilityReason
from plugins.state.compatibility import build_compatibility_info

__all__ = (
    "BLOCKED_PLUGIN_FILE_HASHES",
    "build_blocked_plugin_hash_error",
    "get_blocked_plugin_hash_compatibility",
)

BLOCKED_PLUGIN_FILE_HASHES: frozenset[str] = frozenset(())
_BLOCKLIST_POLICY_NAME = "plugin_hash_blocklist"
_BLOCKLIST_MESSAGE = "Plugin file is blocked by local hash policy."


def get_blocked_plugin_hash_compatibility(file_hash: str) -> CompatibilityInfo | None:
    normalized_hash = str(file_hash or "").strip().lower()
    if not normalized_hash or normalized_hash not in BLOCKED_PLUGIN_FILE_HASHES:
        return None
    return build_compatibility_info(
        IncompatibilityReason.BROKEN_PLUGIN,
        _BLOCKLIST_MESSAGE,
        {
            "blocked": True,
            "policy": _BLOCKLIST_POLICY_NAME,
        },
        False,
    )


def build_blocked_plugin_hash_error(
    plugin_name: str,
    file_hash: str,
    *,
    plugin_class: type[PluginInstanceProtocol] | None = None,
) -> PluginIncompatibleError:
    compatibility = get_blocked_plugin_hash_compatibility(file_hash)
    if compatibility is None:
        raise StateError("Requested blocked-plugin error for a hash that is not blocklisted.")
    return PluginIncompatibleError(plugin_name, compatibility, plugin_class=plugin_class)
