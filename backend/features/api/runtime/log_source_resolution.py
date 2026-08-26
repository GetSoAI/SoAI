"""SoAI - Log source name resolution for streaming endpoints [backend/features/api/runtime/log_source_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "build_log_source_details",
    "resolve_log_source_name",
)


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


def build_log_source_details(requested_name: str, resolved_name: str) -> dict[str, str] | None:
    requested = requested_name.strip() if isinstance(requested_name, str) else ""
    resolved = resolved_name.strip() if isinstance(resolved_name, str) else ""
    if not requested or not resolved or requested == resolved:
        return None
    coerced = coerce_json_dict({"requested": requested, "resolved": resolved})
    if coerced is None:
        return None
    requested_value = coerced.get("requested")
    resolved_value = coerced.get("resolved")
    if not isinstance(requested_value, str) or not isinstance(resolved_value, str):
        return None
    if not requested_value or not resolved_value or requested_value == resolved_value:
        return None
    return {"requested": requested_value, "resolved": resolved_value}
