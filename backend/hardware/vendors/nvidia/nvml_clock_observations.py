"""SoAI - NVML clock baseline, range and frozen member observations [backend/hardware/vendors/nvidia/nvml_clock_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_operation_types import GPUClockConversionUnavailableError
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_int_in_range_strict, require_positive_int_strict
from hardware.vendors.nvidia.internal_protocols import NvmlControlObservation
from hardware.vendors.nvidia.nvml_clock_offset_abi import NvmlClockOffsetError, read_clock_offset

if TYPE_CHECKING:
    from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
    from hardware.vendors.nvidia.internal_protocols import (
        NvmlControlModuleProtocol,
        NvmlDeviceHandle,
        NvmlNativeFunctionResolverProtocol,
    )

__all__ = (
    "NvmlClockFacilityUnavailable",
    "read_coherent_nvml_clock_baseline",
    "read_nvml_clock_baseline",
    "read_nvml_clock_relation",
    "read_nvml_clock_member",
    "read_nvml_original_clock_member",
)


class NvmlClockFacilityUnavailable(GPUClockConversionUnavailableError):
    __slots__ = ()


def read_nvml_clock_baseline(
    module: NvmlControlModuleProtocol, handle: NvmlDeviceHandle, domain: int
) -> int:
    if domain not in (0, 2) or not is_strict_int(domain):
        raise ValidationError("NVML P0 clock domain is invalid.")
    try:
        getter = module.nvmlDeviceGetMinMaxClockOfPState
    except AttributeError as exception:
        raise NvmlClockFacilityUnavailable("NVML P0 clock facility is absent.") from exception
    if not callable(getter):
        raise ValidationError("NVML P0 clock facility is malformed.")
    minimum, baseline = _clock_range(getter(handle, domain, 0))
    if minimum <= 0:
        raise ValidationError("NVML actual P0 clock range is invalid.")
    return baseline


def read_nvml_clock_relation(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    domain: int,
    resolver: NvmlNativeFunctionResolverProtocol | None,
    *,
    required_route: str | None = None,
) -> tuple[int, int, int, str]:
    if required_route not in (None, "modern", "legacy"):
        raise ValidationError("NVML required clock relation is invalid.")
    if required_route == "modern" and resolver is None:
        raise StateError("NVML frozen clock relation is unavailable.")
    if resolver is not None and required_route != "legacy":
        try:
            original, minimum, maximum = read_clock_offset(
                handle=handle,
                clock_type=domain,
                pstate=0,
                resolve_function=resolver,
                native_error=module.NVMLError,
            )
        except NvmlClockOffsetError as exception:
            if (
                required_route == "modern"
                or exception.native_invoked
                or exception.native_status != 13
            ):
                raise
        else:
            return original, minimum, maximum, "modern"
    try:
        if domain == 0:
            getter, range_getter = (
                module.nvmlDeviceGetGpcClkVfOffset,
                module.nvmlDeviceGetGpcClkMinMaxVfOffset,
            )
        elif domain == 2:
            getter, range_getter = (
                module.nvmlDeviceGetMemClkVfOffset,
                module.nvmlDeviceGetMemClkMinMaxVfOffset,
            )
        else:
            raise ValidationError("NVML legacy clock domain is unsupported.")
    except AttributeError as exception:
        raise NvmlClockFacilityUnavailable("NVML legacy clock facility is absent.") from exception
    if not callable(getter) or not callable(range_getter):
        raise ValidationError("NVML legacy clock facility is malformed.")
    minimum, maximum = _clock_range(range_getter(handle))
    original = require_int_in_range_strict(
        getter(handle),
        minimum=minimum,
        maximum=maximum,
        error_message="NVML original clock offset is invalid.",
    )
    return original, minimum, maximum, "legacy"


def read_coherent_nvml_clock_baseline(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    domain: int,
    observed_relation: tuple[int, int, int, str],
    resolver: NvmlNativeFunctionResolverProtocol | None,
) -> int:
    baseline = read_nvml_clock_baseline(module, handle, domain)
    repeated_relation = read_nvml_clock_relation(
        module, handle, domain, resolver, required_route=observed_relation[3]
    )
    if repeated_relation != observed_relation:
        raise GPUClockConversionUnavailableError(
            "NVML clock offset or constraints changed during P0 observation.",
            details={"reason": "clock_observation_changed"},
        )
    return baseline


def _read_nvml_member_clock_relation(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    resolver: NvmlNativeFunctionResolverProtocol | None,
) -> tuple[int, int, int, str]:
    if member.domain_id is None:
        raise ValidationError("NVML frozen clock domain is unavailable.")
    if member.member_id == "vf_offset:legacy":
        required_route = "legacy"
    elif member.member_id == "vf_offset:modern":
        required_route = "modern"
    else:
        raise StateError("NVML frozen clock relation is unavailable.")
    return read_nvml_clock_relation(
        module, handle, member.domain_id, resolver, required_route=required_route
    )


def _clock_range(value: tuple[int, int]) -> tuple[int, int]:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(not is_strict_int(number) for number in value)
        or value[0] > value[1]
    ):
        raise ValidationError("NVML actual clock range is invalid.")
    return value[0], value[1]


def read_nvml_clock_member(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    resolver: NvmlNativeFunctionResolverProtocol | None,
) -> NvmlControlObservation:
    domain = member.domain_id
    if (
        (member.field, domain, member.pstate_id, member.native_unit)
        not in (("core_clock", 0, 0, "MHz"), ("mem_clock", 2, 0, "MHz"))
        or domain is None
        or member.requested_mode is not None
        or member.original_mode is not None
    ):
        raise ValidationError("NVML frozen clock member routing is invalid.")
    requested = require_int_in_range_strict(
        member.requested_value,
        minimum=-(2**31),
        maximum=2**31 - 1,
        error_message="NVML frozen offset is invalid.",
    )
    if record.requested_modes[member.field] == "auto" and requested != 0:
        raise ValidationError("NVML automatic clock policy requires its native zero offset.")
    user_value = require_positive_int_strict(
        record.requested_settings[member.field], error_message="NVML frozen user clock is invalid."
    )
    if record.requested_units[member.field] != "MHz":
        raise ValidationError("NVML frozen user clock unit is invalid.")
    value, minimum, maximum, route = _read_nvml_member_clock_relation(
        module, handle, member, resolver
    )
    if member.member_id != f"vf_offset:{route}":
        raise StateError("NVML native clock relation changed.")
    automatic = record.requested_modes[member.field] == "auto"
    meaning = minimum <= requested <= maximum and (automatic or domain != 2)
    original_restorable = (
        is_strict_int(member.original_value) and minimum <= member.original_value <= maximum
    )
    failure = None
    if not automatic:
        try:
            actual_baseline = read_coherent_nvml_clock_baseline(
                module, handle, domain, (value, minimum, maximum, route), resolver
            )
        except module.NVMLError as exception:
            meaning = False
            failure = StateError(
                "NVML P0 conversion authority could not be revalidated.", cause=exception
            )
        else:
            meaning = meaning and actual_baseline == user_value - requested
    return NvmlControlObservation(value, None, meaning, original_restorable, failure)


def read_nvml_original_clock_member(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    resolver: NvmlNativeFunctionResolverProtocol | None,
) -> NvmlControlObservation:
    domain = member.domain_id
    if (
        (member.field, domain, member.pstate_id, member.native_unit)
        not in (("core_clock", 0, 0, "MHz"), ("mem_clock", 2, 0, "MHz"))
        or domain is None
        or member.original_mode is not None
    ):
        raise ValidationError("NVML original clock member routing is invalid.")
    value, minimum, maximum, _route = _read_nvml_member_clock_relation(
        module, handle, member, resolver
    )
    restorable = (
        is_strict_int(member.original_value) and minimum <= member.original_value <= maximum
    )
    return NvmlControlObservation(value, None, restorable, restorable, None)
