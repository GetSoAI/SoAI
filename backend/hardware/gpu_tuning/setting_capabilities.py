"""SoAI - GPU tuning setting capability descriptors [backend/hardware/gpu_tuning/setting_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_settings_contract import (
    GPU_SETTING_CORE_CLOCK_FIELD,
    GPU_SETTING_FAN_SPEED_FIELD,
    GPU_SETTING_MEM_CLOCK_FIELD,
    GPU_SETTING_POWER_LIMIT_FIELD,
)
from core.logging.trace import get_logger
from core.validation.booleans import parse_bool
from core.validation.numbers import coerce_int_from_json

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "GpuSettingDescriptor",
    "capability_supported",
    "get_capability_entry",
    "gpu_setting_descriptors",
    "sanitize_ranged_setting",
    "setting_descriptor_for_key",
)

LOGGER_NAME = "SoAI.hardware.gpu_tuning.setting_capabilities"
OPERATION_SUPPORTED_FLAG = "hardware.gpu_tuning.setting_capabilities.supported_flag"


@dataclass(frozen=True, slots=True)
class GpuSettingDescriptor:
    request_key: str
    caps_key: str
    label: str
    unit: str


_GPU_SETTING_DESCRIPTOR_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    (GPU_SETTING_POWER_LIMIT_FIELD, "power_limit_watts", "Power limit", "W"),
    (GPU_SETTING_FAN_SPEED_FIELD, "fan_speed_percent", "Fan speed", "%"),
    (GPU_SETTING_CORE_CLOCK_FIELD, "core_clock_mhz", "Core clock", "MHz"),
    (GPU_SETTING_MEM_CLOCK_FIELD, "mem_clock_mhz", "Memory clock", "MHz"),
)


def gpu_setting_descriptors() -> tuple[GpuSettingDescriptor, ...]:
    return tuple(
        GpuSettingDescriptor(
            request_key=request_key,
            caps_key=caps_key,
            label=label,
            unit=unit,
        )
        for request_key, caps_key, label, unit in _GPU_SETTING_DESCRIPTOR_ITEMS
    )


def setting_descriptor_for_key(key: str) -> GpuSettingDescriptor | None:
    for request_key, caps_key, label, unit in _GPU_SETTING_DESCRIPTOR_ITEMS:
        if request_key == key:
            return GpuSettingDescriptor(
                request_key=request_key,
                caps_key=caps_key,
                label=label,
                unit=unit,
            )
    return None


def capability_supported(
    value: JSONValue,
    *,
    logger: LoggerProtocol | None = None,
    operation: str = OPERATION_SUPPORTED_FLAG,
    recover_message: str = "Failed to parse supported flag (non-critical).",
) -> bool:
    resolved_logger = logger if logger is not None else get_logger(LOGGER_NAME)
    try:
        return bool(parse_bool(value, default=False))
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            resolved_logger,
            exception,
            message=recover_message,
            operation=operation,
            level="debug",
        )
        return False


def get_capability_entry(
    capabilities: Mapping[str, JSONValue],
    descriptor: GpuSettingDescriptor,
    *,
    logger: LoggerProtocol | None = None,
    operation: str = OPERATION_SUPPORTED_FLAG,
    recover_message: str = "Failed to parse supported flag (non-critical).",
) -> JSONDict:
    candidate = capabilities.get(descriptor.caps_key)
    if not isinstance(candidate, dict) or (
        not capability_supported(
            candidate.get("supported"),
            logger=logger,
            operation=operation,
            recover_message=recover_message,
        )
    ):
        raise ValidationError(f"{descriptor.label} adjustments are not supported for this device.")
    backend = candidate.get("control_backend")
    if not isinstance(backend, str) or not backend.strip():
        raise ValidationError(f"{descriptor.label} has no supported control backend.")
    return candidate


def sanitize_ranged_setting(
    descriptor: GpuSettingDescriptor,
    value: JSONValue,
    caps: JSONDict,
    *,
    enforce_range: bool = True,
) -> str | int:
    if isinstance(value, str) and value.lower() == "auto":
        return "auto"
    value_int = coerce_int_from_json(
        value,
        default=None,
        parse_float_strings=True,
        round_float_strings=True,
    )
    if value_int is None:
        raise ValidationError(f"{descriptor.label} must be an integer or 'auto'.")
    if not enforce_range:
        return value_int
    min_limit = coerce_int_from_json(
        caps.get("min"),
        default=None,
        parse_float_strings=True,
        round_float_strings=True,
    )
    if min_limit is not None and value_int < min_limit:
        raise ValidationError(f"{descriptor.label} must be at least {min_limit}{descriptor.unit}.")
    max_limit = coerce_int_from_json(
        caps.get("max"),
        default=None,
        parse_float_strings=True,
        round_float_strings=True,
    )
    if max_limit is not None and value_int > max_limit:
        raise ValidationError(f"{descriptor.label} must be at most {max_limit}{descriptor.unit}.")
    allowed_values = _allowed_int_values(caps)
    if allowed_values and value_int not in allowed_values:
        raise ValidationError(
            _allowed_values_error_message(
                label=descriptor.label,
                unit=descriptor.unit,
                values=allowed_values,
            ),
        )
    return value_int


def _allowed_int_values(caps: JSONDict) -> tuple[int, ...]:
    value = caps.get("allowed_values")
    if not isinstance(value, list):
        return ()
    values: list[int] = []
    for item in value:
        parsed = coerce_int_from_json(
            item,
            default=None,
            parse_float_strings=True,
            round_float_strings=True,
        )
        if parsed is not None and parsed not in values:
            values.append(parsed)
    values.sort()
    return tuple(values)


def _allowed_values_error_message(
    *,
    label: str,
    unit: str,
    values: tuple[int, ...],
) -> str:
    if len(values) <= 20:
        rendered = ", ".join(f"{value}{unit}" for value in values)
        return f"{label} must be one of: {rendered}."
    return (
        f"{label} must match one of {len(values)} supported values "
        f"from {values[0]}{unit} to {values[-1]}{unit}."
    )
