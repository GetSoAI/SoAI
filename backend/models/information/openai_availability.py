"""SoAI - OpenAI model list availability filtering [backend/models/information/openai_availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.model_info_fields import is_model_info_active_and_enabled
from core.models.provider_backing import is_provider_backed_model
from core.state.plugin_health_resolution import plugin_state_is_available
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.state.protocols import ImmutablePluginStates
    from core.types.json import JSONDict

__all__ = ("is_model_available_for_openai_api",)


def is_model_available_for_openai_api(
    model_data: JSONDict,
    *,
    all_plugin_states: ImmutablePluginStates,
    installed_plugin_names_ref: Callable[[], set[str]],
) -> bool:
    plugin_name = coerce_optional_trimmed_str(model_data.get("plugin"))
    if not plugin_name or plugin_name not in installed_plugin_names_ref():
        return False
    if not is_model_info_active_and_enabled(model_data):
        return False
    plugin_state_info = all_plugin_states.get(plugin_name)
    if plugin_state_info is None:
        return True
    provider_backed = is_provider_backed_model(model_data)
    return plugin_state_is_available(
        plugin_state_info,
        provider_backed=provider_backed,
    )
