"""SoAI - External provider list snapshot projection [backend/features/api/routes/plugins/provider_list_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict
from features.api.routes.plugins.provider_lifecycle_operations import (
    coerce_provider_record_or_server_error,
    ensure_external_provider_support,
)
from features.api.runtime.context import resolve_api_context

__all__ = ("get_provider_list_snapshot",)


async def get_provider_list_snapshot(request: Request) -> list[JSONDict]:
    plugin_name = request.path_params["plugin_name"]
    api_context = resolve_api_context(request)
    canonical_plugin_name, _display_name = await ensure_external_provider_support(
        request,
        plugin_name,
        api_context.dependencies.plugin_manager,
    )
    providers = await api_context.dependencies.model_provider_coordinator.provider_list_for_plugin(
        canonical_plugin_name,
    )
    result: list[JSONDict] = []
    for provider in providers:
        record = coerce_provider_record_or_server_error(
            request,
            provider,
            label="External provider record",
        )
        coerced = coerce_json_dict(normalize_for_json(record))
        if coerced is None:
            raise ValidationError("Failed to normalize provider record for response.")
        result.append(coerced)
    return result
