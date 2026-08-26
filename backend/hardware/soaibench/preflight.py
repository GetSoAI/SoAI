"""SoAI - SoAIBench OpenCL preflight flow [backend/hardware/soaibench/preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import (
    BoundedBlockingTimeoutBase,
    run_bounded_blocking_call,
)
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from core.validation.numberish import require_int_from_numberish
from hardware.soaibench.device_matching import match_opencl_device
from hardware.soaibench.errors import SoAIBenchUnsupported, unsupported_guidance
from hardware.soaibench.opencl_devices import enumerate_opencl_gpu_devices
from hardware.soaibench.types import SoAIBenchGpuIdentity, SoAIBenchRunStatus
from hardware.vendors.vendor_metadata import vendor_aliases
from hardware.vendors.vendor_types import NVIDIA_VENDOR

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.types.json import JSONDict

__all__ = (
    "finish_preflight_unsupported",
    "run_preflight",
)


async def run_preflight(
    *,
    opencl_pool: BoundedBlockingPool,
    identity: SoAIBenchGpuIdentity,
) -> JSONDict:
    try:
        return await run_bounded_blocking_call(
            opencl_pool,
            _preflight_blocking,
            identity,
            timeout_sec=10.0,
        )
    except BoundedBlockingTimeoutBase as exception:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="SoAIBench OpenCL preflight timed out.",
        ) from exception


async def finish_preflight_unsupported(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run: JSONDict,
    exception: SoAIBenchUnsupported,
) -> JSONDict:
    completed_at_ms = epoch_ms()
    started_at_ms = require_int_from_numberish(run["started_at_ms"], field="started_at_ms")
    await database_hardware.finish_soaibench_run(
        str(run["run_id"]),
        {
            "status": SoAIBenchRunStatus.UNSUPPORTED.value,
            "completed_at_ms": completed_at_ms,
            "duration_ms": max(0, completed_at_ms - started_at_ms),
            "sample_count": 0,
            "summary_json": serialize_json_compact_stable(
                {
                    "message": exception.message,
                    "guidance": unsupported_guidance(exception.reason),
                },
            ),
            "unsupported_reason": exception.reason,
        },
    )
    refreshed = await database_hardware.get_soaibench_run_for_user(
        user_id=require_int_from_numberish(run["created_by_user_id"], field="created_by_user_id"),
        run_id=str(run["run_id"]),
    )
    if refreshed is None:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="SoAIBench terminal preflight row was not found.",
        )
    return refreshed


def _preflight_blocking(identity: SoAIBenchGpuIdentity) -> JSONDict:
    _validate_driver_binding(identity)
    candidates = enumerate_opencl_gpu_devices()
    match = match_opencl_device(identity, candidates)
    return {
        "match_basis": match.match_basis,
        "opencl_platform_name": match.device.platform_name,
        "opencl_platform_vendor": match.device.platform_vendor,
        "opencl_device_name": match.device.device_name,
        "opencl_device_vendor": match.device.device_vendor,
        "opencl_driver_version": match.device.driver_version,
    }


def _validate_driver_binding(identity: SoAIBenchGpuIdentity) -> None:
    if NVIDIA_VENDOR not in vendor_aliases(identity.vendor or ""):
        return
    if identity.kernel_driver == "nvidia":
        return
    operating_system = (identity.operating_system or "").strip().lower()
    if operating_system and operating_system != "linux":
        return
    raise SoAIBenchUnsupported(
        reason="gpu_driver_inactive",
        message=(
            "The selected NVIDIA GPU is present on PCIe but is not bound to the "
            "active NVIDIA kernel driver."
        ),
    )
