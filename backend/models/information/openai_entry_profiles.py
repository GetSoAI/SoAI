"""SoAI - OpenAI model entry profile assembly [backend/models/information/openai_entry_profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.source_identifier import require_source_model_id
from core.validation.strings import coerce_optional_trimmed_str
from models.capabilities.openai_profile_resolution import (
    compose_model_openai_base_profile,
    resolve_effective_openai_profile,
)
from models.information.openai_entries import (
    build_openai_model_entry,
    enrich_entry_with_capability_profile,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_profiled_openai_model_entry",
    "require_openai_plugin_name",
    "resolve_catalog_openai_model_id",
    "resolve_openai_capability_profile",
)


def require_openai_plugin_name(model_data: JSONDict) -> str:
    plugin_name = coerce_optional_trimmed_str(model_data.get("plugin"))
    if plugin_name:
        return plugin_name
    model_universal_id = coerce_optional_trimmed_str(model_data.get("universal_id")) or "unknown"
    raise ValidationError(
        f"Model '{model_universal_id}' is missing the required plugin reference.",
    )


def resolve_catalog_openai_model_id(model_data: JSONDict) -> str:
    return f"{require_openai_plugin_name(model_data)}/{require_source_model_id(model_data)}"


async def resolve_openai_capability_profile(
    *,
    model_data: JSONDict,
    model_id: str,
    plugin_profiles: dict[str, JSONDict],
    model_get_plugin_capability_profile: Callable[[str], Awaitable[JSONDict]],
) -> JSONDict:
    plugin_name = require_openai_plugin_name(model_data)
    if plugin_name not in plugin_profiles:
        plugin_profiles[plugin_name] = await model_get_plugin_capability_profile(plugin_name)
    overrides_value = model_data.get("openai_capabilities_overrides")
    overrides = overrides_value if isinstance(overrides_value, dict) else None
    base_profile = compose_model_openai_base_profile(
        plugin_profile=plugin_profiles[plugin_name],
        model_data=model_data,
    )
    return resolve_effective_openai_profile(
        model_id=model_id,
        base_profile=base_profile,
        overrides=overrides,
    )


async def build_profiled_openai_model_entry(
    *,
    model_data: JSONDict,
    model_id: str,
    providers_map: dict[str, JSONDict],
    plugin_profiles: dict[str, JSONDict],
    model_get_plugin_capability_profile: Callable[[str], Awaitable[JSONDict]],
    context_window_tokens: int | None,
) -> tuple[JSONDict, JSONDict]:
    model_data_with_context = dict(model_data)
    if context_window_tokens is not None:
        model_data_with_context["context_window_tokens"] = context_window_tokens
    entry = build_openai_model_entry(model_id, model_data_with_context, providers_map)
    effective_profile = await resolve_openai_capability_profile(
        model_data=model_data,
        model_id=model_id,
        plugin_profiles=plugin_profiles,
        model_get_plugin_capability_profile=model_get_plugin_capability_profile,
    )
    enrich_entry_with_capability_profile(entry, effective_profile)
    return entry, effective_profile
