"""SoAI - SoAIBench certified pass execution [backend/hardware/soaibench/worker_certified_passes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from hardware.soaibench.runtime import (
    CERTIFIED_MEASURED_PASSES,
    CERTIFIED_WARMUP_PASSES,
)
from hardware.soaibench.worker_execution import (
    run_alu_phase,
    run_compute_phase,
    run_latency_phase,
    run_matrix_phase,
    run_memory_phase,
    run_mixed_phase,
)
from hardware.soaibench.workload import SoAIBenchWorkloadResult, score_standard_phases

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.types.json import JSONDict
    from hardware.soaibench.types import SoAIBenchGpuIdentity

    type CertifiedPhaseProgress = Callable[[str, int], Awaitable[None]]

__all__ = ("certification_payload", "pass_payload", "run_certified_pass")

CERTIFIED_PHASE_TIMEOUT_SECONDS = 300.0


async def run_certified_pass(
    opencl_pool: BoundedBlockingPool,
    identity: SoAIBenchGpuIdentity,
    stop_event: asyncio.Event,
    phase_progress: CertifiedPhaseProgress,
) -> SoAIBenchWorkloadResult | None:
    if stop_event.is_set():
        return None
    await phase_progress("compute", 1)
    if stop_event.is_set():
        return None
    compute = await run_compute_phase(
        opencl_pool=opencl_pool,
        identity=identity,
        timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
    )
    if stop_event.is_set():
        return None
    await phase_progress("alu", 2)
    if stop_event.is_set():
        return None
    alu = await run_alu_phase(
        opencl_pool=opencl_pool,
        identity=identity,
        timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
    )
    if stop_event.is_set():
        return None
    await phase_progress("matrix", 3)
    if stop_event.is_set():
        return None
    matrix = await run_matrix_phase(
        opencl_pool=opencl_pool,
        identity=identity,
        timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
    )
    if stop_event.is_set():
        return None
    await phase_progress("latency", 4)
    if stop_event.is_set():
        return None
    latency = await run_latency_phase(
        opencl_pool=opencl_pool,
        identity=identity,
        timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
    )
    if stop_event.is_set():
        return None
    await phase_progress("memory", 5)
    if stop_event.is_set():
        return None
    memory = await run_memory_phase(
        opencl_pool=opencl_pool,
        identity=identity,
        timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
    )
    if stop_event.is_set():
        return None
    await phase_progress("stability", 6)
    if stop_event.is_set():
        return None
    mixed = await run_mixed_phase(
        opencl_pool=opencl_pool,
        identity=identity,
        stress=False,
        timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
    )
    if stop_event.is_set():
        return None
    return score_standard_phases(
        alu=alu,
        compute=compute,
        matrix=matrix,
        memory=memory,
        mixed=mixed,
        latency=latency,
    )


def pass_payload(
    index: int,
    result: SoAIBenchWorkloadResult,
    telemetry: JSONDict,
    *,
    warmup: bool,
) -> JSONDict:
    return {
        "index": index,
        "warmup": warmup,
        **result.score_fields,
        "duration_ms": result.duration_ms,
        "sample_count": result.sample_count,
        "telemetry": telemetry,
    }


def certification_payload(result: SoAIBenchWorkloadResult) -> JSONDict:
    return {
        "mode": "certified",
        "warmup_pass_count": CERTIFIED_WARMUP_PASSES,
        "measured_pass_count": CERTIFIED_MEASURED_PASSES,
        "leaderboard_eligible": result.summary.get("leaderboard_eligible") is True,
        "leaderboard_rejection_reason": result.summary.get("leaderboard_rejection_reason"),
        "score_variance_percent": result.summary.get("score_variance_percent"),
        "score_confidence": result.summary.get("score_confidence"),
    }
