"""SoAI - NVIDIA settings integration [backend/hardware/vendors/nvidia/smi.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import atexit
import os
import re
import threading
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.files.temp_files import (
    acquire_directory_lock,
    release_directory_lock,
    system_temp_directory,
)
from core.system.commands import run_argv_capture
from core.system.process_launcher import (
    DEVNULL_STREAM,
    SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    spawn_managed_process,
)
from core.timing.constants import (
    SHORT_POLL_INTERVAL_SEC,
)
from core.timing.sleep import sleep_seconds
from hardware.vendors.nvidia.paths import nvidia_xorg_config_path
from hardware.vendors.nvidia.smi_display_environment import (
    DisplaySearchStatus,
    detect_display_environment,
    display_process_environment,
    display_target_occupied,
    enumerate_displays,
    validate_display,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.process_launcher import ManagedProcess

__all__ = ("NvidiaSettingsController",)

LOGGER_NAME = "SoAI.hardware.vendors.smi"
OPERATION_HARDWARE_NVIDIA_START_HEADLESS_XSERVER = "hardware_nvidia.start_headless_xserver"
OPERATION_HARDWARE_NVIDIA_STOP_XSERVER = "hardware_nvidia.stop_xserver"
MAX_PERF_LEVEL = 8
HEADLESS_XSERVER_LOCK_DIR_NAME = "soai-nvidia-headless-xserver.lock"
RANGE_PATTERN_TEXT = "valid values for '[^']+' are in the range\\s+(-?\\d+)\\s+-\\s+(-?\\d+)"


@dataclass(frozen=True, slots=True)
class NvidiaSettingsControllerDependencies:
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(owner="NvidiaSettingsControllerDependencies", logger=self.logger)


class NvidiaSettingsController:
    def __init__(
        self, deps: NvidiaSettingsControllerDependencies, display: str | None = None
    ) -> None:
        self._logger = deps.logger
        self._lock = threading.Lock()
        self._display = display
        self._xserver_process: ManagedProcess | None = None
        self._env: dict[str, str] | None = None
        self._atexit_registered: bool = False

    def _ensure_display(self, deadline: MonotonicDeadline | None = None) -> bool:
        operation_deadline = deadline or deadline_after(10.0)
        if self._env is not None:
            display = self._env["DISPLAY"]
            xauthority = self._env.get("XAUTHORITY")
            self._env = None
            result = validate_display(display, xauthority, operation_deadline)
            if result.status == DisplaySearchStatus.USABLE:
                self._env = display_process_environment(display, xauthority)
                return True
        result = detect_display_environment(self._logger, operation_deadline)
        if result.status == DisplaySearchStatus.USABLE and result.display is not None:
            selected_display = self._display or result.display
            if selected_display != result.display:
                result = validate_display(selected_display, result.xauthority, operation_deadline)
                if result.status != DisplaySearchStatus.USABLE:
                    return False
            self._env = display_process_environment(selected_display, result.xauthority)
            return True
        if result.status != DisplaySearchStatus.NO_DISPLAY:
            return False
        return self._ensure_headless_xserver(operation_deadline)

    @contextmanager
    def probe_environment(self, deadline: MonotonicDeadline) -> Generator[Mapping[str, str] | None]:
        if not self._lock.acquire(timeout=deadline.remaining_seconds()):
            yield None
            return
        try:
            if self._ensure_display(deadline):
                yield dict(self._env) if self._env is not None else None
            else:
                yield None
        finally:
            self._lock.release()

    def ensure_display_environment(
        self,
        deadline: MonotonicDeadline | None = None,
    ) -> Mapping[str, str] | None:
        with self.probe_environment(deadline or deadline_after(10.0)) as environment:
            return environment

    def _ensure_headless_xserver(self, deadline: MonotonicDeadline) -> bool:
        if self._xserver_process is not None:
            if not self._cleanup_owned_process():
                return False
        if not os.path.exists(nvidia_xorg_config_path()):
            return False
        lock_path = os.path.join(system_temp_directory(), HEADLESS_XSERVER_LOCK_DIR_NAME)
        while not deadline.expired():
            if not acquire_directory_lock(lock_path):
                sleep_seconds(min(SHORT_POLL_INTERVAL_SEC, deadline.remaining_seconds()))
                continue
            try:
                result = detect_display_environment(self._logger, deadline)
                if result.status == DisplaySearchStatus.USABLE and result.display is not None:
                    self._env = display_process_environment(result.display, result.xauthority)
                    return True
                if result.status != DisplaySearchStatus.NO_DISPLAY:
                    return False
                display = self._display or ":1"
                if display in enumerate_displays() or display_target_occupied(display, deadline):
                    return False
                return self._start_headless_xserver(display, deadline)
            finally:
                release_directory_lock(lock_path)
        return False

    def _start_headless_xserver(self, display: str, deadline: MonotonicDeadline) -> bool:
        xorg_config_path = nvidia_xorg_config_path()
        if deadline.remaining_seconds() < 1 or not os.path.exists(xorg_config_path):
            return False
        try:
            self._xserver_process = spawn_managed_process(
                ["Xorg", display, "-config", xorg_config_path],
                stdout=DEVNULL_STREAM,
                stderr=DEVNULL_STREAM,
            )
            if not self._atexit_registered:
                atexit.register(self.close)
                self._atexit_registered = True
            while deadline.remaining_seconds() >= 1:
                if self._xserver_process.poll() is not None:
                    break
                result = validate_display(display, None, deadline)
                if result.status == DisplaySearchStatus.USABLE:
                    self._env = display_process_environment(display, None)
                    return True
                if result.status in (
                    DisplaySearchStatus.TOOL_UNAVAILABLE,
                    DisplaySearchStatus.DEADLINE,
                ):
                    break
                sleep_seconds(min(SHORT_POLL_INTERVAL_SEC, deadline.remaining_seconds()))
        except SUBPROCESS_RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="NVIDIA owned display startup failed.",
                operation=OPERATION_HARDWARE_NVIDIA_START_HEADLESS_XSERVER,
                level="debug",
            )
        self._cleanup_owned_process()
        return False

    def _cleanup_owned_process(self) -> bool:
        self._env = None
        process = self._xserver_process
        if process is None:
            return True
        cleanup_deadline = deadline_after(2.0)
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=min(1.0, cleanup_deadline.remaining_seconds()))
                except SUBPROCESS_RECOVERABLE_EXCEPTIONS:
                    process.kill()
            process.wait(timeout=cleanup_deadline.remaining_seconds())
        except SUBPROCESS_RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="NVIDIA owned display cleanup failed.",
                operation=OPERATION_HARDWARE_NVIDIA_STOP_XSERVER,
                level="warning",
            )
            return False
        self._xserver_process = None
        return True

    def close(self) -> None:
        with self._lock:
            self._cleanup_owned_process()

    def _run_nvidia_settings(self, args: list[str]) -> tuple[bool, str]:
        if not self._ensure_display():
            return (False, "X display not available")
        cmd = ["nvidia-settings"] + args
        try:
            result = run_argv_capture(cmd, env=self._env, timeout=10)
            output = result.stdout + result.stderr
            return (result.return_code == 0, output)
        except SUBPROCESS_RECOVERABLE_EXCEPTIONS as exception:
            return (False, str(exception))

    def _resolve_max_perf_level(self, attribute: str, gpu_index: int) -> int | None:
        for perf_level in range(MAX_PERF_LEVEL, -1, -1):
            success, output = self._run_nvidia_settings(
                ["-q", f"[gpu:{gpu_index}]/{attribute}[{perf_level}]"],
            )
            if not success:
                continue
            match = re.search(RANGE_PATTERN_TEXT, output, re.IGNORECASE)
            if match is not None and int(match.group(1)) < int(match.group(2)):
                return perf_level
        return None

    def _set_offset(
        self,
        attribute: str,
        offset: int,
        gpu_index: int = 0,
        perf_level: int | None = None,
    ) -> tuple[bool, str]:
        resolved_perf_level = perf_level
        if resolved_perf_level is None:
            resolved_perf_level = self._resolve_max_perf_level(attribute, gpu_index)
        if resolved_perf_level is None:
            return (False, f"Maximum performance level unavailable for {attribute}.")
        return self._run_nvidia_settings(
            ["-a", f"[gpu:{gpu_index}]/{attribute}[{resolved_perf_level}]={offset}"],
        )

    def set_clock_offset(
        self,
        offset: int,
        gpu_index: int = 0,
        perf_level: int | None = None,
    ) -> tuple[bool, str]:
        with self._lock:
            return self._set_offset("GPUGraphicsClockOffset", offset, gpu_index, perf_level)

    def set_memory_offset(
        self,
        offset: int,
        gpu_index: int = 0,
        perf_level: int | None = None,
    ) -> tuple[bool, str]:
        with self._lock:
            return self._set_offset("GPUMemoryTransferRateOffset", offset, gpu_index, perf_level)

    def set_fan_speed(
        self,
        speed: int,
        gpu_index: int = 0,
        fan_index: int | None = None,
    ) -> tuple[bool, str]:
        with self._lock:
            resolved_fan_index = gpu_index if fan_index is None else fan_index
            self._run_nvidia_settings(["-a", f"[gpu:{gpu_index}]/GPUFanControlState=1"])
            success, output = self._run_nvidia_settings(
                ["-a", f"[fan:{resolved_fan_index}]/GPUTargetFanSpeed={speed}"],
            )
            return (success, output)

    def reset_fan_control(self, gpu_index: int = 0) -> tuple[bool, str]:
        with self._lock:
            return self._run_nvidia_settings(["-a", f"[gpu:{gpu_index}]/GPUFanControlState=0"])

    def reset_clocks(self, gpu_index: int = 0, perf_level: int | None = None) -> tuple[bool, str]:
        with self._lock:
            core_success, core_output = self._set_offset(
                "GPUGraphicsClockOffset",
                0,
                gpu_index,
                perf_level,
            )
            mem_success, mem_output = self._set_offset(
                "GPUMemoryTransferRateOffset",
                0,
                gpu_index,
                perf_level,
            )
            combined_output = f"Core: {core_output}\nMemory: {mem_output}"
            return (core_success and mem_success, combined_output)
