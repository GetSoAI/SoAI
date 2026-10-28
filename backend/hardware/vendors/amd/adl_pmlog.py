"""SoAI - Finite ADL shared-memory sensor acquisition [backend/hardware/vendors/amd/adl_pmlog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import time
from threading import Event

from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import StateError, ValidationError
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from hardware.vendors.amd.adl_abi import AdlAdapterObservation
from hardware.vendors.amd.adl_pmlog_abi import AdlPMLogLease, AdlPMLogOutput
from hardware.vendors.amd.adl_session import AdlSession

__all__ = ("read_adl_pmlog",)

LOGGER_NAME = "SoAI.hardware.vendors.adl_pmlog"
PMLOG_SAMPLE_INTERVAL_MS = 1000
PMLOG_NOT_READY_STATUS = 4
ADL_PMLOG_INFO_ACTIVITY_GFX = 19

_SENSOR_FIELDS = (
    (1, "core_clock_mhz"),
    (2, "mem_clock_mhz"),
    (8, "temperature"),
    (14, "fan_speed_rpm"),
    (15, "fan_speed"),
    (ADL_PMLOG_INFO_ACTIVITY_GFX, "utilization"),
    (23, "power_draw_watts"),
    (27, "temperature_hotspot_celsius"),
)


def _bind_pmlog(library: ctypes.CDLL) -> None:
    library.ADL2_Overdrive8_PMLogSenorType_Support_Get.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.ADL2_Overdrive8_PMLogSenorType_Support_Get.restype = ctypes.c_int32
    library.ADL2_Overdrive8_PMLog_ShareMemory_Support.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int32),
        ctypes.c_int32,
    ]
    library.ADL2_Overdrive8_PMLog_ShareMemory_Support.restype = ctypes.c_int32
    library.ADL2_Device_PMLog_Device_Create.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    library.ADL2_Device_PMLog_Device_Create.restype = ctypes.c_int32
    library.ADL2_Device_PMLog_Device_Destroy.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    library.ADL2_Device_PMLog_Device_Destroy.restype = ctypes.c_int32
    library.ADL2_Overdrive8_PMLog_ShareMemory_Start.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.c_int32,
        ctypes.c_int32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_int32,
    ]
    library.ADL2_Overdrive8_PMLog_ShareMemory_Start.restype = ctypes.c_int32
    library.ADL2_Overdrive8_PMLog_ShareMemory_Read.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.c_int32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(AdlPMLogOutput),
    ]
    library.ADL2_Overdrive8_PMLog_ShareMemory_Read.restype = ctypes.c_int32
    library.ADL2_Overdrive8_PMLog_ShareMemory_Stop.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    library.ADL2_Overdrive8_PMLog_ShareMemory_Stop.restype = ctypes.c_int32


def read_adl_pmlog(session: AdlSession, adapter: AdlAdapterObservation) -> JSONDict:
    if ctypes.sizeof(AdlPMLogOutput) != 2052 or adapter not in session.read_adapters():
        raise ValidationError("ADL sensor ABI or physical adapter changed.")
    library = session.library
    try:
        _bind_pmlog(library)
    except AttributeError as exception:
        raise StateError(
            "ADL supported sensor exports are unavailable.",
            details={"reason_code": "sensor_export_unavailable"},
            cause=exception,
        ) from exception
    supported = ctypes.c_int32()
    status = library.ADL2_Overdrive8_PMLog_ShareMemory_Support(
        session.context, adapter.adapter_index, ctypes.byref(supported), 0
    )
    if status != 0 or supported.value != 1:
        raise StateError(
            "ADL shared sensor acquisition is unsupported.",
            details={"reason_code": "sensor_interface_unavailable", "native_status": status},
        )
    count, sensors_pointer = ctypes.c_int32(), ctypes.c_void_p()
    status = library.ADL2_Overdrive8_PMLogSenorType_Support_Get(
        session.context, adapter.adapter_index, ctypes.byref(count), ctypes.byref(sensors_pointer)
    )
    if status != 0:
        raise StateError(
            "ADL supported sensor discovery failed.", details={"native_status": status}
        )
    sensor_ids = session.read_owned_integers(sensors_pointer, count.value)
    if (
        not sensor_ids
        or len(set(sensor_ids)) != len(sensor_ids)
        or any(not 0 < sensor < 256 for sensor in sensor_ids)
    ):
        raise ValidationError("ADL supported sensor list is malformed.")
    lease = AdlPMLogLease(adapter.adapter_index)
    session.pmlog_leases.append(lease)
    status = library.ADL2_Device_PMLog_Device_Create(
        session.context, adapter.adapter_index, ctypes.byref(lease.handle)
    )
    if status != 0 or lease.handle.value == 0:
        if status != 0 and lease.handle.value == 0:
            session.pmlog_leases.remove(lease)
        raise StateError(
            "ADL sensor device creation is unverified.", details={"native_status": status}
        )
    try:
        lease.start_attempted = True
        status = library.ADL2_Overdrive8_PMLog_ShareMemory_Start(
            session.context,
            adapter.adapter_index,
            PMLOG_SAMPLE_INTERVAL_MS,
            count.value,
            sensors_pointer,
            ctypes.byref(lease.handle),
            ctypes.byref(lease.shared_memory),
            0,
        )
        if status != 0 or lease.shared_memory.value is None:
            raise StateError("ADL sensor logging start failed.", details={"native_status": status})
        deadline = deadline_after(3.0)
        ready_wait = Event()
        started = time.monotonic()
        reads = not_ready_reads = 0
        while not deadline.expired():
            output = AdlPMLogOutput()
            status = library.ADL2_Overdrive8_PMLog_ShareMemory_Read(
                session.context,
                adapter.adapter_index,
                count.value,
                sensors_pointer,
                ctypes.byref(lease.shared_memory),
                ctypes.byref(output),
            )
            reads += 1
            if deadline.expired():
                raise StateError(
                    "ADL sensor read exceeded its acquisition deadline.",
                    details={"reason_code": "sensor_sample_not_ready"},
                )
            if status == PMLOG_NOT_READY_STATUS:
                not_ready_reads += 1
            elif status != 0:
                raise StateError("ADL sensor read failed.", details={"native_status": status})
            if status == 0:
                metrics = _validated_sample(output, sensor_ids)
                if metrics:
                    if adapter not in session.read_adapters():
                        raise StateError("ADL sensor physical relation changed.")
                    metrics["telemetry_observed_at_ms"] = epoch_ms()
                    get_logger(LOGGER_NAME).debug(
                        (
                            "ADL sensor sample acquired: adapter=%s utilization_sensor_id=%s "
                            "sample_interval_ms=%s start_to_sample_ms=%s reads=%s "
                            "not_ready_reads=%s"
                        ),
                        adapter.adapter_index,
                        ADL_PMLOG_INFO_ACTIVITY_GFX,
                        PMLOG_SAMPLE_INTERVAL_MS,
                        int((time.monotonic() - started) * 1000),
                        reads,
                        not_ready_reads,
                    )
                    return metrics
            ready_wait.wait(min(0.05, deadline.remaining_seconds()))
        raise StateError(
            "ADL sensor sample is not ready.", details={"reason_code": "sensor_sample_not_ready"}
        )
    finally:
        _release_pmlog(session, lease)


def _validated_sample(output: AdlPMLogOutput, supported: tuple[int, ...]) -> JSONDict:
    if output.size not in (0, ctypes.sizeof(AdlPMLogOutput)):
        raise ValidationError("ADL sensor result has an invalid ABI size.")
    metrics: JSONDict = {}
    for sensor, field in _SENSOR_FIELDS:
        entry = output.sensors[sensor]
        if entry.supported not in (0, 1):
            raise ValidationError("ADL sensor support flag is malformed.")
        if sensor not in supported or entry.supported != 1:
            continue
        value = entry.value
        if field in ("fan_speed", "utilization") and not 0 <= value <= 100:
            continue
        if field in ("temperature", "temperature_hotspot_celsius"):
            if not -273 <= value <= 1000:
                continue
        elif value < 0:
            continue
        metrics[field] = value
    return metrics


def _release_pmlog(session: AdlSession, lease: AdlPMLogLease) -> None:
    if lease.start_attempted:
        lease.stop_attempted = True
        status = session.library.ADL2_Overdrive8_PMLog_ShareMemory_Stop(
            session.context, lease.adapter_index, ctypes.byref(lease.handle)
        )
        if status != 0:
            raise StateError(
                "ADL logging stop is unverified; resources remain retained.",
                details={"native_status": status, "reason_code": "native_lifetime_unverified"},
            )
    lease.destroy_attempted = True
    status = session.library.ADL2_Device_PMLog_Device_Destroy(session.context, lease.handle)
    if status != 0:
        raise StateError(
            "ADL sensor device destruction is unverified; resources remain retained.",
            details={"native_status": status, "reason_code": "native_lifetime_unverified"},
        )
    session.pmlog_leases.remove(lease)
