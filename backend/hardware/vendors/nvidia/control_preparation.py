"""SoAI - Complete NVIDIA native original and target capture [backend/hardware/vendors/nvidia/control_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import ctypes
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_operation_types import GPUClockConversionUnavailableError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.types.json import JSONDict, JSONValue
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import (
    require_int_in_range_strict,
    require_non_negative_int_strict,
    require_positive_int_strict,
)
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.control_recovery_records import (
    create_observed_recovery_member,
    create_prepared_recovery_record,
)
from hardware.vendors.nvidia.internal_protocols import (
    NvmlControlModuleProtocol,
    NvmlErrorValueProtocol,
    NvmlNativeFunctionResolverProtocol,
)
from hardware.vendors.nvidia.nvml_actuator_acquisition import require_nvml_member_actuators
from hardware.vendors.nvidia.nvml_clock_offset_abi import NvmlClockOffsetError
from hardware.vendors.nvidia.nvml_clock_preparation import prepare_nvml_clock_members
from hardware.vendors.nvidia.nvml_physical_binding import acquire_nvml_physical_binding
from hardware.vendors.nvidia.tuning_nvml_controls import read_nvml_fan_constraints
from hardware.vendors.nvidia.tuning_power_limit import read_nvml_power_constraints

if TYPE_CHECKING:
    from hardware.vendors.nvidia.internal_protocols import NvmlDeviceHandle


__all__ = ("prepare_nvml_control_record",)


def prepare_nvml_control_record(
    module: NvmlControlModuleProtocol,
    *,
    target: GPUPhysicalDevice,
    operation_id: str,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
    modern_function_resolver: NvmlNativeFunctionResolverProtocol | None,
    clock_control_types: Mapping[str, str] | None,
) -> GPURecoveryRecord:
    require_canonical_trimmed_json_text(operation_id, error_message="NVML operation ID is invalid.")
    settings, modes = copy.deepcopy(requested_settings), copy.deepcopy(requested_modes)
    if (
        not settings
        or not set(settings).issubset(GPU_DIRECT_SETTING_FIELDS)
        or set(settings) != set(modes)
    ):
        raise ValidationError("NVML preparation requires complete supported user fields and modes.")
    for field, value in settings.items():
        if modes[field] not in ("auto", "manual") or (value == "auto" and modes[field] != "auto"):
            raise ValidationError("NVML requested mode conflicts with the user value.")
        if value != "auto":
            if field == "fan_speed":
                require_non_negative_int_strict(value, error_message="NVML fan request is invalid.")
            else:
                require_positive_int_strict(value, error_message="NVML requested value is invalid.")
    try:
        bound = acquire_nvml_physical_binding(module, target=target)
        handle = bound.handle
        members: list[GPURecoveryMember] = []
        units: JSONDict = {}
        if "power_limit" in settings:
            member = _power_member(module, handle, settings["power_limit"], modes["power_limit"])
            members.append(member)
            if modes["power_limit"] == "auto" and member.requested_value is not None:
                settings["power_limit"] = member.requested_value / 1000
            units["power_limit"] = "W"
        if "fan_speed" in settings:
            members.extend(_fan_members(module, handle, settings["fan_speed"], modes["fan_speed"]))
            units["fan_speed"] = "%"
        try:
            clock_members = prepare_nvml_clock_members(
                module, handle, settings, modes, modern_function_resolver, clock_control_types
            )
        except (module.NVMLError, NvmlClockOffsetError) as exception:
            raise GPUClockConversionUnavailableError(
                "NVML clock observation is unavailable.", cause=exception
            ) from exception
        members.extend(clock_members)
        for member in clock_members:
            units[member.field] = "MHz"
        for member in members:
            require_nvml_member_actuators(
                member, modern_function_resolver, module.NVMLError, goal="requested"
            )
        if any(
            (member.requested_value is not None and member.requested_value != member.original_value)
            or (member.requested_mode is not None and member.requested_mode != member.original_mode)
            for member in members
        ):
            setup_members = _persistence_members(module, handle)
            for member in setup_members:
                require_nvml_member_actuators(
                    member, modern_function_resolver, module.NVMLError, goal="requested"
                )
            if setup_members:
                members = setup_members + members
                (
                    settings["persistence_mode"],
                    modes["persistence_mode"],
                    units["persistence_mode"],
                ) = (1, "manual", "policy")
    except (module.NVMLError, ctypes.ArgumentError, AttributeError) as exception:
        raise StateError(
            "NVML original-state preparation failed before native effects.",
            details={"actuator_invoked": False, "operation_id": operation_id},
            cause=exception,
        ) from exception
    return create_prepared_recovery_record(
        operation_id=operation_id,
        backend="nvml",
        requested_settings=settings,
        requested_modes=modes,
        requested_units=units,
        members=tuple(members),
        target=bound.device,
    )


def _persistence_members(
    module: NvmlControlModuleProtocol, handle: NvmlDeviceHandle
) -> list[GPURecoveryMember]:
    try:
        getter = module.nvmlDeviceGetPersistenceMode
    except AttributeError:
        return []
    if not callable(getter):
        raise ValidationError("NVML persistence facility is malformed.")
    try:
        original = getter(handle)
    except module.NVMLError as exception:
        if (
            isinstance(exception, NvmlErrorValueProtocol)
            and is_strict_int(exception.value)
            and exception.value == 3
        ):
            return []
        raise
    original = require_int_in_range_strict(
        original, minimum=0, maximum=1, error_message="NVML persistence original policy is invalid."
    )
    return [
        create_observed_recovery_member(
            field="persistence_mode",
            member_id="persistence",
            original_value=None,
            original_mode=original,
            requested_value=None,
            requested_mode=1,
            backend="nvml",
            native_unit="policy",
            domain_id=None,
            pstate_id=None,
        )
    ]


def _power_member(
    module: NvmlControlModuleProtocol, handle: NvmlDeviceHandle, value: JSONValue, mode: JSONValue
) -> GPURecoveryMember:
    original = require_positive_int_strict(
        module.nvmlDeviceGetPowerManagementLimit(handle),
        error_message="NVML original power limit is invalid.",
    )
    minimum, maximum = read_nvml_power_constraints(module, handle)
    if mode == "auto":
        requested = require_positive_int_strict(
            module.nvmlDeviceGetPowerManagementDefaultLimit(handle),
            error_message="NVML default power limit is invalid.",
        )
    else:
        requested = (
            require_positive_int_strict(value, error_message="NVML user power limit is invalid.")
            * 1000
        )
    requested = require_int_in_range_strict(
        requested,
        minimum=minimum,
        maximum=maximum,
        error_message="NVML power target is outside actual constraints.",
    )
    if not minimum <= original <= maximum:
        raise ValidationError("NVML original power limit conflicts with actual constraints.")
    return create_observed_recovery_member(
        field="power_limit",
        member_id="power_limit",
        original_value=original,
        original_mode=None,
        requested_value=requested,
        requested_mode=None,
        backend="nvml",
        native_unit="mW",
        domain_id=None,
        pstate_id=None,
    )


def _fan_members(
    module: NvmlControlModuleProtocol, handle: NvmlDeviceHandle, value: JSONValue, mode: JSONValue
) -> list[GPURecoveryMember]:
    count = require_positive_int_strict(
        module.nvmlDeviceGetNumFans(handle), error_message="NVML actual fan roster is unavailable."
    )
    constraints: tuple[int, int] | None = None
    speed = None
    if mode != "auto":
        constraints = read_nvml_fan_constraints(module, handle)
        speed = require_int_in_range_strict(
            value,
            minimum=constraints[0],
            maximum=constraints[1],
            error_message="NVML fan target is outside actual constraints.",
        )
    members: list[GPURecoveryMember] = []
    for fan in range(count):
        policy = require_int_in_range_strict(
            module.nvmlDeviceGetFanControlPolicy_v2(handle, fan),
            minimum=0,
            maximum=1,
            error_message="NVML fan original policy is invalid.",
        )
        original = None
        if policy == 1:
            if constraints is None:
                constraints = read_nvml_fan_constraints(module, handle)
            original = require_int_in_range_strict(
                module.nvmlDeviceGetTargetFanSpeed(handle, fan),
                minimum=constraints[0],
                maximum=constraints[1],
                error_message="NVML original manual fan target is invalid.",
            )
        members.append(
            create_observed_recovery_member(
                field="fan_speed",
                member_id=f"fan:{fan}",
                original_value=original,
                original_mode=policy,
                requested_value=speed,
                requested_mode=0 if mode == "auto" else 1,
                backend="nvml",
                native_unit="%",
                domain_id=None,
                pstate_id=None,
            )
        )
    if (
        require_positive_int_strict(
            module.nvmlDeviceGetNumFans(handle), error_message="NVML repeated fan count is invalid."
        )
        != count
    ):
        raise StateError("NVML fan member roster changed during preparation.")
    return members
