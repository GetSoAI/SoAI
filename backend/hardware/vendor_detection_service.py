"""SoAI - GPU vendor detection service [backend/hardware/vendor_detection_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform
import threading
import time
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.protocols import TraceLogger
from core.serialization.json_parsing import parse_json_value
from core.system.protocols import CommandExecutorProtocol
from core.types.json_value import filter_json_dict_list
from hardware.gpu_inventory.windows_adapters import (
    WINDOWS_VIDEO_CONTROLLER_QUERY,
    classify_windows_display_adapter,
    coerce_windows_gpu_name,
    detect_windows_adapter_vendor,
)
from hardware.vendors.vendor_metadata import (
    darwin_gpu_vendor_matches,
    linux_gpu_vendor_matches,
)
from hardware.vendors.vendor_types import UNKNOWN_VENDOR
from hardware.windows_commands import build_windows_powershell_command

__all__ = (
    "GPUVendorDetectionService",
    "GPUVendorDetectionServiceDependencies",
)

OPERATION_DETECT_VENDORS = "hardware.vendor_detection.detect_vendors"


@dataclass(frozen=True, slots=True)
class GPUVendorDetectionServiceDependencies:
    logger: TraceLogger
    command_executor: CommandExecutorProtocol
    cache_ttl_seconds: float = 60.0

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GPUVendorDetectionServiceDependencies",
            cache_ttl_seconds=self.cache_ttl_seconds,
            command_executor=self.command_executor,
            logger=self.logger,
        )


class GPUVendorDetectionService:
    __slots__ = ("_cache", "_cache_ttl", "_executor", "_lock", "_logger")

    def __init__(self, deps: GPUVendorDetectionServiceDependencies) -> None:
        self._logger: TraceLogger = deps.logger
        self._executor: CommandExecutorProtocol = deps.command_executor
        self._cache_ttl: float = deps.cache_ttl_seconds
        self._cache: tuple[float, set[str]] | None = None
        self._lock: threading.Lock = threading.Lock()

    def get_system_gpu_vendors(self) -> set[str]:
        now = time.monotonic()
        with self._lock:
            if self._cache is not None:
                cached_time, cached_vendors = self._cache
                if now - cached_time <= self._cache_ttl:
                    return set(cached_vendors)

        vendors = self._detect_vendors()

        with self._lock:
            self._cache = (now, set(vendors))
        return set(vendors)

    def _detect_vendors(self) -> set[str]:
        vendors: set[str] = set()
        try:
            system = platform.system()
            if system == "Linux":
                vendors = self._detect_linux_vendors()
            elif system == "Windows":
                vendors = self._detect_windows_vendors()
            elif system == "Darwin":
                vendors = self._detect_darwin_vendors()
        except (OSError, RuntimeError, ValueError) as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="Could not perform preliminary GPU vendor scan.",
                operation=OPERATION_DETECT_VENDORS,
                level="trace",
            )
        return vendors

    def _detect_linux_vendors(self) -> set[str]:
        vendors: set[str] = set()
        result = self._executor.execute(["lspci"], timeout=5, shell=False, use_sudo=False)
        if result.return_code == 0:
            for line in result.stdout.splitlines():
                vendors.update(linux_gpu_vendor_matches(line))
        return vendors

    def _detect_windows_vendors(self) -> set[str]:
        vendors: set[str] = set()
        command = build_windows_powershell_command(WINDOWS_VIDEO_CONTROLLER_QUERY)
        result = self._executor.execute(command, timeout=10, shell=False, use_sudo=False)
        if result.return_code != 0 or not result.stdout:
            return vendors
        try:
            parsed = parse_json_value(result.stdout, field="Win32_VideoController output")
        except ValidationError as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="Could not parse preliminary Windows GPU vendor scan.",
                operation=OPERATION_DETECT_VENDORS,
                level="trace",
            )
            return vendors
        for record in filter_json_dict_list(parsed if isinstance(parsed, list) else [parsed]):
            name = coerce_windows_gpu_name(record.get("Name"))
            vendor = detect_windows_adapter_vendor(record, name)
            adapter_type = classify_windows_display_adapter(
                gpu_info=record,
                vendor=vendor,
                name=name,
            )
            if adapter_type is None and vendor != UNKNOWN_VENDOR:
                vendors.add(vendor)
        return vendors

    def _detect_darwin_vendors(self) -> set[str]:
        vendors: set[str] = set()
        result = self._executor.execute(
            ["system_profiler", "SPDisplaysDataType"],
            timeout=10,
            shell=False,
            use_sudo=False,
        )
        if result.return_code == 0 and result.stdout:
            vendors.update(darwin_gpu_vendor_matches(result.stdout))
        return vendors

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None

    def set_cache_ttl(self, cache_ttl_seconds: float) -> None:
        with self._lock:
            self._cache_ttl = cache_ttl_seconds
