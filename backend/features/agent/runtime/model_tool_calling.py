"""SoAI - Shared model tool-calling capability checks [backend/features/agent/runtime/model_tool_calling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.models.model_info_fields import is_model_info_active_and_enabled
from core.openai.capability_checks import (
    is_openai_model_capability_enabled,
    is_openai_model_vision_input_supported,
)
from core.openai.request_fields import resolve_optional_model_name
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.context import ApiContext

__all__ = (
    "build_supports_tool_calling_callable",
    "model_supports_tool_calling",
    "model_supports_vision_input",
    "request_model_supports_tool_calling",
)


def build_supports_tool_calling_callable(
    deps: ApiDependencies,
) -> Callable[[str], Awaitable[bool]]:
    async def supports_tool_calling(model_id: str) -> bool:
        return await model_supports_tool_calling(deps, model_id)

    return supports_tool_calling


async def _virtual_model_infos(
    deps: ApiDependencies,
    model_id: str,
) -> list[Mapping[str, JSONValue]]:
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        return []
    virtual_model = deps.model_virtual_model_service.virtual_model_get(normalized_model_id)
    if not virtual_model:
        return []
    universal_ids = [
        entry.universal_id
        for entry in (virtual_model.models or [])
        if entry is not None and entry.universal_id
    ]
    if not universal_ids:
        return []
    model_info_map = await deps.model_information_service.model_get_info_batch(universal_ids)
    if not isinstance(model_info_map, dict):
        raise StateError("Model information service returned an invalid batch result.")
    return [
        model_info
        for universal_id in universal_ids
        if isinstance((model_info := model_info_map.get(universal_id)), Mapping)
    ]


async def _resolved_model_info(
    deps: ApiDependencies,
    model_id: str,
) -> Mapping[str, JSONValue] | None:
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        return None
    universal_id = await deps.model_resolution_service.model_resolve_to_universal_id(
        normalized_model_id,
    )
    if not universal_id:
        return None
    model_info = await deps.model_information_service.model_get_info(universal_id)
    if not isinstance(model_info, Mapping):
        return None
    return model_info


async def model_supports_tool_calling(
    deps: ApiDependencies,
    model_id: str,
) -> bool:
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        return False

    virtual_infos = await _virtual_model_infos(deps, normalized_model_id)
    if virtual_infos:
        for info in virtual_infos:
            if not is_model_info_active_and_enabled(info):
                continue
            if is_openai_model_capability_enabled(
                info,
                category="chat_features",
                token="tool_calling",
            ):
                return True
        return False

    model_info = await _resolved_model_info(deps, normalized_model_id)
    if model_info is None:
        return False
    if not is_model_info_active_and_enabled(model_info):
        return False
    return is_openai_model_capability_enabled(
        model_info,
        category="chat_features",
        token="tool_calling",
    )


async def model_supports_vision_input(
    deps: ApiDependencies,
    model_id: str,
) -> bool:
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        return False
    virtual_infos = await _virtual_model_infos(deps, normalized_model_id)
    if virtual_infos:
        return any(
            is_model_info_active_and_enabled(info) and is_openai_model_vision_input_supported(info)
            for info in virtual_infos
        )
    model_info = await _resolved_model_info(deps, normalized_model_id)
    if model_info is None:
        return False
    if not is_model_info_active_and_enabled(model_info):
        return False
    return is_openai_model_vision_input_supported(model_info)


async def request_model_supports_tool_calling(
    api_context: ApiContext,
    request_json: Mapping[str, JSONValue],
) -> bool:
    model_name = resolve_optional_model_name(request_json)
    if model_name is None:
        return False
    return await model_supports_tool_calling(api_context.dependencies, model_name)
