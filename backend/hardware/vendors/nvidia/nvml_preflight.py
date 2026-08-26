"""SoAI - NVML runtime preflight executed in an isolated process [backend/hardware/vendors/nvidia/nvml_preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum

from core.imports.availability import module_available
from core.system.commands import run_argv_capture
from core.timing.constants import CONTROL_TIMEOUT_SEC
from hardware.vendors.nvidia.nvml_preflight_script import (
    NVML_PREFLIGHT_EXIT_MODULE_MISSING,
    NVML_PREFLIGHT_EXIT_NVML_UNAVAILABLE,
    NVML_PREFLIGHT_EXIT_USABLE,
    NVML_PREFLIGHT_SCRIPT,
)

__all__ = (
    "NvmlRuntimeOutcome",
    "NvmlRuntimeStatus",
    "hardware_disabled_nvml_runtime_status",
    "probe_nvml_runtime",
)

NVML_PREFLIGHT_DETAIL_MAX_CHARS = 400
NVML_PREFLIGHT_TIMEOUT_RETURN_CODE = 124
NVML_PREFLIGHT_LAUNCH_FAILURE_RETURN_CODE = 127


class NvmlRuntimeOutcome(Enum):
    USABLE = "usable"
    MODULE_MISSING = "module_missing"
    NVML_UNAVAILABLE = "nvml_unavailable"
    PROBE_TIMED_OUT = "probe_timed_out"
    PROBE_CRASHED = "probe_crashed"
    INTERPRETER_UNAVAILABLE = "interpreter_unavailable"
    HARDWARE_DISABLED = "hardware_disabled"


PROBE_FAILURE_OUTCOMES: frozenset[NvmlRuntimeOutcome] = frozenset(
    {
        NvmlRuntimeOutcome.INTERPRETER_UNAVAILABLE,
        NvmlRuntimeOutcome.PROBE_CRASHED,
        NvmlRuntimeOutcome.PROBE_TIMED_OUT,
    },
)


@dataclass(frozen=True, slots=True)
class NvmlRuntimeStatus:
    outcome: NvmlRuntimeOutcome
    return_code: int
    detail: str

    @property
    def usable(self) -> bool:
        return self.outcome is NvmlRuntimeOutcome.USABLE

    @property
    def probe_failed(self) -> bool:
        return self.outcome in PROBE_FAILURE_OUTCOMES


def hardware_disabled_nvml_runtime_status() -> NvmlRuntimeStatus:
    return NvmlRuntimeStatus(
        outcome=NvmlRuntimeOutcome.HARDWARE_DISABLED,
        return_code=NVML_PREFLIGHT_EXIT_USABLE,
        detail="Host hardware management is disabled for this instance.",
    )


def probe_nvml_runtime() -> NvmlRuntimeStatus:
    if not module_available("pynvml"):
        return NvmlRuntimeStatus(
            outcome=NvmlRuntimeOutcome.MODULE_MISSING,
            return_code=NVML_PREFLIGHT_EXIT_MODULE_MISSING,
            detail="pynvml (nvidia-ml-py) is not installed.",
        )
    interpreter_path = sys.executable.strip()
    if not interpreter_path:
        return NvmlRuntimeStatus(
            outcome=NvmlRuntimeOutcome.INTERPRETER_UNAVAILABLE,
            return_code=NVML_PREFLIGHT_LAUNCH_FAILURE_RETURN_CODE,
            detail="No Python interpreter path is available to isolate the NVML probe.",
        )
    result = run_argv_capture(
        [interpreter_path, "-c", NVML_PREFLIGHT_SCRIPT],
        timeout=CONTROL_TIMEOUT_SEC,
    )
    return _classify_preflight_result(result.return_code, result.stderr)


def _classify_preflight_result(return_code: int, stderr: str) -> NvmlRuntimeStatus:
    detail = _trim_detail(stderr)
    if return_code == NVML_PREFLIGHT_EXIT_USABLE:
        return NvmlRuntimeStatus(
            outcome=NvmlRuntimeOutcome.USABLE,
            return_code=return_code,
            detail=detail or "NVML initialized successfully in an isolated process.",
        )
    if return_code == NVML_PREFLIGHT_EXIT_MODULE_MISSING:
        return NvmlRuntimeStatus(
            outcome=NvmlRuntimeOutcome.MODULE_MISSING,
            return_code=return_code,
            detail=detail or "pynvml (nvidia-ml-py) is not importable in the runtime interpreter.",
        )
    if return_code == NVML_PREFLIGHT_EXIT_NVML_UNAVAILABLE:
        return NvmlRuntimeStatus(
            outcome=NvmlRuntimeOutcome.NVML_UNAVAILABLE,
            return_code=return_code,
            detail=detail or "NVML reported that no usable NVIDIA driver is present.",
        )
    if return_code == NVML_PREFLIGHT_TIMEOUT_RETURN_CODE:
        return NvmlRuntimeStatus(
            outcome=NvmlRuntimeOutcome.PROBE_TIMED_OUT,
            return_code=return_code,
            detail=detail or "The isolated NVML probe did not finish within the probe timeout.",
        )
    if return_code == NVML_PREFLIGHT_LAUNCH_FAILURE_RETURN_CODE:
        return NvmlRuntimeStatus(
            outcome=NvmlRuntimeOutcome.INTERPRETER_UNAVAILABLE,
            return_code=return_code,
            detail=detail or "The isolated NVML probe interpreter could not be launched.",
        )
    return NvmlRuntimeStatus(
        outcome=NvmlRuntimeOutcome.PROBE_CRASHED,
        return_code=return_code,
        detail=detail or "The isolated NVML probe terminated abnormally without a Python error.",
    )


def _trim_detail(stderr: str) -> str:
    normalized = " ".join(stderr.split())
    if len(normalized) <= NVML_PREFLIGHT_DETAIL_MAX_CHARS:
        return normalized
    return normalized[:NVML_PREFLIGHT_DETAIL_MAX_CHARS]
