"""SoAI - Model capability and modality normalization utilities [backend/models/manager/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.models.model_type_normalization import normalize_model_type_tokens
from core.models.provider_backing import is_provider_backed_model
from core.openai.capabilities import normalize_openai_capabilities
from core.openai.compatibility import (
    ExternalProviderMode,
    normalize_external_provider_mode,
    normalize_openai_modalities_strict,
)
from core.serialization.json_parsing import parse_json_value
from core.types.json_value import copy_json_dict
from core.validation.boolean_coercion import coerce_bool_flag

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "derive_model_category_type",
    "derive_model_type",
    "normalize_modalities_value",
    "normalize_openai_capabilities_value",
    "normalize_plugin_record",
)

LOGGER_NAME = "SoAI.models.manager.capabilities"


def normalize_plugin_record(record: JSONDict) -> JSONDict:
    normalized = copy_json_dict(record)
    if "modalities" in normalized:
        normalized["modalities"] = normalize_modalities_value(normalized.get("modalities"))
    if "openai_capabilities" in normalized:
        normalized["openai_capabilities"] = normalize_openai_capabilities_value(
            normalized.get("openai_capabilities"),
        )
    external_provider_mode_value = normalized.get("external_provider_mode")
    normalized["external_provider_mode"] = normalize_external_provider_mode(
        external_provider_mode_value if isinstance(external_provider_mode_value, str) else None,
    ).value
    return normalized


def normalize_modalities_value(value: JSONValue) -> list[JSONValue]:
    logger = get_logger(LOGGER_NAME)
    if isinstance(value, str):
        raw_text = value
        try:
            value = parse_json_value(raw_text)
        except (ValidationError, TypeError) as error:
            truncated = raw_text[:100] if len(raw_text) > 100 else raw_text
            logger.warning(
                "Failed to parse modalities value as JSON: %s",
                truncated,
            )
            raise ValidationError("Invalid modalities value (must be JSON array).") from error
    raw_items = [
        str(item).strip()
        for item in (value if isinstance(value, list | tuple | set) else [])
        if str(item).strip()
    ]
    normalized = normalize_openai_modalities_strict(raw_items, field_name="modalities")
    payload: list[JSONValue] = []
    for item in normalized:
        payload.append(item)
    return payload


def normalize_openai_capabilities_value(value: JSONValue) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    return normalize_openai_capabilities(value, logger_instance=logger)


def _parse_plugin_model_types(plugin_info: JSONDict | None) -> list[str]:
    if not plugin_info:
        return []
    raw_value = plugin_info.get("model_types")
    if isinstance(raw_value, str):
        try:
            raw_value = parse_json_value(raw_value)
        except (ValidationError, TypeError):
            raw_value = []
    if not isinstance(raw_value, list | tuple | set):
        return []
    return list(normalize_model_type_tokens(str(item) for item in raw_value))


def _has_external_markers(model_data: JSONDict) -> bool:
    if is_provider_backed_model(model_data):
        return True
    tags_value = model_data.get("tags")
    if isinstance(tags_value, str):
        try:
            tags_value = parse_json_value(tags_value)
        except (ValidationError, TypeError):
            tags_value = []
    if not isinstance(tags_value, list | tuple | set):
        return False
    for raw_tag in tags_value:
        normalized_tag = str(raw_tag or "").strip().lower()
        if not normalized_tag:
            continue
        if normalized_tag in {"external", "external_provider"}:
            return True
    return False


def derive_model_category_type(model_data: JSONDict, plugin_info: JSONDict | None) -> str:
    if is_provider_backed_model(model_data):
        return "cloud"
    if _has_external_markers(model_data):
        return "cloud"
    if plugin_info is not None and "local_models" in plugin_info:
        local_models = coerce_bool_flag(
            plugin_info.get("local_models"),
            logger=get_logger(LOGGER_NAME),
            operation="models.manager.capabilities.coerce_bool_flag.local_models",
            default=True,
            recover_message="Failed to parse local_models flag (non-critical).",
        )
        return "local" if local_models else "cloud"
    path_value = model_data.get("path")
    if isinstance(path_value, str) and path_value.strip():
        return "local"
    return "cloud"


def derive_model_type(model_data: JSONDict, plugin_info: JSONDict | None) -> str | None:
    plugin_name_value = model_data.get("plugin")
    if not isinstance(plugin_name_value, str) or not plugin_name_value:
        return None
    external_mode_raw = (plugin_info or {}).get("external_provider_mode")
    external_mode = normalize_external_provider_mode(
        external_mode_raw if isinstance(external_mode_raw, str) else None,
    )
    if _has_external_markers(model_data):
        return "external"
    supports_external_providers = coerce_bool_flag(
        (plugin_info or {}).get("supports_external_providers"),
        logger=get_logger(LOGGER_NAME),
        operation="models.manager.capabilities.coerce_bool_flag.supports_external_providers",
        default=False,
        recover_message="Failed to parse boolean flag (non-critical).",
    )
    if (
        supports_external_providers
        and external_mode != ExternalProviderMode.NONE
        and derive_model_category_type(model_data, plugin_info) == "cloud"
    ):
        return "external"
    plugin_types = _parse_plugin_model_types(plugin_info)
    if (
        model_format := str(model_data.get("model_format") or "").strip().lower()
    ) and model_format != "unknown":
        if model_format != "transformers" or not plugin_types or "transformers" in plugin_types:
            return model_format
    return plugin_types[0] if len(plugin_types) == 1 else None
