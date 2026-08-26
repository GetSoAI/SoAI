"""SoAI - Model route snapshot helpers [backend/features/api/routes/models/model_snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from fastapi import Request

from core.types.json import JSONDict, JSONValue
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_not_found

__all__ = (
    "get_model_details_snapshot",
    "get_model_list_snapshot",
    "get_model_parameters_snapshot",
)


def _redact_model_path(model_info: Mapping[str, JSONValue]) -> JSONDict:
    payload = dict(model_info)
    payload.pop("path", None)
    return payload


def _redact_model_list_paths(grouped_models: Mapping[str, JSONValue]) -> JSONDict:
    payload: JSONDict = {}
    for key, value in grouped_models.items():
        if isinstance(value, list):
            payload[key] = [
                _redact_model_path(entry) if isinstance(entry, Mapping) else entry
                for entry in value
            ]
        else:
            payload[key] = value
    return payload


async def get_model_list_snapshot(_request: Request, api_context: ApiContext) -> JSONDict:
    model_list = await api_context.dependencies.model_information_service.model_get_formatted_list()
    model_list_payload: JSONDict = {}
    for key, value in model_list.items():
        model_list_payload[key] = value
    return _redact_model_list_paths(model_list_payload)


async def get_model_details_snapshot(
    request: Request,
    api_context: ApiContext,
    universal_id: str,
) -> JSONDict:
    model_info = await api_context.dependencies.model_information_service.model_get_info(
        universal_id,
    )
    if not model_info:
        raise_not_found(request, f"Model '{universal_id}' not found.")
    return _redact_model_path(model_info)


async def get_model_parameters_snapshot(api_context: ApiContext, universal_id: str) -> JSONDict:
    return await api_context.dependencies.model_information_service.model_get_formatted_parameters(
        universal_id,
    )
