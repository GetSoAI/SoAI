"""SoAI - NVIDIA query resolver with NVML and nvidia-smi paths [backend/hardware/vendors/nvidia/query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from hardware.vendors.nvidia import scan
from hardware.vendors.nvidia.smi_scan import query_nvidia_gpus_via_smi

__all__ = ("resolve_query_nvidia_gpus",)

if TYPE_CHECKING:
    from core.hardware.protocols import (
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.types.json import JSONDict


def _query_nvidia_gpus(
    detailed: bool,
    *,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> tuple[list[JSONDict], JSONDict]:
    if nvml_gate.nvml_available:
        return scan.query_nvidia_gpus(
            detailed,
            nvml_gate=nvml_gate,
            capabilities_cache_service=capabilities_cache_service,
        )
    return query_nvidia_gpus_via_smi(
        detailed,
        nvml_gate=nvml_gate,
        capabilities_cache_service=capabilities_cache_service,
    )


def resolve_query_nvidia_gpus() -> Callable[..., tuple[list[JSONDict], JSONDict]]:
    return _query_nvidia_gpus
