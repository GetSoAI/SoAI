"""SoAI - SoAIBench V1 types [backend/hardware/soaibench/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = (
    "SOAIBENCH_SCORE_VERSION",
    "SoAIBenchBenchmarkMode",
    "SoAIBenchGpuIdentity",
    "SoAIBenchProfile",
    "SoAIBenchRunStatus",
)

SOAIBENCH_SCORE_VERSION = "soaibench-v1"


class SoAIBenchBenchmarkMode(StrEnum):
    QUICK = "quick"
    CERTIFIED = "certified"


class SoAIBenchProfile(StrEnum):
    STANDARD = "standard"
    STRESS = "stress"


class SoAIBenchRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    UNSTABLE = "unstable"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STOPPED = "stopped"
    UNSUPPORTED = "unsupported"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class SoAIBenchGpuIdentity:
    device_id: str
    gpu_name: str | None
    gpu_model_key: str | None
    vendor: str | None
    driver_version: str | None
    gpu_uuid: str | None
    pci_bdf: str | None
    kernel_driver: str | None
    operating_system: str | None
    gpu_index: int | None
