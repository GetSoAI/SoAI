"""SoAI - Model info field extraction helpers [backend/core/models/model_info_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.validation.boolean_coercion import coerce_bool_with_default

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_plugin_name",
    "is_model_info_active_and_enabled",
    "resolve_plugin_name_from_model_info",
)


def coerce_plugin_name(model_info: JSONDict | None) -> str | None:
    if not model_info:
        return None
    plugin_value = model_info.get("plugin")
    if not isinstance(plugin_value, str):
        return None
    plugin_name = plugin_value.strip()
    return plugin_name or None


def is_model_info_active_and_enabled(
    model_info: Mapping[str, JSONValue] | None,
) -> bool:
    if not model_info:
        return False
    status_value = model_info.get("status", "active")
    if isinstance(status_value, str) and status_value != "active":
        return False
    return coerce_bool_with_default(model_info.get("is_enabled"), default=True, strict=True)


def resolve_plugin_name_from_model_info(
    model_info: JSONDict | None,
    *,
    universal_id: str,
) -> tuple[str | None, str | None]:
    if not universal_id:
        return (None, "Model universal_id is required.")
    if not model_info:
        return (None, f"Model info for {universal_id} not found.")
    plugin_name = coerce_plugin_name(model_info)
    if plugin_name is None:
        return (None, f"Model info for {universal_id} missing plugin name.")
    return (plugin_name, None)
