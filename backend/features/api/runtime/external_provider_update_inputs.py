"""SoAI - External provider update validation input merging [backend/features/api/runtime/external_provider_update_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.models.external_provider_record import (
    ExternalProviderInternalRecord,
    ExternalProviderRecord,
)
from core.types.json import JSONDict, JSONValue, is_json_dict

__all__ = (
    "ExternalProviderUpdateValidationInput",
    "build_external_provider_update_validation_input",
)


@dataclass(frozen=True, slots=True)
class ExternalProviderUpdateValidationInput:
    api_url: str
    api_key: str | None
    extra_headers: JSONDict | None
    extra_query_params: JSONDict | None


def _merged_api_key(
    update_data: JSONDict,
    existing_decrypted: ExternalProviderInternalRecord,
) -> str | None:
    if "api_key" in update_data:
        api_key = update_data.get("api_key")
        return str(api_key) if isinstance(api_key, str) else None
    existing_api_key = existing_decrypted.get("api_key")
    return str(existing_api_key) if isinstance(existing_api_key, str) else None


def _merged_mapping(
    update_data: JSONDict,
    existing_decrypted: ExternalProviderInternalRecord,
    field_name: str,
) -> JSONDict | None:
    value: JSONValue = (
        update_data.get(field_name)
        if field_name in update_data
        else _existing_mapping_value(existing_decrypted, field_name)
    )
    return value if is_json_dict(value) else None


def _existing_mapping_value(
    existing_decrypted: ExternalProviderInternalRecord,
    field_name: str,
) -> JSONValue:
    if field_name == "extra_headers":
        return existing_decrypted.get("extra_headers")
    if field_name == "extra_query_params":
        return existing_decrypted.get("extra_query_params")
    return None


def build_external_provider_update_validation_input(
    update_data: JSONDict,
    provider_record: ExternalProviderRecord,
    existing_decrypted: ExternalProviderInternalRecord,
) -> ExternalProviderUpdateValidationInput:
    api_url = (
        str(update_data["api_url"])
        if "api_url" in update_data and update_data["api_url"] is not None
        else str(provider_record.get("api_url") or "")
    )
    return ExternalProviderUpdateValidationInput(
        api_url=api_url,
        api_key=_merged_api_key(update_data, existing_decrypted),
        extra_headers=_merged_mapping(update_data, existing_decrypted, "extra_headers"),
        extra_query_params=_merged_mapping(
            update_data,
            existing_decrypted,
            "extra_query_params",
        ),
    )
