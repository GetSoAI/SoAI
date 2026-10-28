"""SoAI - Bounded physically selected Intel GPU tools observations [backend/hardware/vendors/intel/i915_tool_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from shutil import which

from core.errors.exceptions import StateError, ValidationError
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from core.validation.numbers import coerce_float_from_json
from hardware.vendors.command_probe import JsonCommandProbeState, run_json_command_probe

__all__ = ("read_i915_tool_telemetry",)


def read_i915_tool_telemetry(device_directory: str, executor: CommandExecutorProtocol) -> JSONDict:
    executable, deadline_command = which("intel_gpu_top"), which("timeout")
    if executable is None or deadline_command is None:
        return {}
    result = run_json_command_probe(
        executor,
        [
            deadline_command,
            "--signal=INT",
            "--kill-after=1",
            "--preserve-status",
            "2",
            executable,
            "-d",
            f"sys:{device_directory}",
            "-J",
            "-s",
            "1000",
            "-o",
            "-",
        ],
        timeout=5,
        use_sudo=False,
        json_field="Intel GPU tools sample",
    )
    if result.state == JsonCommandProbeState.PERMISSION_DENIED:
        raise PermissionError("Intel GPU tools requires permission to observe the selected device.")
    if result.state != JsonCommandProbeState.OBSERVED:
        raise StateError(
            "Intel GPU tools sensor query failed.",
            details=result.private_details,
            cause=result.failure,
        )
    if len(result.stdout) > 1048576:
        raise ValidationError("Intel GPU tools observation exceeds its bounded input size.")
    payload = result.payload
    if not isinstance(payload, list) or not payload or not isinstance(payload[-1], dict):
        raise ValidationError("Intel GPU tools sample has no completed observation.")
    sample = payload[-1]
    metrics: JSONDict = {}
    engines = sample.get("engines")
    render = engines.get("Render/3D") if isinstance(engines, dict) else None
    if isinstance(render, dict) and render.get("unit") == "%":
        busy = coerce_float_from_json(
            render.get("busy"), default=None, allow_bool=False, allow_nonfinite=False
        )
        if busy is not None and 0 <= busy <= 100:
            metrics["utilization"] = busy
    power = sample.get("power")
    if isinstance(power, dict) and power.get("unit") == "W":
        watts = coerce_float_from_json(
            power.get("GPU"), default=None, allow_bool=False, allow_nonfinite=False
        )
        if watts is not None and watts >= 0:
            metrics["power_draw_watts"] = watts
    return metrics
