"""SoAI - Physically bound GPU sensor freshness reconciliation [backend/hardware/gpu_inventory/sensor_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from copy import deepcopy

from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.gpu_telemetry import GPU_LIVE_SENSOR_FIELDS
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.strict_integer import is_strict_int
from hardware.gpu_inventory.physical_binding import match_gpu_inventory_sources
from hardware.manager.component_observations import observed_status, unavailable_status

__all__ = ("reconcile_gpu_sensor_observations",)


def reconcile_gpu_sensor_observations(
    gpus: list[JSONDict], retained_payload: JSONDict | None
) -> None:
    checked_at = epoch_ms()
    retained_rows = retained_payload.get("gpus") if retained_payload is not None else None
    retained = (
        [row for row in retained_rows if isinstance(row, dict)]
        if isinstance(retained_rows, list)
        else []
    )
    joins = match_gpu_inventory_sources(gpus, retained)
    retained_pairs = dict(joins.pairs)
    for index, gpu in enumerate(gpus):
        if gpu.get("telemetry_available") is not False and any(
            gpu.get(field) is not None for field in GPU_LIVE_SENSOR_FIELDS
        ):
            observed_at = gpu.get("telemetry_observed_at_ms")
            timestamp = observed_at if is_strict_int(observed_at) else checked_at
            metadata = observed_status(timestamp)
            metadata.update({"checked_at_ms": checked_at, "age_ms": max(0, checked_at - timestamp)})
            gpu["telemetry_observation"] = metadata
            continue
        metadata = unavailable_status(
            checked_at,
            error_code=(
                "gpu_sensor_permission_denied"
                if gpu.get("telemetry_unavailable_reason") == "permission_denied"
                else "monitoring_sample_unavailable"
            ),
        )
        if (
            index in retained_pairs
            and joins.baseline_results[index].state == GPUPhysicalBindingState.BOUND
        ):
            previous = retained[retained_pairs[index]]
            observation = previous.get("telemetry_observation")
            observed_at = (
                observation.get("observed_at_ms") if isinstance(observation, dict) else None
            )
            if is_strict_int(observed_at) and observed_at >= 0:
                for field in GPU_LIVE_SENSOR_FIELDS:
                    if field in previous:
                        gpu[field] = deepcopy(previous[field])
                metadata.update(
                    {
                        "status": "stale",
                        "observed_at_ms": observed_at,
                        "age_ms": max(0, checked_at - observed_at),
                    }
                )
        gpu["telemetry_observation"] = metadata
