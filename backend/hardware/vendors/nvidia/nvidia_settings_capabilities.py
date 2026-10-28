"""SoAI - NVIDIA settings capability collection [backend/hardware/vendors/nvidia/nvidia_settings_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_capabilities.payloads import (
    mark_control_capability_unsupported,
    read_control_capability_section,
    update_control_capability_section,
)
from hardware.gpu_inventory.executable_resolution import GpuExecutableState
from hardware.vendors.nvidia.settings_control_queries import (
    NvidiaSettingsSession,
    parse_settings_attribute,
    query_settings_fans,
    query_settings_output,
)
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

OPERATION_HARDWARE_NVIDIA_SETTINGS_FAN_CAPABILITIES = "hardware.nvidia.settings.fan_capabilities"


__all__ = ("apply_nvidia_settings_capabilities",)

RANGE_PATTERN_TEXT = "valid values for '[^']+' are in the range\\s+(-?\\d+)\\s+-\\s+(-?\\d+)"
VALUE_PATTERN_TEXT = "\\):\\s*(-?\\d+)(?:\\.|\\s|$)"
NVIDIA_SETTINGS_PERF_LEVEL = 3
NVIDIA_SETTINGS_QUERY_TIMEOUT_SECONDS = 2
SETTINGS_FAN_QUERY_EXCEPTIONS: tuple[type[Exception], ...] = (
    StateError,
    ValidationError,
    OSError,
    *RECOVERABLE_EXCEPTIONS,
)


def apply_nvidia_settings_capabilities(
    logger: TraceLogger,
    vendor_id: int,
    gpu_caps: JSONDict,
    *,
    controller: NvidiaSettingsController,
    deadline: MonotonicDeadline | None = None,
) -> bool:
    operation_deadline = deadline or deadline_after(10.0)
    with controller.probe_environment(operation_deadline) as env:
        if env is None:
            _mark_probe_failure(gpu_caps, "core_clock_mhz", "x_display")
            _mark_probe_failure(gpu_caps, "mem_clock_mhz", "x_display")
            _mark_probe_failure(gpu_caps, "fan_speed_percent", "x_display")
            return False
        _apply_clock_capability(
            logger=logger,
            env=env,
            controller=controller,
            deadline=operation_deadline,
            vendor_id=vendor_id,
            gpu_caps=gpu_caps,
            caps_key="core_clock_mhz",
            attribute="GPUGraphicsClockOffset",
        )
        _apply_clock_capability(
            logger=logger,
            env=env,
            controller=controller,
            deadline=operation_deadline,
            vendor_id=vendor_id,
            gpu_caps=gpu_caps,
            caps_key="mem_clock_mhz",
            attribute="GPUMemoryTransferRateOffset",
        )
        _apply_fan_capability(
            logger=logger,
            env=env,
            controller=controller,
            vendor_id=vendor_id,
            gpu_caps=gpu_caps,
            deadline=operation_deadline,
        )
        return True


def _apply_clock_capability(
    *,
    logger: TraceLogger,
    env: Mapping[str, str],
    controller: NvidiaSettingsController,
    deadline: MonotonicDeadline,
    vendor_id: int,
    gpu_caps: JSONDict,
    caps_key: str,
    attribute: str,
) -> None:
    perf_level = NVIDIA_SETTINGS_PERF_LEVEL
    query_output, failure_reason = _query_nvidia_settings(
        logger,
        env,
        f"[gpu:{vendor_id}]/{attribute}[{perf_level}]",
        deadline,
        controller=controller,
    )
    if query_output is None:
        _mark_probe_failure(gpu_caps, caps_key, failure_reason)
        return
    offset_min, offset_max = _parse_range(query_output)
    current_offset = _parse_value(query_output)
    if offset_min is None or offset_max is None or offset_min >= offset_max:
        _mark_probe_failure(gpu_caps, caps_key, "parse_error")
        return
    caps = read_control_capability_section(gpu_caps, caps_key)
    default_clock = coerce_int_from_scalar(caps.get("default"))
    if default_clock is None:
        _mark_probe_failure(gpu_caps, caps_key, "parse_error")
        return
    current_clock = default_clock + current_offset if current_offset is not None else None
    absolute_min = default_clock + offset_min
    absolute_max = default_clock + offset_max
    update_control_capability_section(
        gpu_caps,
        caps_key,
        {
            "current": current_clock,
            "min": absolute_min,
            "max": absolute_max,
            "offset_min": offset_min,
            "offset_max": offset_max,
            "perf_level": perf_level,
            "supported": True,
            "via_nvidia_settings": True,
        },
    )


def _apply_fan_capability(
    *,
    logger: TraceLogger,
    env: Mapping[str, str],
    controller: NvidiaSettingsController,
    deadline: MonotonicDeadline,
    vendor_id: int,
    gpu_caps: JSONDict,
) -> None:
    if deadline.remaining_seconds() < 1:
        _mark_probe_failure(gpu_caps, "fan_speed_percent", "timeout")
        return
    try:
        session = NvidiaSettingsSession(
            controller.native_query, env["DISPLAY"], env.get("XAUTHORITY")
        )
        state = parse_settings_attribute(
            query_settings_output(
                session, f"[gpu:{vendor_id}]/GPUFanControlState", deadline=deadline
            ),
            attribute="GPUFanControlState",
            target_type="gpu",
            target_id=vendor_id,
        ).value
        if state not in (0, 1):
            raise ValidationError("NVIDIA settings actual fan policy is invalid.")
        fans = query_settings_fans(session, native_gpu_id=vendor_id, deadline=deadline)
        minimum = max(fan.attribute.minimum for fan in fans if fan.attribute.minimum is not None)
        maximum = min(fan.attribute.maximum for fan in fans if fan.attribute.maximum is not None)
        if minimum > maximum:
            raise ValidationError("NVIDIA settings related fan ranges have no shared target.")
        targets = {fan.attribute.value for fan in fans}
        if state == 1 and any(
            fan.attribute.minimum is None
            or fan.attribute.maximum is None
            or not fan.attribute.minimum <= fan.attribute.value <= fan.attribute.maximum
            for fan in fans
        ):
            raise ValidationError("NVIDIA settings manual fan target is invalid.")
        if deadline.expired():
            raise TimeoutError("NVIDIA settings fan capability deadline expired.")
        update_control_capability_section(
            gpu_caps,
            "fan_speed_percent",
            {
                "current": next(iter(targets)) if state == 1 and len(targets) == 1 else None,
                "min": minimum,
                "max": maximum,
                "mode": "manual" if state == 1 else "auto",
                "supported": True,
                "via_nvidia_settings": True,
            },
        )
    except SETTINGS_FAN_QUERY_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="NVIDIA related fan capability query failed.",
            operation=OPERATION_HARDWARE_NVIDIA_SETTINGS_FAN_CAPABILITIES,
            level="trace",
        )
        _mark_probe_failure(
            gpu_caps,
            "fan_speed_percent",
            "timeout" if isinstance(exception, TimeoutError) else "device_unavailable",
        )


def _query_nvidia_settings(
    logger: TraceLogger,
    env: Mapping[str, str],
    target: str,
    deadline: MonotonicDeadline,
    *,
    controller: NvidiaSettingsController,
) -> tuple[str | None, str | None]:
    timeout = int(min(NVIDIA_SETTINGS_QUERY_TIMEOUT_SECONDS, deadline.remaining_seconds()))
    if timeout < 1:
        return (None, "timeout")
    query = controller.native_query
    if query.executable.state != GpuExecutableState.FOUND or query.executable.path is None:
        return (None, "tool_missing")
    result = query.capture(
        [query.executable.path, "-q", target],
        env=env,
        timeout=timeout,
    )
    output = result.stdout + result.stderr
    if result.return_code != 0:
        reason = _classify_query_failure(result.return_code, output)
        logger.trace(
            "nvidia-settings capability query failed for %s: %s",
            target,
            output.strip(),
        )
        return (None, reason)
    if not output.strip():
        return (None, "parse_error")
    return (output, None)


def _classify_query_failure(return_code: int, output: str) -> str:
    normalized_output = output.lower()
    if return_code == 127 or "not found" in normalized_output:
        return "tool_missing"
    if (
        "authorization required" in normalized_output
        or "unable to load info from any available system" in normalized_output
        or "could not connect to display" in normalized_output
        or "unable to init server" in normalized_output
    ):
        return "x_display"
    if "permission denied" in normalized_output:
        return "permission_denied"
    if "no targets match" in normalized_output or "error resolving target" in normalized_output:
        return "device_unavailable"
    return "device_unavailable"


def _mark_probe_failure(gpu_caps: JSONDict, caps_key: str, reason: str | None) -> None:
    mark_control_capability_unsupported(
        gpu_caps,
        caps_key,
        reason or "device_unavailable",
        force=False,
    )


def _parse_range(output: str) -> tuple[int | None, int | None]:
    match = re.search(RANGE_PATTERN_TEXT, output, re.IGNORECASE)
    if match is None:
        return (None, None)
    return (int(match.group(1)), int(match.group(2)))


def _parse_value(output: str) -> int | None:
    match = re.search(VALUE_PATTERN_TEXT, output)
    if match is None:
        return None
    return int(match.group(1))
