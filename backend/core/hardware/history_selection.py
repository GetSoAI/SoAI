"""SoAI - Hardware history selection validation [backend/core/hardware/history_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import coerce_exact_int_or_none

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "HARDWARE_HISTORY_COMPONENTS",
    "HardwareHistorySelection",
    "normalize_hardware_history_export_selection",
    "parse_hardware_history_gpu_index_value",
    "parse_hardware_history_query_selection",
    "parse_optional_hardware_history_export_selection",
    "parse_required_hardware_history_component",
    "parse_required_hardware_history_selection",
    "resolve_hardware_history_identifier",
)

HARDWARE_HISTORY_COMPONENTS = ("cpu", "gpu", "disk", "network")


@dataclass(frozen=True, slots=True)
class HardwareHistorySelection:
    component: str | None
    gpu_index: int | None
    identifier: str | None


def parse_required_hardware_history_component(
    data: JSONDict,
    *,
    missing_message: str,
    invalid_message: str,
) -> str:
    component_value = data.get("component")
    component = component_value.strip().lower() if isinstance(component_value, str) else ""
    if not component:
        raise ValidationError(missing_message)
    if component not in HARDWARE_HISTORY_COMPONENTS:
        raise ValidationError(invalid_message.replace("{component}", component))
    return component


def parse_hardware_history_gpu_index_value(
    value: JSONValue,
    *,
    missing_message: str | None,
    invalid_message: str,
    negative_message: str | None = None,
) -> int | None:
    if value is None:
        if missing_message is not None:
            raise ValidationError(missing_message)
        return None
    gpu_index = coerce_exact_int_or_none(value)
    if gpu_index is None:
        raise ValidationError(invalid_message)
    if gpu_index < 0:
        raise ValidationError(negative_message or invalid_message)
    return gpu_index


def parse_hardware_history_query_selection(
    *,
    component_value: str | None,
    gpu_index_value: int | None = None,
    gpu_index_raw_value: JSONValue = None,
    identifier_value: str | None = None,
) -> HardwareHistorySelection:
    component = component_value.strip().lower() if isinstance(component_value, str) else ""
    if not component:
        raise ValidationError("Query parameter 'component' is required.")
    if component not in HARDWARE_HISTORY_COMPONENTS:
        raise ValidationError(
            "Query parameter 'component' must be one of: cpu, gpu, disk, network.",
        )
    gpu_index = gpu_index_value
    if gpu_index is None and gpu_index_raw_value is not None and gpu_index_raw_value != "":
        gpu_index = parse_hardware_history_gpu_index_value(
            gpu_index_raw_value,
            missing_message=None,
            invalid_message="Query parameter 'gpu_index' must be an integer.",
            negative_message="Query parameter 'gpu_index' must be greater than or equal to zero.",
        )
    identifier = identifier_value
    if component == "gpu":
        identifier = None
    if component == "gpu" and gpu_index is None:
        raise ValidationError(
            "The 'gpu_index' query parameter is required when component is 'gpu'.",
        )
    return HardwareHistorySelection(
        component=component,
        gpu_index=gpu_index,
        identifier=identifier,
    )


def resolve_hardware_history_identifier(
    data: JSONDict,
    component: str | None,
    *,
    require_device_identifier: bool,
    allow_cpu_identifier: bool = False,
) -> str | None:
    identifier_value = data.get("identifier")
    identifier = identifier_value.strip() if isinstance(identifier_value, str) else ""
    if component == "gpu":
        return None
    if component == "cpu" and allow_cpu_identifier:
        return identifier or None
    if component in {"disk", "network"}:
        if require_device_identifier and not identifier:
            raise ValidationError(f"identifier is required when component is '{component}'")
        return identifier or None
    if identifier:
        raise ValidationError("identifier is only valid when component is 'disk' or 'network'")
    return None


def parse_required_hardware_history_selection(
    data: JSONDict,
    *,
    require_device_identifier: bool,
    allow_cpu_identifier: bool = False,
    reject_gpu_index_without_gpu: bool = True,
    missing_component_message: str,
    invalid_component_message: str,
) -> HardwareHistorySelection:
    component = parse_required_hardware_history_component(
        data,
        missing_message=missing_component_message,
        invalid_message=invalid_component_message,
    )
    gpu_index = None
    if component == "gpu":
        gpu_index = parse_hardware_history_gpu_index_value(
            data.get("gpu_index"),
            missing_message="gpu_index is required when component is 'gpu'",
            invalid_message="gpu_index must be a non-negative integer",
        )
    elif reject_gpu_index_without_gpu and data.get("gpu_index") is not None:
        raise ValidationError("gpu_index is only valid when component is 'gpu'")
    identifier = resolve_hardware_history_identifier(
        data,
        component,
        require_device_identifier=require_device_identifier,
        allow_cpu_identifier=allow_cpu_identifier,
    )
    return HardwareHistorySelection(
        component=component,
        gpu_index=gpu_index,
        identifier=identifier,
    )


def normalize_hardware_history_export_selection(
    *,
    component: str | None,
    identifier: str | None,
    gpu_index: int | None,
) -> HardwareHistorySelection:
    if component is not None and not isinstance(component, str):
        raise ValidationError("component must be a string")
    component_text = component.strip().lower() if isinstance(component, str) else ""
    if component_text and component_text not in HARDWARE_HISTORY_COMPONENTS:
        raise ValidationError("component must be one of: cpu, gpu, disk, network")
    component_value = component_text or None
    if identifier is not None and not isinstance(identifier, str):
        raise ValidationError("identifier must be a string")
    identifier_text = identifier.strip() if isinstance(identifier, str) else ""
    identifier_value = identifier_text or None
    if identifier_value is not None and component_value is None:
        raise ValidationError("identifier requires component to be set")
    if gpu_index is not None and isinstance(gpu_index, bool):
        raise ValidationError("gpu_index must be a non-negative integer")
    if gpu_index is not None and gpu_index < 0:
        raise ValidationError("gpu_index must be a non-negative integer")
    if gpu_index is not None and component_value != "gpu":
        raise ValidationError("gpu_index requires component to be 'gpu'")
    return HardwareHistorySelection(
        component=component_value,
        gpu_index=gpu_index,
        identifier=identifier_value,
    )


def parse_optional_hardware_history_export_selection(data: JSONDict) -> HardwareHistorySelection:
    component_value = data.get("component")
    if component_value is not None and not isinstance(component_value, str):
        raise ValidationError("component must be a string")
    component = component_value if isinstance(component_value, str) else None
    identifier_value = data.get("identifier")
    if identifier_value is not None and not isinstance(identifier_value, str):
        raise ValidationError("identifier must be a string")
    identifier = identifier_value if isinstance(identifier_value, str) else None
    gpu_index = parse_hardware_history_gpu_index_value(
        data.get("gpu_index"),
        missing_message=None,
        invalid_message="gpu_index must be a non-negative integer",
    )
    return normalize_hardware_history_export_selection(
        component=component,
        identifier=identifier,
        gpu_index=gpu_index,
    )
