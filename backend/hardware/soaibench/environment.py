"""SoAI - SoAIBench certified environment snapshots [backend/hardware/soaibench/environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform
from typing import TYPE_CHECKING

from core.meta.version import __version__
from core.types.json_value import coerce_json_dict_or_empty
from hardware.control_snapshots import find_gpu_entry
from hardware.soaibench.gpu_identity import identity_payload
from hardware.soaibench.telemetry import settings_snapshot_from_gpu
from hardware.windows_cpu_info import sanitize_cpu_display_name

if TYPE_CHECKING:
    from core.hardware.protocols import HardwareManagerProtocol
    from core.types.json import JSONDict
    from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = ("build_soaibench_environment",)


async def build_soaibench_environment(
    *,
    hardware_manager: HardwareManagerProtocol,
    identity: SoAIBenchGpuIdentity,
    workload_summary: JSONDict,
) -> JSONDict:
    hardware_snapshot = await hardware_manager.get_system_info(["gpu"], cache=False)
    gpu = find_gpu_entry(hardware_snapshot, identity.device_id) or {}
    return {
        "soai_version": __version__,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "processor": sanitize_cpu_display_name(platform.processor()) or "",
        "gpu_identity": identity_payload(identity),
        "gpu_settings": settings_snapshot_from_gpu(gpu),
        "opencl": _opencl_payload(workload_summary),
    }


def _opencl_payload(summary: JSONDict) -> JSONDict:
    return {
        "match_basis": summary.get("match_basis"),
        "queue_api": summary.get("queue_api"),
        "platform_name": summary.get("opencl_platform_name"),
        "platform_vendor": summary.get("opencl_platform_vendor"),
        "device_name": summary.get("opencl_device_name"),
        "device_vendor": summary.get("opencl_device_vendor"),
        "driver_version": summary.get("opencl_driver_version"),
        **coerce_json_dict_or_empty(summary.get("opencl")),
    }
