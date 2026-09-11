"""SoAI - NVIDIA settings capability collection [backend/hardware/vendors/nvidia/nvidia_settings_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.system.commands import run_argv_capture
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_capabilities.payloads import (
    mark_control_capability_unsupported,
    read_control_capability_section,
    update_control_capability_section,
)
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

__all__ = ("apply_nvidia_settings_capabilities",)

RANGE_PATTERN_TEXT = "valid values for '[^']+' are in the range\\s+(-?\\d+)\\s+-\\s+(-?\\d+)"
VALUE_PATTERN_TEXT = "\\):\\s*(-?\\d+)(?:\\.|\\s|$)"
NVIDIA_SETTINGS_PERF_LEVEL = 3
NVIDIA_SETTINGS_QUERY_TIMEOUT_SECONDS = 2


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
            deadline=operation_deadline,
            vendor_id=vendor_id,
            gpu_caps=gpu_caps,
            caps_key="core_clock_mhz",
            attribute="GPUGraphicsClockOffset",
        )
        _apply_clock_capability(
            logger=logger,
            env=env,
            deadline=operation_deadline,
            vendor_id=vendor_id,
            gpu_caps=gpu_caps,
            caps_key="mem_clock_mhz",
            attribute="GPUMemoryTransferRateOffset",
        )
        _apply_fan_capability(
            logger=logger,
            env=env,
            vendor_id=vendor_id,
            gpu_caps=gpu_caps,
            deadline=operation_deadline,
        )
        return True


def _apply_clock_capability(
    *,
    logger: TraceLogger,
    env: Mapping[str, str],
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
    current_clock = coerce_int_from_scalar(caps.get("current"))
    if default_clock is None:
        _mark_probe_failure(gpu_caps, caps_key, "parse_error")
        return
    if current_offset is not None:
        current_clock = default_clock + current_offset
    absolute_min = default_clock + offset_min
    absolute_max = default_clock + offset_max
    update_control_capability_section(
        gpu_caps,
        caps_key,
        {
            "current": current_clock if current_clock is not None else default_clock,
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
    deadline: MonotonicDeadline,
    vendor_id: int,
    gpu_caps: JSONDict,
) -> None:
    state_output, state_failure_reason = _query_nvidia_settings(
        logger,
        env,
        f"[gpu:{vendor_id}]/GPUFanControlState",
        deadline,
    )
    target_output, target_failure_reason = _query_nvidia_settings(
        logger,
        env,
        f"[fan:{vendor_id}]/GPUTargetFanSpeed",
        deadline,
    )
    if state_output is None or target_output is None:
        _mark_probe_failure(
            gpu_caps,
            "fan_speed_percent",
            state_failure_reason or target_failure_reason,
        )
        return
    fan_min, fan_max = _parse_range(target_output)
    if fan_min is None or fan_max is None or fan_min >= fan_max:
        _mark_probe_failure(gpu_caps, "fan_speed_percent", "parse_error")
        return
    state_value = _parse_value(state_output)
    current_value = _parse_value(target_output)
    if state_value is None:
        _mark_probe_failure(gpu_caps, "fan_speed_percent", "parse_error")
        return
    caps = read_control_capability_section(gpu_caps, "fan_speed_percent")
    existing_current_value = coerce_int_from_scalar(caps.get("current"))
    update_control_capability_section(
        gpu_caps,
        "fan_speed_percent",
        {
            "current": current_value if current_value is not None else existing_current_value,
            "min": fan_min,
            "max": fan_max,
            "mode": "manual" if state_value == 1 else "auto",
            "supported": True,
            "via_nvidia_settings": True,
        },
    )


def _query_nvidia_settings(
    logger: TraceLogger,
    env: Mapping[str, str],
    target: str,
    deadline: MonotonicDeadline,
) -> tuple[str | None, str | None]:
    timeout = int(min(NVIDIA_SETTINGS_QUERY_TIMEOUT_SECONDS, deadline.remaining_seconds()))
    if timeout < 1:
        return (None, "timeout")
    result = run_argv_capture(
        ["nvidia-settings", "-q", target],
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
