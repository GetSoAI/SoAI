"""SoAI - SoAIBench GPU telemetry snapshots [backend/hardware/soaibench/telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import BoundedBlockingPool, run_bounded_blocking_call
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.numbers import coerce_float_from_json
from hardware.control_snapshots import find_gpu_entry
from hardware.soaibench.nvidia_telemetry import read_nvidia_fast_telemetry
from hardware.soaibench.telemetry_aggregation import SoAIBenchTelemetryAccumulator
from hardware.soaibench.telemetry_observation import SoAIBenchTelemetrySnapshot

if TYPE_CHECKING:
    from core.hardware.protocols import HardwareManagerProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SoAIBenchTelemetryAccumulator",
    "SoAIBenchTelemetryDiagnostics",
    "SoAIBenchTelemetrySnapshot",
    "read_soaibench_telemetry_snapshot",
    "settings_snapshot_from_gpu",
)

TELEMETRY_READ_OPERATION = "hardware.soaibench.telemetry.read"


@dataclass(slots=True)
class SoAIBenchTelemetryDiagnostics:
    blocking_pool: BoundedBlockingPool
    provider_failure_active: bool = False


async def read_soaibench_telemetry_snapshot(
    hardware_manager: HardwareManagerProtocol,
    *,
    device_id: str,
    temperature_limit_celsius: float | None,
    logger: LoggerProtocol,
    diagnostics: SoAIBenchTelemetryDiagnostics,
) -> SoAIBenchTelemetrySnapshot:
    try:
        snapshot = await run_bounded_blocking_call(
            diagnostics.blocking_pool,
            partial(
                _acquire_soaibench_telemetry_snapshot,
                hardware_manager,
                device_id=device_id,
                temperature_limit_celsius=temperature_limit_celsius,
            ),
            total_timeout_sec=LOCAL_IO_TIMEOUT_SEC,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        if not diagnostics.provider_failure_active:
            log_exception(
                logger,
                exception,
                message="SoAI Bench telemetry provider became unavailable (non-critical).",
                operation=TELEMETRY_READ_OPERATION,
                level="trace",
            )
        diagnostics.provider_failure_active = True
        return _unavailable_snapshot(
            "telemetry_provider_unavailable",
            temperature_limit_celsius=temperature_limit_celsius,
        )
    diagnostics.provider_failure_active = False
    return snapshot


def _acquire_soaibench_telemetry_snapshot(
    hardware_manager: HardwareManagerProtocol,
    *,
    device_id: str,
    temperature_limit_celsius: float | None,
) -> SoAIBenchTelemetrySnapshot:
    fast_telemetry = read_nvidia_fast_telemetry(
        device_id,
        nvml_gate=hardware_manager.nvidia_nvml_gate,
    )
    if fast_telemetry is not None:
        return _snapshot_from_metrics(
            temperature=_numeric(fast_telemetry.get("temperature_celsius")),
            power=_numeric(fast_telemetry.get("avg_power_watts")),
            core_utilization=_numeric(fast_telemetry.get("core_utilization_percent")),
            throttle_detected=_optional_bool(fast_telemetry.get("throttle_detected")),
            temperature_limit_celsius=temperature_limit_celsius,
            diagnostic_code=_optional_string(fast_telemetry.get("diagnostic_code")),
        )
    snapshot = hardware_manager.sync_get_system_info(
        components=["gpu"], cache=False, include_gpu_capabilities=False
    )
    gpu = find_gpu_entry(snapshot, device_id)
    status = snapshot.get("component_status")
    gpu_status = status.get("gpu") if isinstance(status, dict) else None
    stale_component = isinstance(gpu_status, dict) and gpu_status.get("status") not in (
        "available",
        "partial",
    )
    if gpu is None or stale_component or gpu.get("telemetry_available") is False:
        return _unavailable_snapshot(
            "gpu_telemetry_unavailable",
            temperature_limit_celsius=temperature_limit_celsius,
        )
    return _snapshot_from_metrics(
        temperature=_numeric(gpu.get("temperature")),
        power=_numeric(gpu.get("power_draw_watts")),
        core_utilization=_numeric(gpu.get("utilization")),
        throttle_detected=None,
        temperature_limit_celsius=temperature_limit_celsius,
        diagnostic_code=None,
    )


def _snapshot_from_metrics(
    *,
    temperature: float | None,
    power: float | None,
    core_utilization: float | None,
    throttle_detected: bool | None,
    temperature_limit_celsius: float | None,
    diagnostic_code: str | None,
) -> SoAIBenchTelemetrySnapshot:
    temperature_exceeded = (
        temperature is not None
        and temperature_limit_celsius is not None
        and temperature > temperature_limit_celsius
    )
    if temperature_exceeded:
        return SoAIBenchTelemetrySnapshot(
            temperature_celsius=temperature,
            power_watts=power,
            utilization_percent=core_utilization,
            throttle_detected=throttle_detected,
            temperature_limit_celsius=temperature_limit_celsius,
            temperature_exceeded=True,
            instability_reason="temperature_limit_exceeded",
            instability_message=(
                f"GPU temperature {temperature:.1f}C exceeded limit "
                f"{temperature_limit_celsius:.1f}C."
            ),
            diagnostic_code=diagnostic_code,
        )
    return SoAIBenchTelemetrySnapshot(
        temperature_celsius=temperature,
        power_watts=power,
        utilization_percent=core_utilization,
        throttle_detected=throttle_detected,
        temperature_limit_celsius=temperature_limit_celsius,
        temperature_exceeded=False,
        instability_reason=None,
        instability_message=None,
        diagnostic_code=diagnostic_code,
    )


def settings_snapshot_from_gpu(gpu: JSONDict) -> JSONDict:
    clock = coerce_json_dict_or_empty(gpu.get("clock"))
    return _compact_snapshot(
        {
            "power_limit_watts": _numeric(gpu.get("power_limit_watts")),
            "fan_speed": _numeric(gpu.get("fan_speed")),
            "core_clock_mhz": _snapshot_clock(gpu.get("core_clock_mhz"), clock.get("core_mhz")),
            "mem_clock_mhz": _snapshot_clock(gpu.get("mem_clock_mhz"), clock.get("memory_mhz")),
        },
    )


def _unavailable_snapshot(
    diagnostic_code: str,
    *,
    temperature_limit_celsius: float | None,
) -> SoAIBenchTelemetrySnapshot:
    return SoAIBenchTelemetrySnapshot(
        temperature_celsius=None,
        power_watts=None,
        utilization_percent=None,
        throttle_detected=None,
        temperature_limit_celsius=temperature_limit_celsius,
        temperature_exceeded=False,
        instability_reason=None,
        instability_message=None,
        diagnostic_code=diagnostic_code,
    )


def _compact_snapshot(values: JSONDict) -> JSONDict:
    snapshot: JSONDict = {}
    for key, value in values.items():
        if _is_present(value):
            snapshot[key] = value
    return snapshot


def _snapshot_clock(primary: JSONValue, fallback: JSONValue) -> float | None:
    primary_clock = _numeric(primary)
    return primary_clock if primary_clock is not None else _numeric(fallback)


def _is_present(value: JSONValue) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _numeric(value: JSONValue) -> float | None:
    return coerce_float_from_json(
        value,
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )


def _optional_bool(value: JSONValue) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_string(value: JSONValue) -> str | None:
    return value if isinstance(value, str) and value else None
