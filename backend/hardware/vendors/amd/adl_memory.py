"""SoAI - Physically bound full-width Windows ADL memory observations [backend/hardware/vendors/amd/adl_memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import GPUInventoryReadState, GPUPhysicalDevice
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from core.validation.strict_integer import is_strict_int
from hardware.vendors.amd.adl_abi import AdlAdapterObservation
from hardware.vendors.amd.adl_physical_inventory import acquire_adl_physical_devices
from hardware.vendors.amd.adl_pmlog import read_adl_pmlog
from hardware.vendors.amd.adl_session import ADL_LIFETIME_FAILURES, AdlRuntime, AdlSession

__all__ = (
    "AdlMemoryInfo2",
    "AdlMemoryObservation",
    "AdlMemoryAcquisition",
    "acquire_adl_memory",
    "read_adl_memory_bytes",
)


class AdlMemoryInfo2(ctypes.Structure):
    memory_size: int = 0
    memory_type: bytes = b""
    memory_bandwidth: int = 0
    hyper_memory_size: int = 0
    invisible_memory_size: int = 0
    visible_memory_size: int = 0
    _fields_ = (
        ("memory_size", ctypes.c_int64),
        ("memory_type", ctypes.c_char * 256),
        ("memory_bandwidth", ctypes.c_int64),
        ("hyper_memory_size", ctypes.c_int64),
        ("invisible_memory_size", ctypes.c_int64),
        ("visible_memory_size", ctypes.c_int64),
    )


@dataclass(frozen=True, slots=True)
class AdlMemoryObservation:
    device: GPUPhysicalDevice
    capacity_bytes: int | None
    state: GPUInventoryReadState = GPUInventoryReadState.OBSERVED
    reason_code: str | None = None
    native_status: int | None = None
    telemetry: JSONDict | None = None
    telemetry_reason_code: str | None = None
    telemetry_failure: Exception | None = None


@dataclass(frozen=True, slots=True)
class AdlMemoryReadFailure:
    state: GPUInventoryReadState
    reason_code: str
    native_status: int | None = None


@dataclass(frozen=True, slots=True)
class AdlMemoryAcquisition:
    state: GPUInventoryReadState
    reason_code: str | None
    observations: tuple[AdlMemoryObservation, ...]
    failure: Exception | None = None


def read_adl_memory_bytes(
    session: AdlSession, adapter: AdlAdapterObservation
) -> int | AdlMemoryReadFailure:
    layout = AdlMemoryInfo2()
    layout.memory_size = 2**33
    layout.memory_bandwidth = 17
    if (
        ctypes.sizeof(AdlMemoryInfo2) != 296
        or bytes(layout)[:8] != (2**33).to_bytes(8, "little")
        or bytes(layout)[264:272] != (17).to_bytes(8, "little")
    ):
        raise ValidationError("ADL memory structure violates its full-width ABI.")
    roster = session.read_adapters()
    if adapter.vendor != 1002 or not adapter.exists or adapter not in roster:
        raise StateError("ADL memory adapter identity is unavailable.")
    try:
        query = session.library.ADL2_Adapter_MemoryInfo2_Get
    except AttributeError as exception:
        raise StateError(
            "ADL memory export is unavailable.",
            details={"reason_code": "memory_export_unavailable"},
            cause=exception,
        ) from exception
    query.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(AdlMemoryInfo2)]
    query.restype = ctypes.c_int32
    memory = AdlMemoryInfo2()
    status = query(session.context, adapter.adapter_index, ctypes.byref(memory))
    if not is_strict_int(status):
        raise ValidationError("ADL memory status violates its integer ABI.")
    if status != 0:
        return AdlMemoryReadFailure(
            GPUInventoryReadState.QUERY_FAILED, "native_memory_unavailable", status
        )
    if memory.memory_size <= 0:
        return AdlMemoryReadFailure(GPUInventoryReadState.INVALID_RESPONSE, "native_memory_invalid")
    if roster != session.read_adapters():
        raise StateError("ADL physical adapters changed during memory observation.")
    return memory.memory_size


def acquire_adl_memory(
    runtime: AdlRuntime | None, executor: CommandExecutorProtocol
) -> AdlMemoryAcquisition:
    if runtime is None:
        return AdlMemoryAcquisition(
            GPUInventoryReadState.RUNTIME_UNAVAILABLE, "native_runtime_unavailable", ()
        )
    try:
        with runtime.session() as session:
            physical = acquire_adl_physical_devices(session, executor)
            observations: list[AdlMemoryObservation] = []
            for row in physical:
                capacities: list[int] = []
                failure: AdlMemoryReadFailure | None = None
                for adapter in row.adapters:
                    capacity = read_adl_memory_bytes(session, adapter)
                    if isinstance(capacity, AdlMemoryReadFailure):
                        failure = capacity
                        break
                    capacities.append(capacity)
                if failure is None and (not capacities or len(set(capacities)) != 1):
                    failure = AdlMemoryReadFailure(
                        GPUInventoryReadState.INVALID_RESPONSE, "native_memory_invalid"
                    )
                telemetry: JSONDict | None = None
                telemetry_reason: str | None = None
                telemetry_failure: Exception | None = None
                try:
                    telemetry = read_adl_pmlog(session, row.adapters[0])
                except (StateError, ValidationError) as exception:
                    if session.pmlog_leases:
                        raise
                    telemetry_failure = exception
                    reason = (
                        exception.details.get("reason_code")
                        if exception.details is not None
                        else None
                    )
                    telemetry_reason = (
                        reason if isinstance(reason, str) else "native_sensor_query_failed"
                    )
                observations.append(
                    AdlMemoryObservation(
                        row.device,
                        capacities[0] if failure is None else None,
                        failure.state if failure is not None else GPUInventoryReadState.OBSERVED,
                        failure.reason_code if failure is not None else None,
                        failure.native_status if failure is not None else None,
                        telemetry,
                        telemetry_reason,
                        telemetry_failure,
                    )
                )
            if physical != acquire_adl_physical_devices(session, executor):
                raise StateError("ADL physical fleet changed during memory observation.")
        return AdlMemoryAcquisition(GPUInventoryReadState.OBSERVED, None, tuple(observations))
    except ValidationError as exception:
        return AdlMemoryAcquisition(
            GPUInventoryReadState.INVALID_RESPONSE, "native_memory_invalid", (), exception
        )
    except StateError as exception:
        reason = exception.details.get("reason_code") if exception.details is not None else None
        return AdlMemoryAcquisition(
            GPUInventoryReadState.QUERY_FAILED,
            reason if isinstance(reason, str) else "native_memory_unavailable",
            (),
            exception,
        )
    except ADL_LIFETIME_FAILURES as exception:
        return AdlMemoryAcquisition(
            GPUInventoryReadState.QUERY_FAILED, "native_memory_query_failed", (), exception
        )
