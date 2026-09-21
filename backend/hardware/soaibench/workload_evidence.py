"""SoAI - SoAIBench V2 auditable workload evidence [backend/hardware/soaibench/workload_evidence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from hardware.soaibench.workload_common import FLOAT_SIZE_BYTES, SoAIBenchPhaseResult

__all__ = ("final_write_bytes", "phase_evidence")


def phase_evidence(
    result: SoAIBenchPhaseResult,
    *,
    counted_operations: int,
    counted_bytes: int,
    throughput: float,
) -> JSONDict:
    evidence: JSONDict = {
        "elapsed_seconds": result.elapsed_seconds,
        "element_count": result.element_count,
        "rounds": result.rounds,
        "dispatches": result.dispatches,
        "counted_operations": counted_operations,
        "counted_bytes": counted_bytes,
        "throughput": round(throughput, 6),
    }
    if result.sample_positions and result.sample_values:
        evidence["sample_positions"] = list(result.sample_positions)
        evidence["sample_values"] = list(result.sample_values)
    return evidence


def final_write_bytes(result: SoAIBenchPhaseResult) -> int:
    return result.element_count * FLOAT_SIZE_BYTES * result.dispatches
