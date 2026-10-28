"""SoAI - Windows native capacity observation retention [backend/hardware/gpu_inventory/windows_capacity_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy

from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.strict_integer import is_strict_int
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)
from hardware.manager.component_observations import observed_status, unavailable_status
from hardware.vendors.vendor_types import AMD_VENDOR

__all__ = ("reconcile_windows_capacity_observations",)

CAPACITY_FIELDS = (
    "memory_total_mb",
    "memory_total_bytes",
    "memory_total_source",
    "memory_total_unit",
    "memory_total_reported_value",
)


def reconcile_windows_capacity_observations(
    gpus: list[JSONDict], retained_payload: JSONDict | None
) -> None:
    checked_at_ms = epoch_ms()
    retained_value = retained_payload.get("gpus") if retained_payload is not None else None
    retained = (
        [entry for entry in retained_value if isinstance(entry, dict)]
        if isinstance(retained_value, list)
        else []
    )
    for gpu in gpus:
        source = gpu.get("memory_total_source")
        if gpu.get("memory_total_mb") is not None and source != "win32_video_controller.AdapterRAM":
            metadata = observed_status(checked_at_ms)
            metadata.update({"source": source, "age_ms": 0})
            gpu["memory_total_status"] = "available"
            gpu["memory_total_observation"] = metadata
            continue
        reason = gpu.get("memory_total_unavailable_reason")
        metadata = unavailable_status(
            checked_at_ms,
            error_code=reason if isinstance(reason, str) else "native_memory_unavailable",
        )
        metadata.update({"source": source, "age_ms": None})
        if gpu.get("type") == AMD_VENDOR and reason == "native_session_busy":
            current_binding = resolve_gpu_physical_binding(gpu, gpus)
            retained_binding = resolve_gpu_physical_binding(gpu, retained)
            candidates = [
                entry
                for entry in retained
                if match_gpu_physical_identity(gpu, entry) == GPUPhysicalBindingState.BOUND
            ]
            previous = candidates[0] if len(candidates) == 1 else None
            observation = previous.get("memory_total_observation") if previous is not None else None
            observed_at = (
                observation.get("observed_at_ms") if isinstance(observation, dict) else None
            )
            capacity_bytes = previous.get("memory_total_bytes") if previous is not None else None
            unique_binding = (
                current_binding.state == GPUPhysicalBindingState.BOUND
                and retained_binding.state == GPUPhysicalBindingState.BOUND
                and gpu.get("control_binding_state")
                not in ("identity_conflict", "invalid_response")
            )
            if unique_binding and previous is not None:
                if (
                    previous.get("memory_total_source") == "adl.ADL2_Adapter_MemoryInfo2_Get"
                    and is_strict_int(capacity_bytes)
                    and capacity_bytes > 0
                    and is_strict_int(observed_at)
                ):
                    for field in CAPACITY_FIELDS:
                        gpu[field] = copy.deepcopy(previous.get(field))
                    metadata.update(
                        {
                            "status": "stale",
                            "observed_at_ms": observed_at,
                            "age_ms": max(0, checked_at_ms - observed_at),
                            "source": previous.get("memory_total_source"),
                        }
                    )
                    gpu["memory_total_status"] = "stale"
        gpu["memory_total_observation"] = metadata
