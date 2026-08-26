"""SoAI - Canonical resolved model record enrichment [backend/models/resolved_record.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.source_identifier import require_source_model_id
from core.openai.effective_profile import compute_effective_openai_model_profile
from core.validation.boolean_coercion import coerce_bool_with_default
from core.validation.strings import coerce_optional_trimmed_str
from models.capabilities.openai_profile_resolution import compose_model_openai_base_profile
from models.manager.capabilities import derive_model_category_type, derive_model_type

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("enrich_resolved_model_record",)


def enrich_resolved_model_record(
    model_info: JSONDict,
    plugin_info: JSONDict | None,
) -> JSONDict:
    resolved = dict(model_info)
    resolved["is_enabled"] = coerce_bool_with_default(
        resolved.get("is_enabled"),
        default=True,
        strict=True,
    )
    model_type = derive_model_type(resolved, plugin_info)
    if model_type:
        resolved["model_type"] = model_type
    resolved["type"] = derive_model_category_type(resolved, plugin_info)
    overrides_value = resolved.get("openai_capabilities_overrides")
    overrides = overrides_value if isinstance(overrides_value, dict) else None
    if plugin_info is not None:
        base_profile = compose_model_openai_base_profile(
            plugin_profile=plugin_info,
            model_data=resolved,
        )
        effective_modalities, effective_caps = compute_effective_openai_model_profile(
            base_modalities=base_profile.get("modalities"),
            base_openai_capabilities=base_profile.get("openai_capabilities"),
            overrides=overrides or {},
        )
        resolved["modalities"] = effective_modalities
        resolved["openai_capabilities"] = effective_caps
    if overrides is not None:
        resolved["openai_capabilities_overrides"] = dict(overrides)
    resolved["source_model_id"] = require_source_model_id(resolved)
    plugin_name = coerce_optional_trimmed_str(resolved.get("plugin"))
    if plugin_name:
        resolved["plugin"] = plugin_name
    return resolved
