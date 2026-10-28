"""SoAI - Model OpenAI capability override actions [backend/models/actions/openai_capability_overrides.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.capability_override_updates import (
    require_current_openai_capability_override_snapshot,
    resolve_openai_capability_override_replacement,
    resolve_openai_capability_override_update,
)
from core.types.json_value import coerce_json_dict
from models.actions.dependencies import ModelActionsServiceDependencies
from models.manager.capabilities import normalize_plugin_record

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "replace_model_openai_capability_overrides",
    "reset_model_openai_capability_overrides",
    "update_model_openai_capability_override",
)


async def _require_plugin_record(
    deps: ModelActionsServiceDependencies, plugin_name: str
) -> JSONDict:
    plugin_record_raw = await deps.database_plugins.get_plugin_by_name(plugin_name)
    plugin_record = (
        normalize_plugin_record(coerced)
        if (coerced := coerce_json_dict(plugin_record_raw)) is not None
        else None
    )
    if not plugin_record:
        raise ValidationError(f"Plugin '{plugin_name}' not found.")
    return plugin_record


async def _read_current_overrides(
    deps: ModelActionsServiceDependencies, universal_id: str
) -> JSONValue:
    current_info = await deps.database_models.get_model_info(universal_id)
    return (
        current_info.get("openai_capabilities_overrides")
        if isinstance(current_info, dict)
        else None
    )


async def update_model_openai_capability_override(
    deps: ModelActionsServiceDependencies,
    *,
    universal_id: str,
    plugin_name: str,
    category: str,
    token: str,
    enabled: bool,
) -> None:
    plugin_record = await _require_plugin_record(deps, plugin_name)
    async with deps.model_record_locks[universal_id]:
        current_overrides_value = await _read_current_overrides(deps, universal_id)
        update = resolve_openai_capability_override_update(
            base_modalities=plugin_record.get("modalities"),
            base_openai_capabilities=plugin_record.get("openai_capabilities"),
            current_overrides=current_overrides_value or {},
            category=category,
            token=token,
            enabled=enabled,
            universal_id=universal_id,
            plugin_name=plugin_name,
        )
        if not update.changed:
            return
        updated = await deps.database_models.update_model_openai_capabilities_overrides(
            universal_id,
            update.next_payload,
        )
        if not updated:
            raise ValidationError(
                f"Failed to update OpenAI capability overrides for model '{universal_id}'.",
            )


async def replace_model_openai_capability_overrides(
    deps: ModelActionsServiceDependencies,
    *,
    universal_id: str,
    plugin_name: str,
    disabled: Mapping[str, Sequence[str]],
    enabled: Mapping[str, Sequence[str]],
    expected: JSONValue,
) -> bool:
    plugin_record = await _require_plugin_record(deps, plugin_name)
    next_payload = resolve_openai_capability_override_replacement(
        base_modalities=plugin_record.get("modalities"),
        base_openai_capabilities=plugin_record.get("openai_capabilities"),
        disabled=disabled,
        enabled=enabled,
        universal_id=universal_id,
        plugin_name=plugin_name,
    )
    async with deps.model_record_locks[universal_id]:
        current_snapshot = require_current_openai_capability_override_snapshot(
            current_overrides=await _read_current_overrides(deps, universal_id),
            expected_overrides=expected,
            universal_id=universal_id,
        )
        if current_snapshot == next_payload:
            return False
        updated = await deps.database_models.update_model_openai_capabilities_overrides(
            universal_id,
            next_payload,
        )
        if not updated:
            raise ValidationError(
                f"Failed to update OpenAI capability overrides for model '{universal_id}'.",
            )
    return True


async def reset_model_openai_capability_overrides(
    deps: ModelActionsServiceDependencies,
    *,
    universal_id: str,
) -> None:
    async with deps.model_record_locks[universal_id]:
        current_overrides = await _read_current_overrides(deps, universal_id)
        if current_overrides is None:
            return
        updated = await deps.database_models.update_model_openai_capabilities_overrides(
            universal_id,
            None,
        )
        if not updated:
            raise ValidationError(
                f"Failed to reset OpenAI capability overrides for model '{universal_id}'.",
            )
