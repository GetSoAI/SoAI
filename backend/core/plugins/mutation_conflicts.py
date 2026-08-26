"""SoAI - Plugin lifecycle mutation conflict identities [backend/core/plugins/mutation_conflicts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.portable_identifiers import (
    is_portable_plugin_identifier,
    require_portable_plugin_identifier,
)

__all__ = (
    "build_plugin_lifecycle_conflict_key",
    "extract_plugin_lifecycle_conflict_target",
)

PREFIX = "plugin:"
SUFFIX = ":lifecycle"


def build_plugin_lifecycle_conflict_key(plugin_name: str) -> str:
    normalized = require_portable_plugin_identifier(plugin_name, field_name="plugin_name")
    return f"{PREFIX}{normalized}{SUFFIX}"


def extract_plugin_lifecycle_conflict_target(conflict_key: str) -> str | None:
    if not conflict_key.startswith(PREFIX) or not conflict_key.endswith(SUFFIX):
        return None
    target = conflict_key[len(PREFIX) : -len(SUFFIX)]
    return target if is_portable_plugin_identifier(target) else None
