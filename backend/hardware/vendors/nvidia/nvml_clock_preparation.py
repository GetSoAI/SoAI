"""SoAI - NVML clock originals and frozen P0 conversion authority [backend/hardware/vendors/nvidia/nvml_clock_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import (
    GPUClockCombinationUnsupportedError,
    GPUClockConversionUnavailableError,
)
from core.hardware.gpu_recovery_records import GPURecoveryMember
from core.types.json import JSONDict, JSONValue
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_int_in_range_strict, require_positive_int_strict
from hardware.gpu_capabilities.payloads import read_control_capability_section
from hardware.gpu_tuning.control_recovery_records import create_observed_recovery_member
from hardware.vendors.nvidia.internal_protocols import (
    NvmlApplicationClockModuleProtocol,
    NvmlControlModuleProtocol,
    NvmlErrorValueProtocol,
    NvmlNativeFunctionResolverProtocol,
)
from hardware.vendors.nvidia.nvml_application_clock_preparation import (
    prepare_nvml_application_members,
)
from hardware.vendors.nvidia.nvml_clock_observations import (
    NvmlClockFacilityUnavailable,
    read_coherent_nvml_clock_baseline,
    read_nvml_clock_baseline,
    read_nvml_clock_relation,
)
from hardware.vendors.nvidia.nvml_clock_offset_abi import NvmlClockOffsetError

if TYPE_CHECKING:
    from hardware.vendors.nvidia.internal_protocols import NvmlDeviceHandle


__all__ = (
    "selected_nvml_clock_facilities",
    "require_compatible_nvml_clock_facilities",
    "prepare_nvml_clock_members",
    "require_core_vf_unavailable",
    "prepare_nvml_clock_member",
)


def selected_nvml_clock_facilities(
    capabilities: JSONDict, fields: Collection[str]
) -> dict[str, str]:
    selected: dict[str, str] = {}
    for field, caps_key in (("core_clock", "core_clock_mhz"), ("mem_clock", "mem_clock_mhz")):
        section = read_control_capability_section(capabilities, caps_key)
        if field in fields and section.get("control_backend") in ("nvml", "nvidia_nvml"):
            selected[field] = (
                "application_clocks"
                if section.get("clock_control_type") == "application_clocks"
                else "vf_offset"
            )
    return selected


def require_compatible_nvml_clock_facilities(clock_control_types: Mapping[str, str]) -> None:
    if len(set(clock_control_types.values())) > 1:
        raise GPUClockCombinationUnsupportedError("NVML mixed clock conversion is unavailable.")


def prepare_nvml_clock_members(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    settings: JSONDict,
    modes: JSONDict,
    resolver: NvmlNativeFunctionResolverProtocol | None,
    clock_control_types: Mapping[str, str] | None,
) -> tuple[GPURecoveryMember, ...]:
    clock_fields = set(settings).intersection(("core_clock", "mem_clock"))
    if clock_control_types is not None:
        if set(clock_control_types) != clock_fields or any(
            control_type not in ("vf_offset", "application_clocks")
            for control_type in clock_control_types.values()
        ):
            raise ValidationError("NVML selected clock facilities are incomplete or invalid.")
        require_compatible_nvml_clock_facilities(clock_control_types)
        if "application_clocks" in clock_control_types.values():
            return prepare_nvml_application_members(module, handle, settings, modes)
    if "mem_clock" in settings and clock_control_types is None:
        if modes["mem_clock"] == "manual" or (
            "core_clock" not in settings and isinstance(module, NvmlApplicationClockModuleProtocol)
        ):
            if "core_clock" in settings:
                require_core_vf_unavailable(module, handle, resolver)
            return prepare_nvml_application_members(module, handle, settings, modes)
    members: list[GPURecoveryMember] = []
    for field, domain in (("core_clock", 0), ("mem_clock", 2)):
        if field not in settings:
            continue
        try:
            member, baseline = prepare_nvml_clock_member(
                module, handle, field, domain, settings[field], modes[field], resolver
            )
        except (module.NVMLError, NvmlClockOffsetError, NvmlClockFacilityUnavailable) as exception:
            if not _clock_route_unavailable(exception):
                raise
            if field == "mem_clock" and "core_clock" in settings:
                raise GPUClockCombinationUnsupportedError(
                    "NVML mixed clock conversion is unavailable."
                ) from exception
            if field == "core_clock" and "mem_clock" in settings:
                require_core_vf_unavailable(module, handle, resolver)
            return prepare_nvml_application_members(module, handle, settings, modes)
        members.append(member)
        if modes[field] == "auto":
            settings[field] = baseline
    return tuple(members)


def _clock_route_unavailable(exception: Exception) -> bool:
    return (
        isinstance(exception, NvmlClockFacilityUnavailable)
        or (
            isinstance(exception, NvmlErrorValueProtocol)
            and is_strict_int(exception.value)
            and exception.value == 3
        )
        or (isinstance(exception, NvmlClockOffsetError) and exception.native_status == 3)
    )


def require_core_vf_unavailable(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    resolver: NvmlNativeFunctionResolverProtocol | None,
) -> None:
    try:
        read_nvml_clock_baseline(module, handle, 0)
        read_nvml_clock_relation(module, handle, 0, resolver)
    except (module.NVMLError, NvmlClockOffsetError, NvmlClockFacilityUnavailable) as exception:
        if not _clock_route_unavailable(exception):
            raise
        if resolver is None or not isinstance(exception, NvmlClockOffsetError):
            return
        try:
            read_nvml_clock_relation(module, handle, 0, None)
        except (module.NVMLError, NvmlClockFacilityUnavailable) as legacy_exception:
            if not _clock_route_unavailable(legacy_exception):
                raise
            return
    raise GPUClockCombinationUnsupportedError("NVML mixed clock conversion is unavailable.")


def prepare_nvml_clock_member(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    field: str,
    domain: int,
    value: JSONValue,
    mode: JSONValue,
    resolver: NvmlNativeFunctionResolverProtocol | None,
) -> tuple[GPURecoveryMember, int]:
    if (field, domain) not in (("core_clock", 0), ("mem_clock", 2)):
        raise ValidationError("NVML requested clock field conflicts with native domain.")
    if domain == 2 and mode != "auto":
        raise GPUClockConversionUnavailableError(
            "NVML absolute memory clock conversion is unavailable.",
            details={"field": field, "reason": "conversion_unavailable"},
        )
    relation = read_nvml_clock_relation(module, handle, domain, resolver)
    baseline = read_coherent_nvml_clock_baseline(module, handle, domain, relation, resolver)
    original, minimum, maximum, route = relation
    requested = (
        0
        if mode == "auto"
        else require_positive_int_strict(
            value, error_message="NVML user absolute clock is invalid."
        )
        - baseline
    )
    requested = require_int_in_range_strict(
        requested,
        minimum=minimum,
        maximum=maximum,
        error_message="NVML clock offset target is outside actual constraints.",
    )
    member = create_observed_recovery_member(
        field=field,
        member_id=f"vf_offset:{route}",
        domain_id=domain,
        pstate_id=0,
        original_value=original,
        original_mode=None,
        native_unit="MHz",
        backend="nvml",
        requested_value=requested,
        requested_mode=None,
    )
    return member, baseline
