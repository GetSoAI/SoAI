"""SoAI - OpenAI model entry formatting primitives [backend/models/information/openai_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.durations import ms_to_seconds_floor
from core.timing.epoch import EPOCH_MS_DETECTION_FLOOR, epoch_seconds
from core.types.json_value import copy_json_dict
from core.validation.coercion import coerce_int
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_openai_model_entry",
    "build_virtual_model_openai_entry",
    "coerce_timestamp_to_int",
    "enrich_entry_with_capability_profile",
    "extract_model_timestamp",
    "model_sort_key",
    "resolve_model_owner",
)


def model_sort_key(entry: JSONDict) -> str:
    value = entry.get("id")
    return value if isinstance(value, str) else ""


def build_virtual_model_openai_entry(name: str, created_at: int) -> JSONDict:
    return {
        "id": name,
        "object": "model",
        "created": coerce_timestamp_to_int(created_at),
        "owned_by": "soai-router",
    }


def enrich_entry_with_capability_profile(entry: JSONDict, profile: JSONDict) -> None:
    modalities = profile.get("modalities")
    if isinstance(modalities, list | tuple):
        normalized_modalities = [
            item for item in modalities if isinstance(item, str) and item.strip()
        ]
        if normalized_modalities:
            entry["modalities"] = normalized_modalities
    openai_capabilities = profile.get("openai_capabilities")
    if isinstance(openai_capabilities, dict):
        entry["openai_capabilities"] = copy_json_dict(openai_capabilities)


def coerce_timestamp_to_int(value: JSONValue) -> int:
    timestamp = int(epoch_seconds())
    coerced = coerce_int(value)
    if coerced is not None:
        timestamp = coerced
    if timestamp >= EPOCH_MS_DETECTION_FLOOR:
        return ms_to_seconds_floor(timestamp)
    return timestamp


def extract_model_timestamp(model_data: JSONDict) -> JSONValue:
    return model_data.get("last_modified_at_ms")


def resolve_model_owner(
    model_data: JSONDict,
    provider_map: dict[str, JSONDict] | None = None,
) -> str:
    provider_id = coerce_optional_trimmed_str(model_data.get("provider_id"))
    if provider_id and provider_map:
        provider_entry = provider_map.get(provider_id)
        if provider_entry:
            provider_name = provider_entry.get("name")
            return str(provider_name) if provider_name else provider_id
    return (
        coerce_optional_trimmed_str(model_data.get("owned_by"))
        or coerce_optional_trimmed_str(model_data.get("plugin"))
        or "unknown"
    )


def build_openai_model_entry(
    model_id: str,
    model_data: JSONDict,
    providers_map: dict[str, JSONDict],
) -> JSONDict:
    entry: JSONDict = {
        "id": model_id,
        "object": "model",
        "created": coerce_timestamp_to_int(extract_model_timestamp(model_data)),
        "owned_by": resolve_model_owner(model_data, providers_map),
    }
    context_window_tokens_value = model_data.get("context_window_tokens")
    if is_strict_int(context_window_tokens_value):
        if context_window_tokens_value > 0:
            entry["context_window_tokens"] = context_window_tokens_value
    return entry
