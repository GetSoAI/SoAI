"""SoAI - Actual paired NVML application-clock authority [backend/hardware/vendors/nvidia/nvml_application_clock_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_operation_types import GPUClockConversionUnavailableError
from core.hardware.gpu_recovery_records import (
    GPUEffectState,
    GPUOriginalObservationState,
    GPURecoveryMember,
    GPURecoveryRecord,
    GPURestorationState,
    GPUVerificationState,
)
from core.types.json import JSONDict
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_positive_int_strict
from hardware.vendors.nvidia.internal_protocols import (
    NvmlApplicationClockDefaultModuleProtocol,
    NvmlApplicationClockModuleProtocol,
    NvmlControlModuleProtocol,
    NvmlControlObservation,
)

if TYPE_CHECKING:
    from hardware.vendors.nvidia.internal_protocols import NvmlDeviceHandle


__all__ = (
    "require_nvml_application_module",
    "read_application_clock_pair",
    "read_application_default",
    "require_supported_application_pair",
    "prepare_nvml_application_members",
    "application_clock_members",
    "read_nvml_application_observations",
)


def require_nvml_application_module(
    module: NvmlControlModuleProtocol,
) -> NvmlApplicationClockModuleProtocol:
    if not isinstance(module, NvmlApplicationClockModuleProtocol):
        raise GPUClockConversionUnavailableError(
            "NVML absolute application-clock conversion is unavailable."
        )
    if not all(
        callable(function)
        for function in (
            module.nvmlDeviceGetApplicationsClock,
            module.nvmlDeviceGetSupportedMemoryClocks,
            module.nvmlDeviceGetSupportedGraphicsClocks,
            module.nvmlDeviceSetApplicationsClocks,
        )
    ):
        raise StateError("NVML absolute application-clock conversion facilities are malformed.")
    return module


def read_application_clock_pair(
    module: NvmlApplicationClockModuleProtocol, handle: NvmlDeviceHandle
) -> tuple[int, int]:
    graphics = require_positive_int_strict(
        module.nvmlDeviceGetApplicationsClock(handle, 0),
        error_message="NVML observed graphics application clock is invalid.",
    )
    memory = require_positive_int_strict(
        module.nvmlDeviceGetApplicationsClock(handle, 2),
        error_message="NVML observed memory application clock is invalid.",
    )
    if (
        require_positive_int_strict(
            module.nvmlDeviceGetApplicationsClock(handle, 0),
            error_message="NVML repeated graphics application clock is invalid.",
        )
        != graphics
        or require_positive_int_strict(
            module.nvmlDeviceGetApplicationsClock(handle, 2),
            error_message="NVML repeated memory application clock is invalid.",
        )
        != memory
    ):
        raise GPUClockConversionUnavailableError(
            "NVML application-clock observation changed within its paired query."
        )
    return graphics, memory


def read_application_default(
    module: NvmlApplicationClockModuleProtocol, handle: NvmlDeviceHandle, domain: int
) -> int:
    if not isinstance(module, NvmlApplicationClockDefaultModuleProtocol) or not callable(
        module.nvmlDeviceGetDefaultApplicationsClock
    ):
        raise GPUClockConversionUnavailableError(
            "NVML selected automatic application-clock default is unavailable."
        )
    return require_positive_int_strict(
        module.nvmlDeviceGetDefaultApplicationsClock(handle, domain),
        error_message="NVML selected automatic application-clock default is invalid.",
    )


def require_supported_application_pair(
    module: NvmlApplicationClockModuleProtocol,
    handle: NvmlDeviceHandle,
    pair: tuple[int, int],
) -> None:
    memories = module.nvmlDeviceGetSupportedMemoryClocks(handle)
    _require_clock_roster(memories)
    if pair[1] not in memories:
        raise ValidationError("NVML memory application clock is outside its actual roster.")
    graphics = module.nvmlDeviceGetSupportedGraphicsClocks(handle, pair[1])
    _require_clock_roster(graphics)
    if pair[0] not in graphics:
        raise ValidationError("NVML graphics application clock conflicts with its memory pair.")


def _require_clock_roster(values: list[int]) -> None:
    if (
        not isinstance(values, list)
        or not values
        or any(not is_strict_int(value) or not 0 < value < 2**32 for value in values)
        or len(set(values)) != len(values)
    ):
        raise ValidationError("NVML actual application-clock roster is invalid.")


def prepare_nvml_application_members(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    settings: JSONDict,
    modes: JSONDict,
) -> tuple[GPURecoveryMember, ...]:
    application = require_nvml_application_module(module)
    original = read_application_clock_pair(application, handle)
    require_supported_application_pair(application, handle, original)
    requested: list[int] = []
    for position, (field, domain) in enumerate((("core_clock", 0), ("mem_clock", 2))):
        if field not in settings:
            settings[field], modes[field] = original[position], "manual"
        elif modes[field] == "auto":
            settings[field] = read_application_default(application, handle, domain)
        requested.append(
            require_positive_int_strict(
                settings[field], error_message="NVML requested application clock is invalid."
            )
        )
    require_supported_application_pair(application, handle, (requested[0], requested[1]))
    if read_application_clock_pair(application, handle) != original:
        raise StateError("NVML application-clock pair changed during preparation.")
    return tuple(
        GPURecoveryMember(
            field=field,
            member_id="application_clocks",
            domain_id=domain,
            pstate_id=None,
            original_value=original[position],
            original_mode=None,
            native_unit="MHz",
            backend="nvml",
            requested_value=requested[position],
            requested_mode=None,
            original_observation=GPUOriginalObservationState.OBSERVED,
            effect=GPUEffectState.NOT_ATTEMPTED,
            verification=GPUVerificationState.NOT_ATTEMPTED,
            restoration=GPURestorationState.NOT_REQUIRED,
            changed=False,
        )
        for position, (field, domain) in enumerate((("core_clock", 0), ("mem_clock", 2)))
    )


def application_clock_members(record: GPURecoveryRecord) -> tuple[GPURecoveryMember, ...]:
    pair = tuple(
        member
        for member in record.members
        if member.backend == "nvml" and member.member_id == "application_clocks"
    )
    if len(pair) != 2 or tuple(member.field for member in pair) != ("core_clock", "mem_clock"):
        raise ValidationError("NVML application-clock record lacks its complete ordered pair.")
    for member, domain in zip(pair, (0, 2), strict=True):
        native_route_valid = (
            (member.domain_id, member.pstate_id, member.native_unit) == (domain, None, "MHz")
            and member.original_mode is None
            and member.requested_mode is None
        )
        user_request_valid = (
            record.requested_units.get(member.field) == "MHz"
            and record.requested_modes.get(member.field) in ("manual", "auto")
            and record.requested_settings.get(member.field) == member.requested_value
        )
        if not native_route_valid or not user_request_valid:
            raise ValidationError("NVML application-clock routing or absolute units are invalid.")
        require_positive_int_strict(
            member.original_value, error_message="NVML original clock is invalid."
        )
        require_positive_int_strict(
            member.requested_value, error_message="NVML target clock is invalid."
        )
    if any(
        member.backend == "nvml"
        and member.field in ("core_clock", "mem_clock")
        and member not in pair
        for member in record.members
    ):
        raise ValidationError("NVML application pair conflicts with another clock actuator.")
    return pair


def read_nvml_application_observations(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    record: GPURecoveryRecord,
    goal: Literal["requested", "original"],
) -> tuple[NvmlControlObservation, ...]:
    members = application_clock_members(record)
    application = require_nvml_application_module(module)
    current = read_application_clock_pair(application, handle)
    original = tuple(
        require_positive_int_strict(
            member.original_value, error_message="NVML original application clock is invalid."
        )
        for member in members
    )
    require_supported_application_pair(application, handle, (original[0], original[1]))
    requested = tuple(
        require_positive_int_strict(
            member.requested_value, error_message="NVML requested application clock is invalid."
        )
        for member in members
    )
    meaning = True
    if goal == "requested":
        require_supported_application_pair(application, handle, (requested[0], requested[1]))
        for member, domain in zip(members, (0, 2), strict=True):
            if record.requested_modes[member.field] == "auto":
                default = read_application_default(application, handle, domain)
                meaning = meaning and default == member.requested_value
    elif goal != "original":
        raise ValidationError("NVML application read requires an explicit goal.")
    return tuple(NvmlControlObservation(value, None, meaning, True, None) for value in current)
