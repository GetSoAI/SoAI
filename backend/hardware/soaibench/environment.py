"""SoAI - SoAIBench certified environment snapshots [backend/hardware/soaibench/environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import platform
from typing import TYPE_CHECKING

from core.meta.version import __version__
from core.types.json_value import coerce_json_dict_or_empty
from hardware.soaibench.gpu_identity import identity_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = ("build_soaibench_environment", "system_evidence_from_snapshot")

CPU_NAME_SUMMARY_FIELD = "system_cpu_name"
RAM_GB_SUMMARY_FIELD = "system_ram_gb"


def build_soaibench_environment(
    *,
    identity: SoAIBenchGpuIdentity,
    settings_snapshot: JSONDict,
    preflight_summary: JSONDict,
    workload_summary: JSONDict,
) -> JSONDict:
    return {
        "soai_version": __version__,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "cpu_name": preflight_summary.get(CPU_NAME_SUMMARY_FIELD),
        "system_ram_gb": preflight_summary.get(RAM_GB_SUMMARY_FIELD),
        "gpu_identity": identity_payload(identity),
        "gpu_settings": settings_snapshot,
        "opencl": _opencl_payload(preflight_summary),
        "workload": workload_summary,
    }


def system_evidence_from_snapshot(snapshot: JSONDict) -> JSONDict:
    cpus = snapshot.get("cpus")
    memory = coerce_json_dict_or_empty(snapshot.get("memory"))
    ram_gb = memory.get("total_gb")
    return {
        CPU_NAME_SUMMARY_FIELD: _cpu_configuration_name(cpus),
        RAM_GB_SUMMARY_FIELD: (
            ram_gb
            if isinstance(ram_gb, int | float)
            and not isinstance(ram_gb, bool)
            and math.isfinite(float(ram_gb))
            and ram_gb > 0
            else None
        ),
    }


def _cpu_configuration_name(cpus: JSONValue) -> str | None:
    if not isinstance(cpus, list) or not cpus:
        return None
    counts: dict[str, int] = {}
    for cpu in cpus:
        if not isinstance(cpu, dict):
            return None
        name = cpu.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        normalized = " ".join(name.split())
        counts[normalized] = counts.get(normalized, 0) + 1
    if len(counts) == 1:
        name, count = next(iter(counts.items()))
        return name if count == 1 else f"{count}x {name}"
    return " + ".join(f"{count}x {name}" for name, count in counts.items())


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
