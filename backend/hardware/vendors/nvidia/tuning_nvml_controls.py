"""SoAI - NVML fan and clock tuning routines [backend/hardware/vendors/nvidia/tuning_nvml_controls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.imports.availability import module_available
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_int_in_range_strict, require_positive_int_strict
from hardware.gpu_tuning.service_parsing import coerce_auto_or_gpu_setting_int
from hardware.result_messages import append_log_message
from hardware.vendors.nvidia.internal_protocols import (
    NvmlControlModuleProtocol,
    NvmlControlObservation,
    NvmlFanQueryProtocol,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONValue
    from hardware.vendors.nvidia.internal_protocols import NvmlDeviceHandle


__all__ = ("apply_nvml_fan_setting",)

pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def apply_nvml_fan_setting(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    messages: list[str],
    errors: list[str],
    handle: NvmlDeviceHandle,
    fan_speed: JSONValue,
) -> bool:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        errors.append("Failed to set fan speed: pynvml is unavailable.")
        return False
    try:
        try:
            device_set_default_fan_speed: Callable[..., None] | None = (
                pynvml_module.nvmlDeviceSetDefaultFanSpeed_v2
            )
        except AttributeError:
            device_set_default_fan_speed = None
        try:
            device_set_fan_speed: Callable[..., None] | None = (
                pynvml_module.nvmlDeviceSetFanSpeed_v2
            )
        except AttributeError:
            device_set_fan_speed = None
        if not callable(device_set_default_fan_speed) or not callable(device_set_fan_speed):
            raise StateError("Fan control unavailable.")
        is_auto, speed_value = coerce_auto_or_gpu_setting_int(fan_speed)
        if is_auto:
            _set_default_fan_speed(device_set_default_fan_speed, handle)
            message = "Fan control set to AUTO."
        else:
            if speed_value is None:
                raise StateError("Fan speed must be numeric.")
            device_set_fan_speed(handle, 0, speed_value)
            message = f"Manual fan speed set to {speed_value}%."
        append_log_message(messages, logger, vendor_id, message)
        return True
    except pynvml_module.NVMLError as exception:
        errors.append(f"Failed to set fan speed: {exception}")
    except (ValueError, RuntimeError) as exception:
        errors.append(f"Failed to set fan speed: {exception}")
    return False


def _set_default_fan_speed(
    setter: Callable[..., None],
    handle: NvmlDeviceHandle,
) -> None:
    try:
        setter(handle, 0)
    except TypeError as first_exception:
        try:
            setter(handle)
        except TypeError as second_exception:
            raise first_exception from second_exception


def nvml_fan_member_index(member: GPURecoveryMember) -> int:
    suffix = member.member_id.removeprefix("fan:")
    if not suffix.isascii() or not suffix.isdigit():
        raise ValidationError("NVML fan member identifier is invalid.")
    fan = int(suffix)
    if member.member_id != f"fan:{fan}" or (
        member.domain_id,
        member.pstate_id,
        member.native_unit,
    ) != (None, None, "%"):
        raise ValidationError("NVML fan member routing is invalid.")
    return fan


def read_nvml_fan_member(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
) -> NvmlControlObservation:
    fan = require_nvml_fan_relation(module, handle, member, record)
    if (
        not is_strict_int(member.requested_mode)
        or member.requested_mode not in (0, 1)
        or record.requested_units[member.field] != "%"
    ):
        raise ValidationError("NVML frozen fan policy is invalid.")
    if (record.requested_modes[member.field] == "auto") != (member.requested_mode == 0):
        raise ValidationError("NVML requested fan policy conflicts with user mode.")
    if member.requested_mode == 0:
        if member.requested_value is not None:
            raise ValidationError("NVML automatic fan target cannot invent a speed.")
    elif (
        require_int_in_range_strict(
            member.requested_value,
            minimum=0,
            maximum=100,
            error_message="NVML frozen fan target is invalid.",
        )
        != record.requested_settings[member.field]
    ):
        raise ValidationError("NVML frozen fan target conflicts with user percent.")
    policy = require_int_in_range_strict(
        module.nvmlDeviceGetFanControlPolicy_v2(handle, fan),
        minimum=0,
        maximum=1,
        error_message="NVML actual fan policy is invalid.",
    )
    value = (
        None
        if policy == 0
        else require_int_in_range_strict(
            module.nvmlDeviceGetTargetFanSpeed(handle, fan),
            minimum=0,
            maximum=100,
            error_message="NVML actual manual fan target is invalid.",
        )
    )
    original_policy = require_int_in_range_strict(
        member.original_mode,
        minimum=0,
        maximum=1,
        error_message="NVML frozen original fan policy is invalid.",
    )
    original_restorable = original_policy == 0
    meaning = True
    failure = None
    if member.requested_mode == 1 or original_policy == 1:
        try:
            minimum, maximum = read_nvml_fan_constraints(module, handle)
        except module.NVMLError as exception:
            meaning = False
            original_restorable = False
            failure = StateError(
                "NVML fan constraint authority could not be revalidated.", cause=exception
            )
        else:
            if member.requested_mode == 1:
                requested = require_int_in_range_strict(
                    member.requested_value,
                    minimum=0,
                    maximum=100,
                    error_message="NVML frozen manual fan target is invalid.",
                )
                meaning = minimum <= requested <= maximum
            if original_policy == 1:
                original = require_int_in_range_strict(
                    member.original_value,
                    minimum=0,
                    maximum=100,
                    error_message="NVML frozen original manual fan target is invalid.",
                )
                original_restorable = minimum <= original <= maximum
    return NvmlControlObservation(value, policy, meaning, original_restorable, failure)


def invoke_nvml_fan_member(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    *,
    native_value: int | float | None,
    native_mode: int | str | None,
) -> None:
    fan = nvml_fan_member_index(member)
    if native_mode == 0:
        status = module.nvmlDeviceSetDefaultFanSpeed_v2(handle, fan)
    elif native_mode == 1:
        speed = require_int_in_range_strict(
            native_value,
            minimum=0,
            maximum=100,
            error_message="NVML frozen manual fan target is invalid.",
        )
        status = module.nvmlDeviceSetFanSpeed_v2(handle, fan, speed)
    else:
        raise ValidationError("NVML frozen fan policy is invalid.")
    if not is_strict_int(status) or status != 0:
        raise StateError("NVML fan setter returned an invalid acknowledgement.")


def read_nvml_fan_constraints(
    module: NvmlFanQueryProtocol, handle: NvmlDeviceHandle
) -> tuple[int, int]:
    limits = module.nvmlDeviceGetMinMaxFanSpeed(handle)
    if (
        not isinstance(limits, list)
        or len(limits) != 2
        or any(not is_strict_int(value) for value in limits)
        or not 0 <= limits[0] <= limits[1] <= 100
    ):
        raise ValidationError("NVML actual fan percentage constraints are invalid.")
    return limits[0], limits[1]


def require_nvml_fan_relation(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
) -> int:
    fan = nvml_fan_member_index(member)
    count = require_positive_int_strict(
        module.nvmlDeviceGetNumFans(handle), error_message="NVML actual fan roster is invalid."
    )
    expected = {
        nvml_fan_member_index(item)
        for item in record.members
        if item.field == "fan_speed" and item.backend == "nvml"
    }
    if expected != set(range(count)) or fan >= count:
        raise StateError("NVML actual fan member relation changed.")
    return fan


def read_nvml_original_fan_member(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
) -> NvmlControlObservation:
    fan = require_nvml_fan_relation(module, handle, member, record)
    original_policy = require_int_in_range_strict(
        member.original_mode,
        minimum=0,
        maximum=1,
        error_message="NVML original fan policy is invalid.",
    )
    if original_policy == 0 and member.original_value is not None:
        raise ValidationError("NVML original automatic fan policy cannot invent a speed.")
    policy = require_int_in_range_strict(
        module.nvmlDeviceGetFanControlPolicy_v2(handle, fan),
        minimum=0,
        maximum=1,
        error_message="NVML actual fan policy is invalid.",
    )
    value = (
        None
        if policy == 0
        else require_int_in_range_strict(
            module.nvmlDeviceGetTargetFanSpeed(handle, fan),
            minimum=0,
            maximum=100,
            error_message="NVML actual manual fan target is invalid.",
        )
    )
    restorable = True
    if original_policy == 1:
        original = require_int_in_range_strict(
            member.original_value,
            minimum=0,
            maximum=100,
            error_message="NVML original manual fan target is invalid.",
        )
        minimum, maximum = read_nvml_fan_constraints(module, handle)
        restorable = minimum <= original <= maximum
    return NvmlControlObservation(value, policy, restorable, restorable, None)
