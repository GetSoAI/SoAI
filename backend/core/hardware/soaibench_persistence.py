"""SoAI - SoAIBench persistence outcomes [backend/core/hardware/soaibench_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.types.json import JSONDict

__all__ = (
    "SOAIBENCH_GPU_HISTORY_IDENTITY_FIELDS",
    "SoAIBenchMutationOutcome",
    "SoAIBenchMutationResult",
    "SoAIBenchReconciliationResult",
)

SOAIBENCH_GPU_HISTORY_IDENTITY_FIELDS: tuple[str, ...] = (
    "device_id",
    "gpu_name",
    "gpu_model_key",
    "vendor",
    "driver_version",
    "gpu_uuid",
    "pci_bdf",
    "gpu_index",
)


class SoAIBenchMutationOutcome(StrEnum):
    UPDATED = "updated"
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    TERMINAL_SUPERSEDED = "terminal_superseded"
    INVARIANT_FAILURE = "invariant_failure"


@dataclass(frozen=True, slots=True)
class SoAIBenchMutationResult:
    outcome: SoAIBenchMutationOutcome
    run: JSONDict | None


@dataclass(frozen=True, slots=True)
class SoAIBenchReconciliationResult:
    runs: tuple[JSONDict, ...]
