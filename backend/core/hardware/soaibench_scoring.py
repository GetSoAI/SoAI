"""SoAI - Pure SoAIBench scoring [backend/core/hardware/soaibench_scoring.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

STANDARD_COMPUTE_WEIGHT = 0.40
STANDARD_MEMORY_WEIGHT = 0.60
STRESS_COMPUTE_WEIGHT = 0.70
STRESS_MEMORY_WEIGHT = 0.30

__all__ = ("SoAIBenchScores", "standard_scores", "stress_scores")


@dataclass(frozen=True, slots=True)
class SoAIBenchScores:
    overall: int
    compute: int
    memory: int


def standard_scores(compute_gops: float, memory_gbs: float) -> SoAIBenchScores:
    compute = max(0.0, round(compute_gops, 6))
    memory = max(0.0, round(memory_gbs, 6))
    return SoAIBenchScores(
        overall=round(STANDARD_COMPUTE_WEIGHT * compute + STANDARD_MEMORY_WEIGHT * memory),
        compute=round(compute),
        memory=round(memory),
    )


def stress_scores(compute_gops: float, memory_gbs: float) -> SoAIBenchScores:
    compute = max(0.0, round(compute_gops, 6))
    memory = max(0.0, round(memory_gbs, 6))
    return SoAIBenchScores(
        overall=round(STRESS_COMPUTE_WEIGHT * compute + STRESS_MEMORY_WEIGHT * memory),
        compute=round(compute),
        memory=round(memory),
    )
