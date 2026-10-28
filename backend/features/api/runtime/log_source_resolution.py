"""SoAI - Log source name resolution for streaming endpoints [backend/features/api/runtime/log_source_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("resolve_log_source_name",)


def resolve_log_source_name(api_dependencies: ApiDependencies, requested_name: str) -> str:
    trimmed = requested_name.strip() if isinstance(requested_name, str) else ""
    if not trimmed:
        return ""
    log_manager = api_dependencies.log_manager
    if log_manager is None:
        return trimmed
    if log_manager.has_log_source(trimmed):
        return trimmed
    lower = trimmed.lower()
    if lower and log_manager.has_log_source(lower):
        return lower
    normalized = api_dependencies.plugin_manager.normalize_plugin_name(trimmed)
    if isinstance(normalized, str) and normalized and log_manager.has_log_source(normalized):
        return normalized
    return trimmed
