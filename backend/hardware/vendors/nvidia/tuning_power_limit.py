"""SoAI - NVIDIA NVML power-limit application [backend/hardware/vendors/nvidia/tuning_power_limit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.logging.trace import TraceLogger
from core.types.json import JSONValue
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_positive_int_strict
from hardware.gpu_tuning.service_parsing import coerce_auto_or_gpu_setting_int
from hardware.vendors.nvidia.internal_protocols import (
    NvmlControlModuleProtocol,
    NvmlControlObservation,
)

if TYPE_CHECKING:
    from hardware.vendors.nvidia.internal_protocols import NvmlDeviceHandle


__all__ = ("apply_nvml_power_limit_setting",)


def apply_nvml_power_limit_setting(
    logger: TraceLogger | None,
    *,
    vendor_id: int,
    messages: list[str],
    handle: ctypes.c_void_p,
    power_limit: JSONValue,
    power_default_limit_function: Callable[[ctypes.c_void_p], int] | None,
    power_set_limit_function: Callable[[ctypes.c_void_p, int], None] | None,
    power_current_limit_function: Callable[[ctypes.c_void_p], int] | None,
) -> None:
    if (
        not callable(power_default_limit_function)
        or not callable(power_set_limit_function)
        or not callable(power_current_limit_function)
    ):
        raise StateError("Power limit control unavailable.")
    is_auto, limit_value = coerce_auto_or_gpu_setting_int(power_limit)
    if is_auto:
        limit = power_default_limit_function(handle)
    else:
        if limit_value is None:
            raise StateError("Power limit must be numeric.")
        limit = limit_value * 1000
    limit = require_positive_int_strict(
        limit, error_message="NVML requested power limit is invalid."
    )
    power_set_limit_function(handle, limit)
    observed = require_positive_int_strict(
        power_current_limit_function(handle),
        error_message="NVML configured power readback is invalid.",
    )
    if observed != limit:
        raise StateError(
            "NVML configured power readback does not match the requested limit.",
            details={"actuator_invoked": True, "requested_mW": limit, "observed_mW": observed},
        )
    message = (
        f"Power limit reset to default ({limit // 1000}W)."
        if is_auto
        else f"Power limit set to {limit // 1000}W."
    )
    messages.append(message)
    if logger:
        logger.info("NVIDIA GPU %s %s", vendor_id, message)


def read_nvml_power_member(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
) -> NvmlControlObservation:
    if (
        (member.member_id, member.domain_id, member.pstate_id, member.native_unit)
        != ("power_limit", None, None, "mW")
        or member.requested_mode is not None
        or member.original_mode is not None
    ):
        raise ValidationError("NVML power member routing is invalid.")
    requested = require_positive_int_strict(
        member.requested_value, error_message="NVML frozen power target is invalid."
    )
    if (
        record.requested_units[member.field] != "W"
        or record.requested_settings[member.field] != requested / 1000
    ):
        raise ValidationError("NVML frozen user watts conflict with native milliwatts.")
    value = require_positive_int_strict(
        module.nvmlDeviceGetPowerManagementLimit(handle),
        error_message="NVML actual power readback is invalid.",
    )
    failure = None
    original_restorable = False
    try:
        minimum, maximum = read_nvml_power_constraints(module, handle)
    except module.NVMLError as exception:
        meaning = False
        failure = StateError(
            "NVML power constraint authority could not be revalidated.", cause=exception
        )
    else:
        meaning = minimum <= requested <= maximum
        original_restorable = (
            is_strict_int(member.original_value) and minimum <= member.original_value <= maximum
        )
    if record.requested_modes[member.field] == "auto":
        try:
            actual_default = require_positive_int_strict(
                module.nvmlDeviceGetPowerManagementDefaultLimit(handle),
                error_message="NVML actual default power is invalid.",
            )
        except module.NVMLError as exception:
            meaning = False
            failure = StateError(
                "NVML automatic power authority could not be revalidated.", cause=exception
            )
        else:
            meaning = meaning and actual_default == requested
    return NvmlControlObservation(value, None, meaning, original_restorable, failure)


def invoke_nvml_power_member(
    module: NvmlControlModuleProtocol, handle: NvmlDeviceHandle, *, native_value: int | float | None
) -> None:
    requested = require_positive_int_strict(
        native_value, error_message="NVML frozen power target is invalid."
    )
    module.nvmlDeviceSetPowerManagementLimit(handle, requested)


def read_nvml_original_power_member(
    module: NvmlControlModuleProtocol, handle: NvmlDeviceHandle, member: GPURecoveryMember
) -> NvmlControlObservation:
    if (member.member_id, member.domain_id, member.pstate_id, member.native_unit) != (
        "power_limit",
        None,
        None,
        "mW",
    ) or member.original_mode is not None:
        raise ValidationError("NVML original power member routing is invalid.")
    value = require_positive_int_strict(
        module.nvmlDeviceGetPowerManagementLimit(handle),
        error_message="NVML actual original power readback is invalid.",
    )
    minimum, maximum = read_nvml_power_constraints(module, handle)
    restorable = (
        is_strict_int(member.original_value) and minimum <= member.original_value <= maximum
    )
    return NvmlControlObservation(value, None, restorable, restorable, None)


def read_nvml_power_constraints(
    module: NvmlControlModuleProtocol, handle: NvmlDeviceHandle
) -> tuple[int, int]:
    limits = module.nvmlDeviceGetPowerManagementLimitConstraints(handle)
    if (
        not isinstance(limits, list)
        or len(limits) != 2
        or any(not is_strict_int(value) for value in limits)
        or not 0 <= limits[0] <= limits[1]
    ):
        raise ValidationError("NVML actual milliwatt power constraints are invalid.")
    return limits[0], limits[1]
