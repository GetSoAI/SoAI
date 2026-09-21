"""SoAI - SoAIBench worker profile dispatch [backend/hardware/soaibench/worker_profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.soaibench.types import SoAIBenchBenchmarkMode, SoAIBenchProfile
from hardware.soaibench.worker_certified import run_certified_standard
from hardware.soaibench.worker_execution import run_stress
from hardware.soaibench.worker_standard import run_standard

if TYPE_CHECKING:
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
    from hardware.soaibench.worker_context import (
        SoAIBenchWorkerEventContext,
        SoAIBenchWorkerRuntimeContext,
    )

__all__ = ("run_selected_profile",)

QUICK_STRESS_DURATION_SECONDS = 60.0


async def run_selected_profile(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    profile: SoAIBenchProfile,
    benchmark_mode: SoAIBenchBenchmarkMode,
) -> None:
    if profile == SoAIBenchProfile.STRESS:
        await run_stress(
            opencl_pool=opencl_pool,
            runtime_context=runtime_context,
            event_context=event_context,
            max_duration_seconds=_stress_duration_for_mode(benchmark_mode),
        )
        return
    if benchmark_mode == SoAIBenchBenchmarkMode.CERTIFIED:
        await run_certified_standard(
            opencl_pool=opencl_pool,
            runtime_context=runtime_context,
            event_context=event_context,
        )
    else:
        await run_standard(
            opencl_pool=opencl_pool,
            runtime_context=runtime_context,
        )


def _stress_duration_for_mode(benchmark_mode: SoAIBenchBenchmarkMode) -> float | None:
    if benchmark_mode == SoAIBenchBenchmarkMode.QUICK:
        return QUICK_STRESS_DURATION_SECONDS
    return None
