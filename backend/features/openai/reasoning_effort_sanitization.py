"""SoAI - OpenAI reasoning effort request sanitization [backend/features/openai/reasoning_effort_sanitization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.provider_backing import is_provider_backed_model
from core.models.reference_resolution import (
    load_model_info_records,
    resolve_model_reference,
)
from core.types.json_value import copy_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.types.json import JSONDict, JSONValue

__all__ = ("sanitize_reasoning_effort_for_model",)

_SUPPORTED_REASONING_LEVELS_KEY = "supported_reasoning_levels"


def _normalize_effort(value: JSONValue | None) -> str | None:
    if not isinstance(value, str):
        return None
    return coerce_optional_trimmed_str(value.lower())


def _read_dict(value: JSONValue | None) -> JSONDict | None:
    return value if isinstance(value, dict) else None


def _read_supported_reasoning_levels_from_value(
    value: JSONValue | None,
) -> frozenset[str] | None:
    if not isinstance(value, list):
        return None
    efforts: list[str] = []
    for entry in value:
        effort = _normalize_effort(entry)
        if effort is None and isinstance(entry, dict):
            effort = _normalize_effort(entry.get("effort"))
        if effort is not None:
            efforts.append(effort)
    return frozenset(efforts) if efforts else None


def _read_supported_reasoning_levels_from_capabilities(
    value: JSONValue | None,
) -> frozenset[str] | None:
    capabilities = _read_dict(value)
    if capabilities is None:
        return None
    return _read_supported_reasoning_levels_from_value(
        capabilities.get(_SUPPORTED_REASONING_LEVELS_KEY),
    )


def _read_supported_reasoning_levels(model_info: JSONDict) -> frozenset[str] | None:
    direct = _read_supported_reasoning_levels_from_value(
        model_info.get(_SUPPORTED_REASONING_LEVELS_KEY),
    )
    if direct is not None:
        return direct
    metadata = _read_dict(model_info.get("metadata"))
    if metadata is not None:
        metadata_direct = _read_supported_reasoning_levels_from_value(
            metadata.get(_SUPPORTED_REASONING_LEVELS_KEY),
        )
        if metadata_direct is not None:
            return metadata_direct
    model_metadata = _read_dict(model_info.get("model_metadata"))
    nested_metadata = _read_dict(model_metadata.get("metadata")) if model_metadata else None
    if nested_metadata is not None:
        nested_direct = _read_supported_reasoning_levels_from_value(
            nested_metadata.get(_SUPPORTED_REASONING_LEVELS_KEY),
        )
        if nested_direct is not None:
            return nested_direct
    for container in (model_info, metadata, nested_metadata):
        if container is None:
            continue
        capability_levels = _read_supported_reasoning_levels_from_capabilities(
            container.get("openai_capabilities"),
        )
        if capability_levels is not None:
            return capability_levels
    return None


def _should_drop_reasoning_effort(
    *,
    requested_effort: str,
    support_sets: tuple[frozenset[str], ...],
) -> bool:
    if requested_effort != "none":
        return False
    return any(requested_effort not in support_set for support_set in support_sets)


def _should_drop_unknown_provider_none(
    *,
    requested_effort: str,
    records: tuple[JSONDict, ...],
    support_sets: tuple[frozenset[str], ...],
) -> bool:
    if requested_effort != "none" or support_sets:
        return False
    if not records:
        return False
    return all(is_provider_backed_model(record) for record in records)


def _unsupported_reasoning_effort_message(
    *,
    requested_effort: str,
    support_sets: tuple[frozenset[str], ...],
) -> str:
    shared_supported_values = set(support_sets[0])
    for support_set in support_sets[1:]:
        shared_supported_values.intersection_update(support_set)
    supported_values = sorted(shared_supported_values)
    if not supported_values:
        all_supported_values: set[str] = set()
        for support_set in support_sets:
            all_supported_values.update(support_set)
        supported_values = sorted(all_supported_values)
    supported_text = ", ".join(supported_values)
    return (
        f"reasoning_effort '{requested_effort}' is not supported by the selected model. "
        f"Supported values: {supported_text}."
    )


async def sanitize_reasoning_effort_for_model(
    *,
    payload: JSONDict,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ),
) -> JSONDict:
    requested_effort = _normalize_effort(payload.get("reasoning_effort"))
    model_name = coerce_optional_trimmed_str(payload.get("model"))
    if requested_effort is None or model_name is None:
        return payload
    reference = await resolve_model_reference(
        model_name=model_name,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if reference is None:
        return payload
    records = await load_model_info_records(
        reference=reference,
        model_information_service=model_information_service,
    )
    if records is None:
        return payload
    support_sets = tuple(
        support_set
        for record in records
        if (support_set := _read_supported_reasoning_levels(record)) is not None
    )
    if _should_drop_unknown_provider_none(
        requested_effort=requested_effort,
        records=records,
        support_sets=support_sets,
    ):
        sanitized = copy_json_dict(payload)
        sanitized.pop("reasoning_effort", None)
        return sanitized
    if not support_sets:
        return payload
    if _should_drop_reasoning_effort(
        requested_effort=requested_effort,
        support_sets=support_sets,
    ):
        sanitized = copy_json_dict(payload)
        sanitized.pop("reasoning_effort", None)
        return sanitized
    if any(requested_effort not in support_set for support_set in support_sets):
        raise ValidationError(
            _unsupported_reasoning_effort_message(
                requested_effort=requested_effort,
                support_sets=support_sets,
            ),
        )
    if payload.get("reasoning_effort") == requested_effort:
        return payload
    sanitized = copy_json_dict(payload)
    sanitized["reasoning_effort"] = requested_effort
    return sanitized
