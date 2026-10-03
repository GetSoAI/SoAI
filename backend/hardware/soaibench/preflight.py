"""SoAI - SoAIBench OpenCL preflight flow [backend/hardware/soaibench/preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import require_standard_memory_capability

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol

__all__ = ("preflight_blocking", "run_preflight")


async def run_preflight(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
) -> JSONDict:
    return await opencl_pool.preflight(identity, timeout_sec=60.0)


def preflight_blocking(session: OpenCLExecutionSession, identity: SoAIBenchGpuIdentity) -> JSONDict:
    runtime = session.runtime_for(identity)
    require_standard_memory_capability(runtime)
    return {
        "match_basis": runtime.match_basis,
        "queue_api": runtime.queue_api,
        "opencl_platform_name": runtime.platform_name,
        "opencl_platform_vendor": runtime.platform_vendor,
        "opencl_device_name": runtime.device_name,
        "opencl_device_vendor": runtime.device_vendor,
        "opencl_driver_version": runtime.driver_version,
        "opencl_enumeration_warnings": list(runtime.enumeration_warnings),
    }
