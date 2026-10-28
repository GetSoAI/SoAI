"""SoAI - Complete NvAPI originals and frozen native targets [backend/hardware/vendors/nvidia/nvapi_control_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import ctypes
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.types.json import JSONDict
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
from hardware.vendors.nvidia.nvapi_clock_controls import (
    query_nvapi_clock_controls,
    read_nvapi_clock_conversion,
    read_nvapi_clock_member,
)
from hardware.vendors.nvidia.nvapi_control_observations import (
    acquire_nvapi_control_binding,
    nvapi_clock_readiness_recheck,
    nvapi_member_is_safe,
    prepare_nvapi_member_invocation,
)
from hardware.vendors.nvidia.nvapi_fan_controls import (
    query_nvapi_fan_controls,
    read_nvapi_fan_topology,
)
from hardware.vendors.nvidia.nvapi_function_acquisition import resolve_nvapi_function
from hardware.vendors.nvidia.nvapi_power_controls import (
    query_nvapi_power_controls,
    read_nvapi_power_conversion,
    read_nvapi_power_member,
)

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import GPUPreparedControl
    from core.system.protocols import CommandExecutorProtocol
    from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution
    from hardware.vendors.nvidia.internal_protocols import NvmlControlModuleProtocol


__all__ = (
    "prepare_nvapi_control_record",
    "require_nvapi_member_actuator",
    "preflight_nvapi_control_record",
)


def prepare_nvapi_control_record(
    executor: CommandExecutorProtocol,
    *,
    target: GPUPhysicalDevice,
    executable: GpuExecutableResolution,
    query_interface: Callable[[int], int | None],
    nvml_module: NvmlControlModuleProtocol | None,
    operation_id: str,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
) -> GPURecoveryRecord:
    require_canonical_trimmed_json_text(
        operation_id, error_message="NvAPI operation ID is invalid."
    )
    settings, modes = copy.deepcopy(requested_settings), copy.deepcopy(requested_modes)
    if (
        not settings
        or not set(settings).issubset(GPU_DIRECT_SETTING_FIELDS)
        or set(settings) != set(modes)
    ):
        raise ValidationError(
            "NvAPI preparation requires complete supported user fields and modes."
        )
    for field, value in settings.items():
        if modes[field] not in ("auto", "manual"):
            raise ValidationError("NvAPI user modes are invalid.")
        if value == "auto":
            if modes[field] != "auto":
                raise ValidationError("NvAPI user automatic value conflicts with manual mode.")
        elif field == "fan_speed":
            require_non_negative_int_strict(value, error_message="NvAPI fan input is invalid.")
        else:
            require_positive_int_strict(value, error_message="NvAPI numeric input is invalid.")
    bound = acquire_nvapi_control_binding(
        executor, target=target, executable=executable, query_interface=query_interface
    )
    members: list[GPURecoveryMember] = []
    units: JSONDict = {}
    if "power_limit" in settings:
        power_info, power_status = query_nvapi_power_controls(
            bound.handle, query_interface=query_interface
        )
        power = read_nvapi_power_member(power_info, power_status)
        if modes["power_limit"] == "auto":
            power_target = power.default
            settings["power_limit"] = "auto"
        else:
            watts = require_positive_int_strict(
                settings["power_limit"], error_message="NvAPI user watts are invalid."
            )
            if power.default != 100000:
                raise StateError(
                    "NvAPI absolute-watt reference for this native default is unproved."
                )
            default_mw = read_nvapi_power_conversion(nvml_module, bound.device)
            numerator = watts * 100_000_000
            if numerator % default_mw != 0:
                raise StateError(
                    "NvAPI requested watts cannot be represented exactly in native milli-percent."
                )
            power_target = numerator // default_mw
        power_target = require_int_in_range_strict(
            power_target,
            minimum=power.minimum,
            maximum=power.maximum,
            error_message="NvAPI power target is outside actual constraints.",
        )
        members.append(
            create_observed_recovery_member(
                field="power_limit",
                member_id="policy",
                original_value=power.value,
                original_mode=None,
                requested_value=power_target,
                requested_mode=None,
                backend="nvapi",
                native_unit="milli-percent",
                domain_id=None,
                pstate_id=power.pstate,
            )
        )
        units["power_limit"] = "W"
    if "fan_speed" in settings:
        fan_control, fan_status = query_nvapi_fan_controls(
            bound.handle, query_interface=query_interface
        )
        for fan in read_nvapi_fan_topology(fan_control, fan_status):
            fan_mode = 0 if modes["fan_speed"] == "auto" else 1
            fan_target = (
                None
                if fan_mode == 0
                else require_int_in_range_strict(
                    settings["fan_speed"],
                    minimum=fan.minimum,
                    maximum=fan.maximum,
                    error_message="NvAPI fan target is outside actual constraints.",
                )
            )
            members.append(
                create_observed_recovery_member(
                    field="fan_speed",
                    member_id=f"cooler:{fan.cooler_id}",
                    original_value=fan.value,
                    original_mode=fan.mode,
                    requested_value=fan_target,
                    requested_mode=fan_mode,
                    backend="nvapi",
                    native_unit="%",
                    domain_id=None,
                    pstate_id=None,
                )
            )
        if modes["fan_speed"] == "auto":
            settings["fan_speed"] = "auto"
        units["fan_speed"] = "%"
    if "core_clock" in settings or "mem_clock" in settings:
        clock_info = query_nvapi_clock_controls(
            bound.handle,
            query_interface=query_interface,
            readiness_recheck=nvapi_clock_readiness_recheck(
                executor, bound, executable=executable, query_interface=query_interface
            ),
        )
        for field, domain in (("core_clock", 0), ("mem_clock", 4)):
            if field not in settings:
                continue
            clock = read_nvapi_clock_member(clock_info, pstate=0, domain=domain)
            if modes[field] == "auto":
                clock_target = 0
                settings[field] = "auto"
            else:
                user_mhz = require_positive_int_strict(
                    settings[field], error_message="NvAPI user clock is invalid."
                )
                baseline = read_nvapi_clock_conversion(nvml_module, bound.device, domain)
                clock_target = (user_mhz - baseline) * 1000
            clock_target = require_int_in_range_strict(
                clock_target,
                minimum=clock.minimum,
                maximum=clock.maximum,
                error_message="NvAPI clock target is outside actual delta constraints.",
            )
            members.append(
                create_observed_recovery_member(
                    field=field,
                    member_id="pstate_delta",
                    original_value=clock.value,
                    original_mode=None,
                    requested_value=clock_target,
                    requested_mode=None,
                    backend="nvapi",
                    native_unit="kHz",
                    domain_id=domain,
                    pstate_id=0,
                )
            )
            units[field] = "MHz"
    for member in members:
        require_nvapi_member_actuator(member, query_interface=query_interface)
    return create_prepared_recovery_record(
        operation_id=operation_id,
        backend="nvapi",
        requested_settings=settings,
        requested_modes=modes,
        requested_units=units,
        members=tuple(members),
        target=bound.device,
    )


def require_nvapi_member_actuator(
    member: GPURecoveryMember, *, query_interface: Callable[[int], int | None]
) -> None:
    if (member.original_value, member.original_mode) == (
        member.requested_value,
        member.requested_mode,
    ):
        return
    if member.field == "fan_speed":
        fan_setter = resolve_nvapi_function(
            "NvAPI_GPU_ClientFanCoolersSetControl", query_interface=query_interface
        )
        if fan_setter is None:
            raise StateError("NvAPI selected fan actuator is unavailable.")
    elif member.field in ("core_clock", "mem_clock"):
        clock_setter = resolve_nvapi_function(
            "NvAPI_GPU_SetPstates20", query_interface=query_interface
        )
        if clock_setter is None:
            raise StateError("NvAPI selected clock actuator is unavailable.")
    elif member.field == "power_limit":
        power_setter = resolve_nvapi_function(
            "NvAPI_GPU_ClientPowerPoliciesSetStatus", query_interface=query_interface
        )
        if power_setter is None:
            raise StateError("NvAPI selected power actuator is unavailable.")
    else:
        raise ValidationError("NvAPI member has no declared native actuator.")


def preflight_nvapi_control_record(
    executor: CommandExecutorProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    *,
    executable: GpuExecutableResolution,
    query_interface: Callable[[int], int | None],
    nvml_module: NvmlControlModuleProtocol | None,
    goal: Literal["requested", "original"],
) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
    native_failures: tuple[type[Exception], ...] = (
        ctypes.ArgumentError,
        *HANDLED_RUNTIME_EXCEPTIONS,
    )
    try:
        for member in record.members:
            if member.backend != "nvapi":
                continue
            _, observed, _ = prepare_nvapi_member_invocation(
                executor=executor,
                record=record,
                target=prepared.target,
                member=member,
                executable=executable,
                query_interface=query_interface,
                nvml_module=nvml_module,
                goal=goal,
                purpose="stage",
            )
            if not nvapi_member_is_safe(member, observed, goal):
                failures = (
                    () if observed.conversion_failure is None else (observed.conversion_failure,)
                )
                return (
                    GPUControlPreflightRejection(
                        "native_state_changed", "NvAPI original or conversion authority changed."
                    ),
                    failures,
                )
    except native_failures as exception:
        return GPUControlPreflightRejection(
            "native_query_failed", "NvAPI native preflight failed."
        ), (exception,)
    return None, ()
