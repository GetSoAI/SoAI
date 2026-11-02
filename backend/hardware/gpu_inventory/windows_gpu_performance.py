"""SoAI - Physical Windows GPU engine and memory observations [backend/hardware/gpu_inventory/windows_gpu_performance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import re
import struct
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_identity_normalization import observed_pci_bdf_components
from core.hardware.windows_adapter_address import (
    load_windows_adapter_library,
    read_windows_adapter_address,
)
from core.hardware.windows_performance_counters import (
    WindowsRawCounter,
    read_windows_performance_counters,
)
from core.logging.trace import get_logger
from core.types.json import JSONDict
from hardware.gpu_inventory.memory_metrics import bytes_to_mebibytes, memory_percent_used

__all__ = ("WindowsGpuPerformance", "WindowsGpuPerformanceDependencies")

LOGGER_NAME = "SoAI.hardware.gpu_inventory.windows_gpu_performance"
OPERATION_HARDWARE_WINDOWS_GPU_PERFORMANCE_ACQUIRE = "hardware.windows_gpu_performance.acquire"
ENGINE_PATH = r"\GPU Engine(*)\Running Time"
DEDICATED_PATH = r"\GPU Adapter Memory(*)\Dedicated Usage"
SHARED_PATH = r"\GPU Adapter Memory(*)\Shared Usage"
INSTANCE_PATTERN = r"(?:pid_[0-9]+_)?luid_0x([0-9a-fA-F]{8})_0x([0-9a-fA-F]{8})_phys_([0-9]+)(?:_eng_([0-9]+)_engtype_[^\x00]+)?"


@dataclass(frozen=True, slots=True)
class WindowsGpuPerformanceDependencies:
    counter_reader: Callable[[tuple[str, ...]], dict[str, tuple[WindowsRawCounter, ...]]] = (
        read_windows_performance_counters
    )
    adapter_library_loader: Callable[[], ctypes.CDLL | None] = load_windows_adapter_library

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WindowsGpuPerformanceDependencies",
            counter_reader=self.counter_reader,
            adapter_library_loader=self.adapter_library_loader,
        )


class WindowsGpuPerformance:
    def __init__(self, dependencies: WindowsGpuPerformanceDependencies) -> None:
        require_dependencies(owner="WindowsGpuPerformance", dependencies=dependencies)
        self.dependencies = dependencies
        self._previous: dict[str, WindowsRawCounter] = {}
        self._lock = RLock()

    def enrich(self, gpus: list[JSONDict]) -> None:
        if not gpus:
            return
        failures: tuple[type[Exception], ...] = (
            StateError,
            ValidationError,
            OSError,
            AttributeError,
            ctypes.ArgumentError,
            *RECOVERABLE_EXCEPTIONS,
        )
        with self._lock:
            try:
                counters = self.dependencies.counter_reader(
                    (ENGINE_PATH, DEDICATED_PATH, SHARED_PATH)
                )
                library = self.dependencies.adapter_library_loader()
                if library is None:
                    self._previous = {}
                    return
                engines = counters.get(ENGINE_PATH, ())
                observations = self._physical_observations(counters, library)
                for address, values in observations.items():
                    candidates: list[JSONDict] = []
                    for gpu in gpus:
                        pci = gpu.get("pci_bdf_full")
                        components = (
                            observed_pci_bdf_components(pci) if isinstance(pci, str) else None
                        )
                        if components is not None and components[1:] == address:
                            candidates.append(gpu)
                    if len(candidates) != 1:
                        continue
                    gpu = candidates[0]
                    utilization = values.get("utilization")
                    if gpu.get("utilization") is None and utilization is not None:
                        gpu["utilization"] = utilization
                        gpu["telemetry_available"] = True
                        gpu["telemetry_unavailable_reason"] = None
                    dedicated = values.get("dedicated")
                    shared = values.get("shared")
                    if isinstance(dedicated, int):
                        gpu["memory_dedicated_used_mb"] = bytes_to_mebibytes(dedicated)
                        if gpu.get("memory_used_mb") is None:
                            gpu["memory_used_bytes"] = dedicated
                            gpu["memory_used_mb"] = bytes_to_mebibytes(dedicated)
                            total = gpu.get("memory_total_bytes")
                            if (
                                isinstance(total, int)
                                and not isinstance(total, bool)
                                and 0 < total
                                and dedicated <= total
                            ):
                                gpu["percent_used"] = memory_percent_used(dedicated, total)
                    if isinstance(shared, int):
                        gpu["memory_shared_used_mb"] = bytes_to_mebibytes(shared)
                self._previous = {counter.name: counter for counter in engines}
            except failures as exception:
                self._previous = {}
                log_handled_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Optional Windows GPU performance acquisition unavailable.",
                    operation=OPERATION_HARDWARE_WINDOWS_GPU_PERFORMANCE_ACQUIRE,
                    level="trace",
                )

    def _physical_observations(
        self, counters: dict[str, tuple[WindowsRawCounter, ...]], library: ctypes.CDLL
    ) -> dict[tuple[int, int, int], dict[str, int | float]]:
        groups: dict[bytes, dict[str, list[WindowsRawCounter]]] = {}
        excluded: set[bytes] = set()
        for path, rows in counters.items():
            for counter in rows:
                match = re.fullmatch(INSTANCE_PATTERN, counter.name)
                if match is None:
                    raise ValidationError("Windows GPU counter instance has an invalid identity.")
                luid = struct.pack("<II", int(match[2], 16), int(match[1], 16))
                if int(match[3]) != 0:
                    excluded.add(luid)
                if luid not in groups:
                    groups[luid] = {}
                if path not in groups[luid]:
                    groups[luid][path] = []
                groups[luid][path].append(counter)
        observations: dict[tuple[int, int, int], dict[str, int | float]] = {}
        addresses: set[tuple[int, int, int]] = set()
        for luid, paths in groups.items():
            if luid in excluded:
                continue
            address = read_windows_adapter_address(library, luid)
            if address is None or not (
                0 <= address[0] <= 255 and 0 <= address[1] <= 31 and 0 <= address[2] <= 7
            ):
                continue
            if address in addresses:
                raise ValidationError("Windows GPU counter LUIDs map to an ambiguous PCI address.")
            addresses.add(address)
            values: dict[str, int | float] = {}
            for path, field in ((DEDICATED_PATH, "dedicated"), (SHARED_PATH, "shared")):
                memory_rows = paths.get(path, [])
                if len(memory_rows) == 1:
                    values[field] = memory_rows[0].value
            utilization = self._utilization(paths.get(ENGINE_PATH, []), luid)
            if utilization is not None:
                values["utilization"] = utilization
            if read_windows_adapter_address(library, luid) != address:
                raise StateError(
                    "Windows GPU counter physical relation changed during acquisition."
                )
            observations[address] = values
        return observations

    def _utilization(self, rows: list[WindowsRawCounter], luid: bytes) -> float | None:
        previous = {
            name: counter
            for name, counter in self._previous.items()
            if (match := re.fullmatch(INSTANCE_PATTERN, name)) is not None
            and struct.pack("<II", int(match[2], 16), int(match[1], 16)) == luid
        }
        if not rows or set(previous) != {counter.name for counter in rows}:
            return None
        engines: dict[str, float] = {}
        for counter in rows:
            before = previous[counter.name]
            elapsed = counter.timestamp_100ns - before.timestamp_100ns
            running = counter.value - before.value
            match = re.fullmatch(INSTANCE_PATTERN, counter.name)
            if match is None or match[4] is None or not 0 < elapsed <= 300_000_000 or running < 0:
                return None
            engines[match[4]] = engines.get(match[4], 0.0) + 100.0 * running / elapsed
        return min(100.0, max(engines.values())) if engines else None
