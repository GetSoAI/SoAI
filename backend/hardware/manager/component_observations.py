"""SoAI - Component observation freshness and acceptance [backend/hardware/manager/component_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_telemetry import GPU_LIVE_SENSOR_FIELDS
from core.types.json import JSONDict, JSONValue
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_optional_non_negative_int_strict,
)
from hardware.gpu_inventory.memory_metrics import gpu_capacity_is_current
from hardware.manager.storage_observations import disk_rows, reconcile_disk_rows

__all__ = (
    "OPTIONAL_PROBE_EXCEPTIONS",
    "OBSERVATION_STATES",
    "ComponentObservation",
    "observed_status",
    "unavailable_status",
    "component_statuses",
    "require_observation_status",
    "require_component_value",
    "accept_component_observations",
    "observations_reusable",
    "disconnected_snapshot",
    "current_history_snapshot",
    "is_current_observation_sample",
)

OPTIONAL_PROBE_EXCEPTIONS: tuple[type[Exception], ...] = (OSError,) + RECOVERABLE_EXCEPTIONS
OBSERVATION_STATES = ("available", "partial", "stale", "unavailable", "disconnected")


@dataclass(slots=True)
class ComponentObservation:
    accepted_sequence: int
    checked_monotonic: float
    observed_monotonic: float | None
    metadata: JSONDict


def observed_status(current_time_ms: int, *, status: str = "available") -> JSONDict:
    return {
        "status": status,
        "observed_at_ms": current_time_ms if status in ("available", "partial") else None,
        "checked_at_ms": current_time_ms,
        "sampled_current": status in ("available", "partial"),
    }


def unavailable_status(current_time_ms: int, *, error_code: str) -> JSONDict:
    status = observed_status(current_time_ms, status="unavailable")
    status["error_code"] = error_code
    return status


def component_statuses(snapshot: Mapping[str, JSONValue]) -> JSONDict:
    metadata = snapshot.get("component_status")
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValidationError("Hardware component metadata must be an object.")
    return metadata


def require_observation_status(metadata: JSONDict) -> None:
    if metadata.get("status") not in OBSERVATION_STATES:
        raise ValidationError("Hardware component observation state is invalid.")
    checked = metadata.get("checked_at_ms")
    observed = metadata.get("observed_at_ms")
    require_non_negative_int_strict(
        checked, error_message="Hardware component check timestamp is invalid."
    )
    require_optional_non_negative_int_strict(
        observed, error_message="Hardware component observation timestamp is invalid."
    )
    if metadata["status"] in ("available", "partial") and observed is None:
        raise ValidationError("Observed hardware component has no observation timestamp.")
    if "sampled_current" in metadata and not isinstance(metadata["sampled_current"], bool):
        raise ValidationError("Hardware component sample authority is invalid.")


def require_component_value(component: str, value: JSONValue) -> None:
    if component in ("cpus", "disk"):
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ValidationError("Hardware component list is invalid.")
    elif not isinstance(value, dict):
        raise ValidationError("Hardware component object is invalid.")


def accept_component_observations(
    *,
    cached: JSONDict,
    observations: dict[str, ComponentObservation],
    sequences: Mapping[str, int],
    snapshot: JSONDict,
    checked_monotonic: float,
    checked_at_ms: int,
) -> set[str]:
    metadata = deepcopy(component_statuses(snapshot))
    prepared_disk: list[JSONDict] | None = None
    accepted: set[str] = set()
    for component in sequences:
        candidate = metadata.get(component)
        if candidate is not None:
            if not isinstance(candidate, dict):
                raise ValidationError("Hardware component observation must be an object.")
            require_observation_status(candidate)
            if (
                candidate["status"] in ("available", "partial")
                and component not in snapshot
                and component != "gpu_capabilities"
            ):
                raise ValidationError("Observed hardware component has no value.")
        if component in snapshot:
            require_component_value(component, snapshot[component])
            if component == "disk":
                disk_rows(snapshot[component], require_observation_status)
                disk_status = (
                    candidate if isinstance(candidate, dict) else observed_status(checked_at_ms)
                )
                previous = observations.get(component)
                if disk_status["status"] in ("available", "partial"):
                    prepared_disk = reconcile_disk_rows(
                        snapshot[component],
                        cached.get(component, []),
                        disk_status,
                        previous.metadata if previous is not None else {},
                        require_observation_status,
                    )
                    for row in prepared_disk:
                        row_status = row.get("observation_status")
                        if isinstance(row_status, dict) and row_status.get("status") not in (
                            "available",
                            "partial",
                        ):
                            row_status["sampled_current"] = False
                require_observation_status(disk_status)
                metadata[component] = disk_status
    for component, sequence in sequences.items():
        candidate = metadata.get(component)
        if candidate is None and component not in snapshot:
            continue
        if candidate is None:
            candidate = observed_status(checked_at_ms)
        if not isinstance(candidate, dict):
            raise ValidationError("Hardware component observation must be an object.")
        candidate = deepcopy(candidate)
        if "observed_at_ms" not in candidate:
            candidate["observed_at_ms"] = None
        require_observation_status(candidate)
        previous = observations.get(component)
        if previous is not None and sequence <= previous.accepted_sequence:
            continue
        successful = candidate["status"] in ("available", "partial")
        observed_monotonic = None if previous is None else previous.observed_monotonic
        if successful:
            if component not in snapshot and component != "gpu_capabilities":
                raise ValidationError("Observed hardware component has no value.")
            if component in snapshot:
                cached[component] = (
                    deepcopy(prepared_disk)
                    if component == "disk"
                    else deepcopy(snapshot[component])
                )
            observed_monotonic = checked_monotonic
        else:
            candidate["sampled_current"] = False
            if component in cached:
                candidate["status"] = "stale"
                candidate["observed_at_ms"] = (
                    previous.metadata.get("observed_at_ms")
                    if previous is not None
                    else candidate.get("observed_at_ms")
                )
            elif component in snapshot and candidate.get("observed_at_ms") is not None:
                cached[component] = deepcopy(snapshot[component])
        observations[component] = ComponentObservation(
            sequence, checked_monotonic, observed_monotonic, candidate
        )
        accepted.add(component)
    cached["component_status"] = {
        key: deepcopy(value.metadata) for key, value in observations.items()
    }
    cpus = cached.get("cpus")
    if isinstance(cpus, list) and cpus:
        cached["cpu"] = deepcopy(cpus[0]) if isinstance(cpus[0], dict) else {}
    else:
        cached.pop("cpu", None)
    statuses = component_statuses(cached)
    if "cpus" in statuses:
        statuses["cpu"] = deepcopy(statuses["cpus"])
    return accepted


def observations_reusable(
    observations: Mapping[str, ComponentObservation],
    components: set[str],
    *,
    now_monotonic: float,
    cache_ttl_seconds: float,
) -> bool:
    for component in components - {"timestamp_ms", "cpu"}:
        observation = observations.get(component)
        if observation is None:
            return False
        if now_monotonic - observation.checked_monotonic >= cache_ttl_seconds:
            return False
    return True


def disconnected_snapshot(snapshot: JSONDict) -> JSONDict:
    retained = deepcopy(snapshot)
    metadata = component_statuses(retained)
    for component in set(retained) | set(metadata):
        if component in ("timestamp_ms", "component_status"):
            continue
        status = metadata.get(component)
        if not isinstance(status, dict):
            status = {"observed_at_ms": None, "checked_at_ms": retained.get("timestamp_ms", 0)}
        status["status"] = "disconnected"
        status["sampled_current"] = False
        metadata[component] = status
    if metadata:
        retained["component_status"] = metadata
    return retained


def current_history_snapshot(snapshot: JSONDict) -> JSONDict:
    current = deepcopy(snapshot)
    metadata = component_statuses(snapshot)
    for component, raw_status in metadata.items():
        if not isinstance(raw_status, dict):
            raise ValidationError("Hardware history observation must be an object.")
        if not is_current_observation_sample(raw_status, snapshot.get("timestamp_ms")):
            current.pop(component, None)
    if "network" not in current and "network_speed" in current:
        network = snapshot.get("network")
        if isinstance(network, dict):
            current["network"] = {
                key: deepcopy(value)
                for key, value in network.items()
                if key in ("interfaces", "by_device_id")
            }
    disk = current.get("disk")
    gpu_payload = current.get("gpu")
    if isinstance(gpu_payload, dict):
        gpu_rows = gpu_payload.get("gpus")
        if isinstance(gpu_rows, list):
            for row in gpu_rows:
                if isinstance(row, dict) and isinstance(
                    observation := row.get("telemetry_observation"), dict
                ):
                    if not is_current_observation_sample(observation, snapshot.get("timestamp_ms")):
                        for field in GPU_LIVE_SENSOR_FIELDS:
                            if field in row:
                                row[field] = None
                if isinstance(row, dict) and not gpu_capacity_is_current(row):
                    row["memory_total_mb"] = None
                    row["memory_total_bytes"] = None
                    row["memory_total_reported_value"] = None
    if isinstance(disk, list):
        fresh_rows: list[JSONDict] = []
        for row in disk_rows(disk, require_observation_status):
            status = row.get("observation_status")
            if not isinstance(status, dict) or (
                is_current_observation_sample(status, snapshot.get("timestamp_ms"))
            ):
                fresh_rows.append(row)
        current["disk"] = fresh_rows
    return current


def is_current_observation_sample(metadata: JSONDict, timestamp: JSONValue) -> bool:
    require_observation_status(metadata)
    if metadata["status"] not in ("available", "partial"):
        return False
    if "sampled_current" in metadata:
        return metadata["sampled_current"] is True
    return metadata.get("observed_at_ms") == timestamp
