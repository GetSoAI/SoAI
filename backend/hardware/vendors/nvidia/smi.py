"""SoAI - NVIDIA settings integration [backend/hardware/vendors/nvidia/smi.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import atexit
import os
import re
import threading
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.files.temp_files import (
    acquire_directory_lock,
    release_directory_lock,
    system_temp_directory,
)
from core.logging.trace import get_logger
from core.system.commands import run_argv_capture
from core.system.process_launcher import (
    DEVNULL_STREAM,
    SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    spawn_managed_process,
)
from core.timing.constants import (
    LOCAL_IO_TIMEOUT_SEC,
    RESPONSIVE_TIMEOUT_SEC,
    SHORT_POLL_INTERVAL_SEC,
)
from core.timing.monotonic import monotonic_ms
from core.timing.sleep import sleep_seconds
from hardware.vendors.nvidia.paths import nvidia_xorg_config_path
from hardware.vendors.nvidia.smi_display_environment import detect_display_environment

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.process_launcher import ManagedProcess

__all__ = ("NvidiaSettingsController",)

LOGGER_NAME = "SoAI.hardware.vendors.smi"
OPERATION_HARDWARE_NVIDIA_START_HEADLESS_XSERVER = "hardware_nvidia.start_headless_xserver"
OPERATION_HARDWARE_NVIDIA_STOP_XSERVER = "hardware_nvidia.stop_xserver"
MAX_PERF_LEVEL = 8
HEADLESS_XSERVER_LOCK_DIR_NAME = "soai-nvidia-headless-xserver.lock"
HEADLESS_XSERVER_LOCK_TIMEOUT_MS = 10_000
RANGE_PATTERN_TEXT = "valid values for '[^']+' are in the range\\s+(-?\\d+)\\s+-\\s+(-?\\d+)"


class NvidiaSettingsController:
    def __init__(
        self,
        display: str | None = None,
        controller_logger: TraceLogger | None = None,
    ) -> None:
        self._logger: TraceLogger = controller_logger or get_logger(LOGGER_NAME)
        self._lock = threading.Lock()
        self._display = display
        self._xserver_process: ManagedProcess | None = None
        self._env: dict[str, str] | None = None
        self._atexit_registered: bool = False

    def _ensure_display(self) -> bool:
        if self._env is not None:
            return True
        env_config = detect_display_environment(self._logger)
        display_value = env_config.get("display")
        display = self._display or (display_value if isinstance(display_value, str) else ":1")
        self._env = os.environ.copy()
        self._env["DISPLAY"] = display
        xauthority_value = env_config.get("xauthority")
        if isinstance(xauthority_value, str) and xauthority_value:
            self._env["XAUTHORITY"] = xauthority_value
        if env_config["needs_own_xserver"] and (not env_config["has_display_manager"]):
            return self._ensure_headless_xserver()
        return True

    def ensure_display_environment(self) -> Mapping[str, str] | None:
        with self._lock:
            if not self._ensure_display():
                return None
            return dict(self._env) if self._env is not None else None

    def _use_existing_display_if_available(self) -> bool:
        if self._env is None:
            return False
        env_config = detect_display_environment(self._logger)
        if env_config.get("has_display_manager") is not True:
            return False
        display_value = env_config.get("display")
        self._env["DISPLAY"] = display_value if isinstance(display_value, str) else ":0"
        xauthority_value = env_config.get("xauthority")
        if isinstance(xauthority_value, str) and xauthority_value:
            self._env["XAUTHORITY"] = xauthority_value
        return True

    def _ensure_headless_xserver(self) -> bool:
        lock_path = os.path.join(system_temp_directory(), HEADLESS_XSERVER_LOCK_DIR_NAME)
        deadline_ms = monotonic_ms() + HEADLESS_XSERVER_LOCK_TIMEOUT_MS
        while True:
            if not acquire_directory_lock(lock_path):
                if self._use_existing_display_if_available():
                    return True
                if monotonic_ms() >= deadline_ms:
                    return False
                sleep_seconds(SHORT_POLL_INTERVAL_SEC)
                continue
            try:
                if self._use_existing_display_if_available():
                    return True
                if not self._start_headless_xserver(":1"):
                    self._logger.warning("Failed to start headless X server for nvidia-settings")
                    return False
                if self._env is None:
                    return False
                self._env["DISPLAY"] = ":1"
                return True
            finally:
                try:
                    release_directory_lock(lock_path)
                except OSError as exception:
                    log_handled_exception(
                        self._logger,
                        exception,
                        message="Failed to remove NVIDIA headless X server lock (non-critical).",
                        operation=OPERATION_HARDWARE_NVIDIA_START_HEADLESS_XSERVER,
                        level="debug",
                    )

    def _start_headless_xserver(self, display: str) -> bool:
        xorg_config_path = nvidia_xorg_config_path()
        if not os.path.exists(xorg_config_path):
            self._logger.warning("xorg.conf not found; cannot start X server")
            return False
        process_ready = threading.Event()
        launch_error: dict[str, BaseException] = {}

        def _run_xserver() -> None:
            try:
                with spawn_managed_process(
                    ["Xorg", display, "-config", xorg_config_path],
                    stdout=DEVNULL_STREAM,
                    stderr=DEVNULL_STREAM,
                ) as process:
                    self._xserver_process = process
                    process_ready.set()
                    process.wait()
            except SUBPROCESS_RECOVERABLE_EXCEPTIONS as exception:
                launch_error["exception"] = exception
                process_ready.set()
                log_exception(
                    self._logger,
                    exception,
                    message="Failed to start X server",
                    operation=OPERATION_HARDWARE_NVIDIA_START_HEADLESS_XSERVER,
                )

        thread = threading.Thread(
            target=_run_xserver,
            name="soai-nvidia-xserver",
            daemon=True,
        )
        thread.start()
        if not process_ready.wait(timeout=2):
            return False
        if launch_error:
            return False
        sleep_seconds(RESPONSIVE_TIMEOUT_SEC)
        process = self._xserver_process
        if not process:
            return False
        if process.poll() is not None:
            return False
        if not self._atexit_registered:
            atexit.register(self._stop_xserver)
            self._atexit_registered = True
        return True

    def _stop_xserver(self) -> None:
        with self._lock:
            if self._xserver_process:
                try:
                    self._xserver_process.terminate()
                    self._xserver_process.wait(timeout=LOCAL_IO_TIMEOUT_SEC)
                except SUBPROCESS_RECOVERABLE_EXCEPTIONS:
                    try:
                        self._xserver_process.kill()
                    except SUBPROCESS_RECOVERABLE_EXCEPTIONS as exception:
                        log_handled_exception(
                            self._logger,
                            exception,
                            message="Failed to kill headless X server process (non-critical).",
                            operation=OPERATION_HARDWARE_NVIDIA_STOP_XSERVER,
                            level="debug",
                        )
                self._xserver_process = None

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
